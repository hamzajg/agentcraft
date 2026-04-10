"""
backend_dev/agent.py — writes source code files.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Backend Developer Agent. Implement backend code following best practices."""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class BackendDevAgent(AiderAgent):
    _role = "backend_dev"

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
            role="backend_dev",
            model=model,
            workspace=workspace,
            system_prompt=system_prompt or SYSTEM_PROMPT,
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
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str, timeout: int = 150) -> dict:
        MAX_AUTO_RETRIES = 2
        attempt = self._retry_count.get(label, 0) + 1
        self._retry_count[label] = attempt
        logger.info("[backend_dev] step %d: %s", attempt, label)

        result = self.run(
            message=message, read_files=read_files, edit_files=[output_path],
            timeout=timeout, log_callback=self.log_callback,
        )
        success = result.get("success", False) and _file_has_content(output_path)

        if not success:
            classification = self._classify_failure(result, output_path, label)
            result["severity"] = classification["severity"]
            result["auto_retry"] = classification["auto_retry"]
            result["needs_user_input"] = classification["needs_user_input"]
            result["retry_count"] = attempt
            result["escalated_message"] = classification.get("escalated_message", "")

            if classification["auto_retry"] and attempt <= MAX_AUTO_RETRIES:
                logger.info("[backend_dev] auto-retry '%s' (%d/%d, %s)",
                            label, attempt + 1, MAX_AUTO_RETRIES + 1, classification["severity"])
                retry_msg = classification.get("escalated_message") or message
                return self._run_step(retry_msg, read_files, output_path, label, timeout)

            if classification["needs_user_input"]:
                result["needs_user_input"] = True
        else:
            result["severity"] = "success"
            result["auto_retry"] = False
            result["needs_user_input"] = False
            result["retry_count"] = attempt

        self._step_results.append({
            "label": label, "success": success, "file": str(output_path),
            "exit_code": result.get("exit_code", -1), "severity": result.get("severity", "?"),
            "attempt": attempt,
        })
        if success:
            logger.info("[backend_dev] step OK: %s", label)
        else:
            logger.warning("[backend_dev] step FAILED [%s]: %s (attempt %d)",
                           result.get("severity", "?"), label, attempt)
        return result

    def _classify_failure(self, result: dict, output_path: Path, label: str) -> dict:
        exit_code = result.get("exit_code", -1)
        stderr = result.get("stderr", "")
        content = output_path.read_text() if output_path.exists() else ""

        # Transient (crash, timeout)
        if exit_code != 0 and (exit_code == -1 or "timeout" in stderr.lower() or exit_code >= 128):
            return {"severity": "transient", "auto_retry": True, "needs_user_input": False, "escalated_message": ""}

        # Hallucination
        if _file_has_content(output_path) and self._looks_like_hallucination(content):
            return {"severity": "hallucination", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}

        # Refusal
        if exit_code == 0 and not _file_has_content(output_path):
            return {
                "severity": "refusal", "auto_retry": True, "needs_user_input": False,
                "escalated_message": "CRITICAL: You MUST write the complete file content. No placeholders or stubs.",
            }

        # Critical
        return {"severity": "critical", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}

    def _looks_like_hallucination(self, content: str) -> bool:
        if not content or len(content.strip()) < 20:
            return True
        lines = content.splitlines()
        placeholder_patterns = [r"TODO", r"placeholder", r"stub", r"fill.*in", r"coming soon",
                                r"auto-generat", r"skipped", r"incomplete", r"not (yet|currently) (implemented|available|generated)",
                                r"_.*_"]
        placeholder_lines = sum(1 for line in lines for p in placeholder_patterns if __import__("re").search(p, line, __import__("re").IGNORECASE))
        if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
            return True
        if len(content.strip()) < 100:
            return True
        if all(line.startswith("#") or line.startswith("//") or line.strip() == "" for line in lines):
            return True
        return False

    def implement(self, task: dict, docs_dir: Path) -> dict:
        target_file = _ensure_file(self.workspace / task["file"])
        target_file.write_text("")

        context_files = [self.workspace / f for f in task.get("context_files", []) if (self.workspace / f).exists()]
        read_files = list(docs_dir.glob("*.md")) + context_files

        criteria = "\n".join(f"- {c}" for c in task.get("acceptance_criteria", []))
        message = (
            f"Create file: {task['file']}\n\n"
            f"Task: {task['description']}\n\n"
            + (f"Must satisfy:\n{criteria}\n\n" if criteria else "")
            + "Output the complete file only. No explanation."
        )
        logger.info("[backend_dev] implementing: %s", task["file"])
        result = self._run_step(message, read_files, target_file, f"implement {task['file']}", timeout=150)

        if not result.get("success"):
            if result.get("needs_user_input"):
                decision = self._ask_user_retry(f"implement {task['file']}",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    return result
                if "skip" in decision:
                    target_file.write_text(f"# {task['file']}\n// Auto-generation skipped.\n")
                    result["success"] = True
            elif result.get("auto_retry"):
                pass  # Already auto-retried
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str, severity: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed [{severity.upper()}]: {error_detail}. What should I do?",
            suggestions=["Retry with more explicit instructions", "Skip this step", "Abort — I'll fix manually"],
            timeout=600,
        )
        return (reply or "").lower().strip()
