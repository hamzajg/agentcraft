"""
config_agent/agent.py — writes JSON registry files, YAML, .properties, shell scripts.
Follows the same incremental step + user-controlled retry pattern as all agents.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Config Agent. Generate configuration files (JSON, YAML, properties)."""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class ConfigAgent(AiderAgent):
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

    def get_step_results(self) -> list[dict]:
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str, timeout: int = 120) -> dict:
        result = self.run(
            message=message, read_files=read_files, edit_files=[output_path],
            timeout=timeout, log_callback=self.log_callback,
        )
        success = result.get("success", False) and _file_has_content(output_path)
        self._step_results.append({"label": label, "success": success, "file": str(output_path)})
        if not success:
            logger.warning("[config_agent] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
        )
        return (reply or "").lower().strip()

    def implement(self, task: dict, docs_dir: Path) -> dict:
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
            decision = self._ask_user_retry("write config", "aider could not write config file")
            if "abort" in decision:
                result["success"] = False
                return result
            if "skip" in decision:
                target_file.write_text(f"# {task['file']}\n# Auto-generation skipped.\n")
                result["success"] = True
            else:
                result = self._run_step(
                    f"CRITICAL: Write the complete {task['file']} configuration file.",
                    read_files, target_file, "write config (retry)", timeout=120,
                )
        return result
