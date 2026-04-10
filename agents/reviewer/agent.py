"""
reviewer/agent.py — reads completed task output and decides APPROVED or REWORK.
Follows the same incremental step + user-controlled retry pattern as all agents.
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

    def get_step_results(self) -> list[dict]:
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  label: str, timeout: int = 90) -> dict:
        result = self.run_readonly(message=message, read_files=read_files, timeout=timeout)
        success = result is not None and len(result.strip()) > 0
        self._step_results.append({"label": label, "success": success, "file": ""})
        if not success:
            logger.warning("[reviewer] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
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
        if not output or len(output.strip()) == 0:
            decision = self._ask_user_retry("review task", "reviewer returned no verdict")
            if "abort" in decision:
                return ReviewVerdict(approved=False, reason="Review aborted", suggestions=[])
            if "skip" in decision:
                return ReviewVerdict(approved=True, reason="Auto-approved after skip", suggestions=[])
            output = self._run_step(
                f"CRITICAL: Review the file {task['file']} and respond with APPROVED or REWORK.",
                read_files, "review task (retry)", timeout=90,
            )

        return self._parse_verdict(output or "", task["file"])

    def review_iteration(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> ReviewVerdict:
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
        if not output or len(output.strip()) == 0:
            decision = self._ask_user_retry("review iteration", "reviewer returned no verdict")
            if "abort" in decision:
                return ReviewVerdict(approved=False, reason="Review aborted", suggestions=[])
            if "skip" in decision:
                return ReviewVerdict(approved=True, reason="Auto-approved after skip", suggestions=[])
            output = self._run_step(
                "CRITICAL: Review the iteration and respond with APPROVED or REWORK.",
                read_files, "review iteration (retry)", timeout=90,
            )

        return self._parse_verdict(output or "", f"iteration {iteration['id']}")

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
