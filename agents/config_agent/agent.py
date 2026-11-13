"""
config_agent/agent.py — writes JSON registry files, YAML, .properties, shell scripts.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
import re
from pathlib import Path

from core.base import AiderAgent
from core.failure import StepFailureMixin
from core.files import ensure_file as _ensure_file, file_has_content as _file_has_content

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else "# Config Agent"


class ConfigAgent(StepFailureMixin, AiderAgent):
    _role = "config_agent"

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
            role="config_agent",
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
        """Return per-step results for reporting to orchestrator."""
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str, timeout: int = 120) -> dict:
        """
        Run a single aider step with auto-retry for non-critical failures.
        """
        MAX_AUTO_RETRIES = 2

        attempt = self._retry_count.get(label, 0) + 1
        self._retry_count[label] = attempt

        logger.info("[config_agent] step %d: %s", attempt, label)

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
            result["read_files"] = read_files
            result["timeout"] = timeout

            if classification["auto_retry"] and attempt <= MAX_AUTO_RETRIES:
                logger.info("[config_agent] auto-retrying '%s' (attempt %d/%d, severity=%s)",
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
            logger.info("[config_agent] step OK: %s", label)
        else:
            logger.warning("[config_agent] step FAILED [%s]: %s (attempt %d)",
                           result.get("severity", "?"), label, attempt)
        return result


    def implement(self, task: dict, docs_dir: Path) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._implement_impl(task, docs_dir)
        except Exception:
            logger.exception("[config_agent] unhandled error in implement")
            result = {"success": False, "file": task.get("file", "unknown"), "error": "unhandled exception"}
        self.report_status("idle")
        return result

    def _implement_impl(self, task: dict, docs_dir: Path) -> dict:
        target_file = _ensure_file(self.workspace / task["file"])
        target_file.write_text("")

        context_files = [
            self.workspace / f for f in task.get("context_files", [])
            if (self.workspace / f).exists()
        ]
        read_files = list(docs_dir.glob("*.md")) + context_files

        criteria_list = task.get("acceptance_criteria", [])
        criteria_str = "\n".join(f"- {c}" for c in criteria_list)
        message = (
            f"Create file: {task['file']}\n\n"
            f"Task: {task['description']}\n\n"
            + (f"Must satisfy:\n{criteria_str}\n\n" if criteria_str else "")
            + "Output the complete file only. No explanation."
        )
        logger.info("[config_agent] writing: %s", task["file"])

        result = self._run_step(message, read_files, target_file, "write config", timeout=120)

        if not result.get("success"):
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("write config",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    return result
                if "skip" in decision:
                    target_file.write_text(f"# {task['file']}\n# Auto-generation skipped.\n")
                    result["success"] = True
                else:
                    escalated = result.get("escalated_message", "") or f"CRITICAL: WRITE the complete {task['file']} configuration file with real content."
                    result = self._run_step(escalated, read_files, target_file,
                                            "write config (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried
        return result
