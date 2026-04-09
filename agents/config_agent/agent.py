"""
config_agent.py — writes JSON registry files, YAML, .properties, shell scripts.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Config Agent. Generate configuration files (JSON, YAML, properties)."""


class ConfigAgent(AiderAgent):
    _role = "config_agent"

    def __init__(self, model: str, workspace: Path, system_prompt: str = None, skills: list = None, framework_id: str = None, task_id: str = None, iteration_id: int = None):
        super().__init__(
            role="config_agent",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT,
            max_retries=2,
        )

    def implement(self, task: dict, docs_dir: Path) -> dict:
        target_file = self.workspace / task["file"]
        target_file.parent.mkdir(parents=True, exist_ok=True)

        context_files = [
            self.workspace / f
            for f in task.get("context_files", [])
            if (self.workspace / f).exists()
        ]
        read_files = list(docs_dir.glob("*.md")) + context_files

        criteria = "\n".join(f"- {c}" for c in task.get("acceptance_criteria", []))
        file_path = task['file']
        desc = task['description']
        criteria_list = task.get('acceptance_criteria', [])
        criteria_str = chr(10).join(f'- {c}' for c in criteria_list)
        message = f'Create file: {file_path}\n\nTask: {desc}\n\n'
        if criteria_str:
            message += f'Must satisfy:\n{criteria_str}\n\n'
        message += 'Output the complete file only. No explanation.'
        logger.info("[config_agent] writing: %s", task["file"])
        return self.run(
            message=message,
            read_files=read_files,
            edit_files=[target_file],
            timeout=120,
            log_callback=self.log_callback,
        )
