"""
integration_test/agent.py — Integration and E2E test agent.

Runs after all tasks in an iteration are individually approved.
Follows the same incremental step + user-controlled retry pattern as all agents.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Integration Test Agent. Write integration and E2E tests."""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class IntegrationTestAgent(AiderAgent):
    _role = "integration_test"

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
            role="integration_test",
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
            logger.warning("[integration_test] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
        )
        return (reply or "").lower().strip()

    def write_integration_tests(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> list[dict]:
        ai_dir = self.workspace / ".ai"
        spec_file = ai_dir / "spec.md"
        uc_file = ai_dir / "use_cases.md"

        written_files = [
            self.workspace / t["file"]
            for t in tasks
            if (self.workspace / t["file"]).exists()
        ]
        read_files = (
            list(docs_dir.glob("*.md"))
            + written_files
            + ([spec_file] if spec_file.exists() else [])
            + ([uc_file] if uc_file.exists() else [])
        )

        test_file = f"tests/integration/iter_{iteration['id']}_{_snake(iteration['name'])}"
        target = _ensure_file(self.workspace / test_file)
        target.write_text("")

        _iter_id = iteration["id"]
        _iter_name = iteration.get("name", "")
        message = (
            f"Write integration test for iteration {_iter_id}: {_iter_name}.\n\n"
            f"Test file: {test_file}\n\n"
            "Use the appropriate testing framework and approach for this project.\n"
            "Test the integration between components.\n"
            "Output the complete test file only."
        )
        logger.info("[integration_test] writing: %s", test_file)

        result = self._run_step(message, read_files, target, "write integration tests", timeout=120)
        if not result.get("success"):
            decision = self._ask_user_retry("write integration tests", "aider could not write tests")
            if "abort" in decision:
                result["success"] = False
                result["test_file"] = test_file
                return [result]
            if "skip" in decision:
                target.write_text(f"# Integration tests for iteration {_iter_id}\n# Auto-generation skipped.\n")
                result["success"] = True
            else:
                result = self._run_step(
                    f"CRITICAL: Write the complete integration test file for {test_file}.",
                    read_files, target, "write integration tests (retry)", timeout=120,
                )
        result["test_file"] = test_file
        return [result]

    def write_e2e_tests(self, phase: int, docs_dir: Path) -> dict:
        return self._write_e2e(phase, docs_dir)

    def _write_e2e(self, phase: int, docs_dir: Path) -> dict:
        test_file = f"tests/e2e/phase_{phase}"
        target = _ensure_file(self.workspace / test_file)
        target.write_text("")

        ai_dir = self.workspace / ".ai"
        uc_file = ai_dir / "use_cases.md"
        read_files = list(docs_dir.glob("*.md")) + ([uc_file] if uc_file.exists() else [])

        message = (
            f"Write E2E tests for phase {phase}.\n\n"
            f"Test file: {test_file}\n\n"
            "Use the appropriate testing framework and approach for this project.\n"
            "Test the full flow through the system.\n"
            "Output the complete test file only."
        )
        logger.info("[integration_test] writing E2E phase %d: %s", phase, test_file)

        result = self._run_step(message, read_files, target, "write E2E tests", timeout=120)
        if not result.get("success"):
            decision = self._ask_user_retry("write E2E tests", "aider could not write tests")
            if "abort" in decision:
                result["success"] = False
                result["test_file"] = test_file
                return result
            if "skip" in decision:
                target.write_text(f"# E2E tests for phase {phase}\n# Auto-generation skipped.\n")
                result["success"] = True
            else:
                result = self._run_step(
                    f"CRITICAL: Write the complete E2E test file for phase {phase}.",
                    read_files, target, "write E2E tests (retry)", timeout=120,
                )
        result["test_file"] = test_file
        return result


def _snake(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_")
