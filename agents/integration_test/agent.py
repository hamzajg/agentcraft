"""
integration_test.py — Integration and E2E test agent.

Runs after all tasks in an iteration are individually approved.
Writes tests that cross component boundaries:
  - Integration tests: two or more real components wired together
  - E2E tests: full call through the stack (mocking only external I/O)

Let the LLM decide the appropriate testing approach based on the project type.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Integration Test Agent. Write integration and E2E tests."""


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
    ):
        super().__init__(
            role="integration_test",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills,
            framework_id=framework_id,
            max_retries=2,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def write_integration_tests(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> list[dict]:
        """
        Write integration tests covering the interactions between
        components produced in this iteration.

        Let the LLM decide the appropriate testing approach.
        Returns list of result dicts (one per test file written).
        """
        ai_dir    = self.workspace / ".ai"
        spec_file = ai_dir / "spec.md"
        uc_file   = ai_dir / "use_cases.md"

        written_files = [
            self.workspace / t["file"]
            for t in tasks
            if (self.workspace / t["file"]).exists()
        ]
        read_files = (
            list(docs_dir.glob("*.md"))
            + written_files
            + ([spec_file] if spec_file.exists() else [])
            + ([uc_file]   if uc_file.exists()   else [])
        )

        # Let the LLM determine the appropriate test structure
        test_file = f"tests/integration/iter_{iteration['id']}_{_snake(iteration['name'])}"
        target = self.workspace / test_file
        target.parent.mkdir(parents=True, exist_ok=True)

        impl_files_list = "\n".join(f"- {t['file']}" for t in tasks if t["agent"] == "backend_dev")

        _iter_id   = iteration["id"]
        _iter_name = iteration.get("name", "")
        message = (
            f"Write integration test for iteration {_iter_id}: {_iter_name}.\n\n"
            f"Test file: {test_file}\n\n"
            "Use the appropriate testing framework and approach for this project.\n"
            "Test the integration between components.\n"
            "Output the complete test file only."
        )
        logger.info("[integration_test] writing: %s", test_file)
        result = self.run(
            message=message,
            read_files=read_files,
            edit_files=[target],
            timeout=120,
            log_callback=self.log_callback,
        )
        result["test_file"] = test_file
        return [result]

    def write_e2e_tests(self, phase: int, docs_dir: Path) -> dict:
        """
        Write E2E tests for a completed phase.
        Let the LLM decide the appropriate testing approach based on the project type.
        """
        return self._write_e2e(phase, docs_dir)

    def _write_e2e(self, phase: int, docs_dir: Path) -> dict:
        """E2E tests for the phase - let the LLM decide the approach."""
        test_file = f"tests/e2e/phase_{phase}"
        target    = self.workspace / test_file
        target.parent.mkdir(parents=True, exist_ok=True)

        ai_dir  = self.workspace / ".ai"
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
        result = self.run(
            message=message,
            read_files=read_files,
            edit_files=[target],
            timeout=120,
            log_callback=self.log_callback,
        )
        result["test_file"] = test_file
        return result


def _snake(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_")

def _pascal(name: str) -> str:
    return "".join(w.capitalize() for w in name.split())
