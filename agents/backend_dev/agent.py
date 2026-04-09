"""
backend_dev.py — writes Java and Spring Boot source files.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Backend Developer Agent. Implement backend code following best practices."""


class BackendDevAgent(AiderAgent):
    _role = "backend_dev"

    def __init__(self, model: str, workspace: Path, system_prompt: str = None, skills: list = None, framework_id: str = None, task_id: str = None, iteration_id: int = None):
        super().__init__(
            role="backend_dev",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT,
            max_retries=3,
        )

    def implement(self, task: dict, docs_dir: Path) -> dict:
        """
        Implement a single file task.
        Aider writes directly to workspace/task['file'].
        Returns the run result dict.
        """
        target_file = self.workspace / task["file"]
        target_file.parent.mkdir(parents=True, exist_ok=True)

        context_files = [
            self.workspace / f
            for f in task.get("context_files", [])
            if (self.workspace / f).exists()
        ]
        read_files = list(docs_dir.glob("*.md")) + context_files

        criteria = "\n".join(f"- {c}" for c in task.get("acceptance_criteria", []))
        message = (
            f"Create file: {task['file']}\n\n"
            f"Task: {task['description']}\n\n"
            + (f"Must satisfy:\n{criteria}\n\n" if criteria else "")
            + "Output the complete file only. No explanation."
        )
        logger.info("[backend_dev] implementing: %s", task["file"])
        return self.run(
            message=message,
            read_files=read_files,
            edit_files=[target_file],
            timeout=150,
            log_callback=self.log_callback,
        )
