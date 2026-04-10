"""
backend_dev/agent.py — Backend Developer agent.

Responsible for implementing source code files.
Reads spec/docs and task description, writes code to workspace.

Design principles:
  - Small incremental steps — each step is one focused aider call
  - NO automatic retries — failures are reported, user decides
  - Clear step reporting with progress
  - User-controlled retry via clarification system
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    (Path(__file__).parent / "prompt.md").read_text()
    if (Path(__file__).parent / "prompt.md").exists()
    else "You are the Backend Developer Agent. Implement backend code following best practices."
)


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
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
            skills=skills,
            framework_id=framework_id,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
            **kwargs,
        )
        self._step_results = []

    # ── Public entry point (called by orchestrator) ───────────────────────

    def implement(self, task: dict, docs_dir: Path) -> dict:
        """
        Implement a single file task.

        Args:
            task: Task dict with 'file', 'description', 'acceptance_criteria', 'context_files'.
            docs_dir: Directory containing specification/docs.

        Returns:
            Result dict with 'success', 'stdout', 'stderr', 'exit_code'.
        """
        self.report_status("running")
        self._step_results = []

        target_file = self.workspace / task["file"]
        _ensure_file(target_file)

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
            + "Output the complete file content. No explanation."
        )

        logger.info("[backend_dev] implementing: %s", task["file"])

        result = self._run_step(
            message=message,
            read_files=read_files,
            output_path=target_file,
            label=f"implement {task['file']}",
            timeout=150,
        )

        if not result.get("success"):
            decision = self._ask_user_retry(
                f"implement {task['file']}",
                "aider could not generate the file",
            )
            if "abort" in decision:
                self.report_status("idle")
                return {"success": False, "stdout": "", "stderr": "aborted by user", "exit_code": -1}
            if "skip" in decision:
                target_file.write_text(f"# {task['file']}\n# Auto-generation skipped — stub file\n")
                self.emit_file_written(target_file)
                self.report_status("idle")
                return {"success": True, "stdout": "stub created", "stderr": "", "exit_code": 0}
            # "retry" — exactly one more attempt
            result = self._run_step(
                message=(
                    f"CRITICAL: Create the file {task['file']} with complete implementation.\n\n"
                    f"Task: {task['description']}\n\n"
                    + (f"Must satisfy:\n{criteria}\n\n" if criteria else "")
                    + "You MUST produce actual working code — no placeholders or stubs."
                ),
                read_files=read_files,
                output_path=target_file,
                label=f"implement {task['file']} (retry)",
                timeout=150,
            )
            if not result.get("success") and not _file_has_content(target_file):
                target_file.write_text(f"# {task['file']}\n# Retry also failed — stub file\n")
                self.emit_file_written(target_file)

        self.report_status("idle")
        return result

    def get_step_results(self) -> list[dict]:
        """Return per-step results for reporting to user/orchestrator."""
        return list(self._step_results)

    # ── Step runner: single-shot, no auto-retry ──────────────────────────

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str,
                  timeout: int = 180) -> dict:
        """Run a single aider step. NO automatic retry. Returns result dict."""
        logger.info("[backend_dev] step: %s", label)

        result = self.run(
            message=message,
            read_files=read_files,
            edit_files=[output_path],
            timeout=timeout,
            log_callback=self.log_callback,
        )

        success = result.get("success", False) and _file_has_content(output_path)
        step_info = {
            "label": label,
            "success": success,
            "file": str(output_path),
            "exit_code": result.get("exit_code", -1),
        }
        self._step_results.append(step_info)

        if not success:
            logger.warning("[backend_dev] step FAILED: %s (exit=%s)",
                           label, result.get("exit_code", "?"))
        else:
            logger.info("[backend_dev] step OK: %s", label)

        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        """Ask user what to do after a step failure."""
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=[
                "Retry this step",
                "Skip this step and create a stub",
                "Abort",
            ],
            timeout=300,
        )
        return (reply or "").lower().strip()
