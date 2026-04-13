"""
reviewer/agent.py — reads completed task output and decides APPROVED or REWORK.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
import re
from pathlib import Path
from dataclasses import dataclass

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Reviewer Agent. Review code and provide approval or rework feedback."""


@dataclass
class ReviewVerdict:
    approved: bool
    reason: str
    suggestions: list[str]

    @property
    def label(self) -> str:
        return "APPROVED" if self.approved else "REWORK"


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
    return path.exists() and path.stat().st_size > 0


class ReviewerAgent(AiderAgent):
    _role = "reviewer"

    def __init__(
        self,
        model: str,
        workspace: Path,
        system_prompt: str = None,
        skills: list = None,
        framework_id: str = None,
        task_id: str = None,
        iteration_id: int = None,
        rag_client=None,
        llm_client=None,
        **kwargs,
    ):
        super().__init__(
            role="reviewer",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills or [],
            framework_id=framework_id,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
            **kwargs,
        )
        self._step_results = []
        self._retry_count = {}

    def get_step_results(self) -> list[dict]:
        """Return per-step results for reporting to orchestrator."""
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  label: str, timeout: int = 90) -> dict:
        """
        Run a single readonly review step with auto-retry for non-critical failures.
        """
        MAX_AUTO_RETRIES = 2

        attempt = self._retry_count.get(label, 0) + 1
        self._retry_count[label] = attempt

        logger.info("[reviewer] step %d: %s", attempt, label)

        result = self.run_readonly(message=message, read_files=read_files, timeout=timeout)

        output_text = result if isinstance(result, str) else (result.get("output", "") if isinstance(result, dict) else "")
        success = output_text and len(output_text.strip()) > 0

        if not success:
            classification = self._classify_failure_for_review(output_text, label)
            result_dict = result if isinstance(result, dict) else {"output": output_text, "exit_code": -1, "stderr": ""}
            result_dict["severity"] = classification["severity"]
            result_dict["auto_retry"] = classification["auto_retry"]
            result_dict["needs_user_input"] = classification["needs_user_input"]
            result_dict["retry_count"] = attempt
            result_dict["escalated_message"] = classification.get("escalated_message", "")

            if classification["auto_retry"] and attempt <= MAX_AUTO_RETRIES:
                logger.info("[reviewer] auto-retrying '%s' (attempt %d/%d, severity=%s)",
                            label, attempt + 1, MAX_AUTO_RETRIES + 1, classification["severity"])
                retry_msg = classification.get("escalated_message") or message
                return self._run_step(retry_msg, read_files, label, timeout)

            if classification["needs_user_input"]:
                result_dict["needs_user_input"] = True
        else:
            result_dict = result if isinstance(result, dict) else {"output": result, "exit_code": 0, "stderr": ""}
            result_dict["severity"] = "success"
            result_dict["auto_retry"] = False
            result_dict["needs_user_input"] = False
            result_dict["retry_count"] = attempt

        self._step_results.append({
            "label": label, "success": success, "file": "",
            "exit_code": result_dict.get("exit_code", -1), "severity": result_dict.get("severity", "?"),
            "attempt": attempt,
        })
        if success:
            logger.info("[reviewer] step OK: %s", label)
        else:
            logger.warning("[reviewer] step FAILED [%s]: %s (attempt %d)",
                           result_dict.get("severity", "?"), label, attempt)
        return result_dict

    def _classify_failure_for_review(self, output_text: str, label: str) -> dict:
        import re
        if not output_text or len(output_text.strip()) < 20:
            return {"severity": "transient", "auto_retry": True, "needs_user_input": False, "escalated_message": ""}
        if self._looks_like_hallucination(output_text):
            return {"severity": "hallucination", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}
        if len(output_text.strip()) < 100:
            return {"severity": "refusal", "auto_retry": True, "needs_user_input": False,
                    "escalated_message": "CRITICAL: You MUST provide a complete review. No placeholders or stubs."}
        return {"severity": "critical", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}

    def _looks_like_hallucination(self, content: str) -> bool:
        import re
        if not content or len(content.strip()) < 20:
            return True
        lines = content.splitlines()
        placeholder_patterns = [r"TODO", r"placeholder", r"stub", r"fill.*in", r"coming soon",
                                r"auto-generat", r"skipped\b", r"incomplete\b", r"not (yet|currently) (implemented|available|generated)"]
        placeholder_lines = sum(1 for line in lines for p in placeholder_patterns if re.search(p, line, re.IGNORECASE))
        if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
            return True
        if len(content.strip()) < 100:
            return True
        if all(line.lstrip().startswith(("#", "//", "/*", "*", "*/")) or line.strip() == "" for line in lines if line.strip()):
            return True
        return False

    def _ask_user_retry(self, step_label: str, error_detail: str, severity: str) -> str:
        """Ask user what to do after a critical or hallucination failure."""
        severity_label = severity.upper()
        reply = self.ask(
            question=f"Step '{step_label}' failed [{severity_label}]: {error_detail}. What should I do?",
            suggestions=[
                "Retry with more explicit instructions",
                "Skip this step and continue",
                "Abort — I'll fix this manually",
            ],
            timeout=600,
        )
        return (reply or "").lower().strip()

    def handle_query(self, question: str, context: dict) -> str:
        code = context.get("code", context.get("code_snippet", ""))
        file = context.get("file", "")
        if self._llm:
            prompt = (
                "You are an expert code reviewer.\n"
                + (f"File: {file}\n" if file else "")
                + (f"Code:\n{code[:1000]}\n\n" if code else "")
                + f"Question from another agent:\n{question}\n\n"
                + "Give a concise technical answer. If something is wrong, "
                + "explain what and suggest the fix."
            )
            return self._llm.chat(prompt) or "No opinion available."
        return "Reviewer LLM not available."

    def review(self, task: dict, docs_dir: Path) -> ReviewVerdict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._review_impl(task, docs_dir)
        except Exception:
            logger.exception("[reviewer] unhandled error in review")
            result = ReviewVerdict(approved=False, reason="Unhandled exception", suggestions=["Manual review needed"])
        self.report_status("idle")
        return result

    def _review_impl(self, task: dict, docs_dir: Path) -> ReviewVerdict:
        target_file = self.workspace / task["file"]
        if not target_file.exists():
            logger.warning("[reviewer] file not found: %s", target_file)
            return ReviewVerdict(
                approved=False,
                reason=f"File was not created: {task['file']}",
                suggestions=["Agent must create the file before review"]
            )

        read_files = [target_file] + list(docs_dir.glob("*.md"))

        message = f"""
Review the file that was just written against its task specification.

Task specification:
{_task_summary(task)}

Read the file {task['file']} and check:
1. Does it fully implement the task description?
2. Does it meet every acceptance criterion?
3. Is the code/config/docs correct and consistent with the project architecture?
4. Are there any missing imports, broken references, or wrong field names?

Respond with EXACTLY one of these formats — no preamble:

APPROVED

or:

REWORK: <one-line reason>
- <specific fix needed>
- <specific fix needed>
"""
        output = self._run_step(message, read_files, "review task", timeout=90)
        output_text = output if isinstance(output, str) else (output.get("output", "") if isinstance(output, dict) else "")

        if not output_text or len(output_text.strip()) == 0:
            if output.get("needs_user_input"):
                decision = self._ask_user_retry("review task",
                                                output.get("stderr", "no output"),
                                                output.get("severity", "critical"))
                if "abort" in decision:
                    return ReviewVerdict(approved=False, reason="Review aborted", suggestions=[])
                if "skip" in decision:
                    return ReviewVerdict(approved=True, reason="Auto-approved after skip", suggestions=[])
                escalated = output.get("escalated_message", "") or "CRITICAL: Review the file and respond with APPROVED or REWORK."
                output = self._run_step(escalated, read_files, "review task (user-retry)", timeout=90)
                output_text = output if isinstance(output, str) else (output.get("output", "") if isinstance(output, dict) else "")
            elif output.get("auto_retry"):
                pass  # Already auto-retried

        return self._parse_verdict(output_text or "", task["file"])

    def review_iteration(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> ReviewVerdict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._review_iteration_impl(iteration, tasks, docs_dir)
        except Exception:
            logger.exception("[reviewer] unhandled error in review_iteration")
            result = ReviewVerdict(approved=False, reason="Unhandled exception", suggestions=["Manual review needed"])
        self.report_status("idle")
        return result

    def _review_iteration_impl(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> ReviewVerdict:
        written_files = [
            self.workspace / t["file"]
            for t in tasks
            if (self.workspace / t["file"]).exists()
        ]
        read_files = written_files + list(docs_dir.glob("*.md"))

        message = f"""
Review the entire iteration output for cohesion and completeness.

Iteration: {iteration['name']}
Goal: {iteration['goal']}

Check:
1. Do all files work together consistently (imports, interfaces, field names)?
2. Is the iteration goal fully achieved?
3. Are there missing files that were expected?

Expected files:
{chr(10).join('- ' + f for f in iteration.get('files_expected', []))}

Respond EXACTLY:
APPROVED
or:
REWORK: <reason>
- <fix>
"""
        output = self._run_step(message, read_files, "review iteration", timeout=90)
        output_text = output if isinstance(output, str) else (output.get("output", "") if isinstance(output, dict) else "")

        if not output_text or len(output_text.strip()) == 0:
            if output.get("needs_user_input"):
                decision = self._ask_user_retry("review iteration",
                                                output.get("stderr", "no output"),
                                                output.get("severity", "critical"))
                if "abort" in decision:
                    return ReviewVerdict(approved=False, reason="Review aborted", suggestions=[])
                if "skip" in decision:
                    return ReviewVerdict(approved=True, reason="Auto-approved after skip", suggestions=[])
                escalated = output.get("escalated_message", "") or "CRITICAL: Review the iteration and respond with APPROVED or REWORK."
                output = self._run_step(escalated, read_files, "review iteration (user-retry)", timeout=90)
                output_text = output if isinstance(output, str) else (output.get("output", "") if isinstance(output, dict) else "")
            elif output.get("auto_retry"):
                pass  # Already auto-retried

        return self._parse_verdict(output_text or "", f"iteration {iteration['id']}")

    @staticmethod
    def _parse_verdict(text: str, context: str) -> ReviewVerdict:
        text = text.strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for i, line in enumerate(lines):
            upper = line.upper()
            if upper.startswith("APPROVED"):
                return ReviewVerdict(approved=True, reason="", suggestions=[])
            if upper.startswith("REWORK"):
                reason = re.sub(r"(?i)^rework\s*:?\s*", "", line).strip()
                suggestions = [
                    l.lstrip("- ").strip()
                    for l in lines[i+1:]
                    if l.startswith("-")
                ]
                logger.info("[reviewer] REWORK %s: %s (%d suggestions)", context, reason, len(suggestions))
                return ReviewVerdict(approved=False, reason=reason, suggestions=suggestions)

        logger.warning("[reviewer] no clear verdict for %s — defaulting to REWORK", context)
        return ReviewVerdict(
            approved=False,
            reason="Reviewer did not return a clear verdict",
            suggestions=[text[:300]]
        )


def _task_summary(task: dict) -> str:
    return (
        f"File: {task['file']}\n"
        f"Description: {task['description']}\n"
        f"Acceptance criteria:\n" +
        "\n".join(f"  - {c}" for c in task.get("acceptance_criteria", []))
    )
