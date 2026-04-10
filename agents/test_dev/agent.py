"""
test_dev/agent.py — Test developer agent (TDD).

Writes a failing unit or acceptance test BEFORE the implementation exists.
Follows the same incremental step + user-controlled retry pattern as all agents.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Test Developer Agent. Write unit tests following TDD principles."""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class TestDevAgent(AiderAgent):
    _role = "test_dev"

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
            role="test_dev",
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
            logger.warning("[test_dev] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
        )
        return (reply or "").lower().strip()

    def write_unit_test(self, task: dict, docs_dir: Path) -> dict:
        impl_file = task["file"]
        test_file = _impl_to_test_path(impl_file)
        target = _ensure_file(self.workspace / test_file)
        target.write_text("")

        ai_dir = self.workspace / ".ai"
        read_files = list(docs_dir.glob("*.md"))
        for f in [ai_dir / "use_cases.md", ai_dir / "spec.md"]:
            if f.exists():
                read_files.append(f)
        read_files += [self.workspace / f for f in task.get("context_files", []) if (self.workspace / f).exists()]

        criteria = "\n".join(f"- {c}" for c in task.get("acceptance_criteria", []))
        message = (
            f"Write test file: {test_file}\n\n"
            f"Test this: {task['description']}\n\n"
            + (f"Must cover:\n{criteria}\n\n" if criteria else "")
            + "The class under test may not exist yet — that is fine.\n"
            + "Output the complete test file only. No explanation."
        )
        logger.info("[test_dev] writing unit test: %s", test_file)

        result = self._run_step(message, read_files, target, "write unit test", timeout=120)
        if not result.get("success"):
            decision = self._ask_user_retry("write unit test", "aider could not write test")
            if "abort" in decision:
                result["success"] = False
                return result
            if "skip" in decision:
                target.write_text(f"# Unit test for {impl_file}\n# Auto-generation skipped.\n")
                result["success"] = True
            else:
                result = self._run_step(
                    f"CRITICAL: Write the complete test file for {impl_file}. Output only the test code.",
                    read_files, target, "write unit test (retry)", timeout=120,
                )
        result["test_file"] = test_file
        return result

    def write_acceptance_test(self, use_case_id: str, docs_dir: Path, spec_files: list[Path]) -> dict:
        test_file = f"tests/acceptance/{use_case_id.replace('-','_')}_test"
        target = _ensure_file(self.workspace / test_file)
        target.write_text("")
        read_files = list(docs_dir.glob("*.md")) + spec_files

        message = (
            f"Write acceptance test for use case {use_case_id}.\n\n"
            f"File: {test_file}\n\n"
            "Use the appropriate testing framework and approach for this project.\n"
            "Output the complete test file only."
        )
        logger.info("[test_dev] writing acceptance test: %s", test_file)

        result = self._run_step(message, read_files, target, "write acceptance test", timeout=120)
        if not result.get("success"):
            decision = self._ask_user_retry("write acceptance test", "aider could not write test")
            if "abort" in decision:
                result["success"] = False
                return result
            if "skip" in decision:
                target.write_text(f"# Acceptance test for {use_case_id}\n# Auto-generation skipped.\n")
                result["success"] = True
            else:
                result = self._run_step(
                    f"CRITICAL: Write the complete acceptance test for {use_case_id}.",
                    read_files, target, "write acceptance test (retry)", timeout=120,
                )
        result["test_file"] = test_file
        return result


def _impl_to_test_path(impl_file: str) -> str:
    parts = Path(impl_file).parts
    try:
        main_idx = parts.index("main") if "main" in parts else -1
        if main_idx >= 0:
            test_parts = list(parts[:main_idx]) + ["test"] + list(parts[main_idx+1:])
            return str(Path(*test_parts).with_name(Path(parts[-1]).stem + "_test" + Path(parts[-1]).suffix))
    except ValueError:
        pass
    return f"tests/{Path(impl_file).stem}_test{Path(impl_file).suffix}"
