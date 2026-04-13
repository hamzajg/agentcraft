"""
test_dev/agent.py — Test developer agent (TDD).

Writes a failing unit or acceptance test BEFORE the implementation exists.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
import re
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Test Developer Agent. Write unit tests following TDD principles."""


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
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

        logger.info("[test_dev] step %d: %s", attempt, label)

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
                logger.info("[test_dev] auto-retrying '%s' (attempt %d/%d, severity=%s)",
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
            logger.info("[test_dev] step OK: %s", label)
        else:
            logger.warning("[test_dev] step FAILED [%s]: %s (attempt %d)",
                           result.get("severity", "?"), label, attempt)
        return result

    def _classify_failure(self, result: dict, output_path: Path, label: str) -> dict:
        import re
        exit_code = result.get("exit_code", -1)
        stderr = result.get("stderr", "")
        # Skip reading if path is a directory or doesn't exist
        content = ""
        if output_path.exists() and output_path.is_file():
            content = output_path.read_text()
        if exit_code != 0 and (exit_code == -1 or "timeout" in stderr.lower() or exit_code >= 128):
            return {"severity": "transient", "auto_retry": True, "needs_user_input": False, "escalated_message": ""}
        if _file_has_content(output_path) and self._looks_like_hallucination(content):
            return {"severity": "hallucination", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}
        if exit_code == 0 and not _file_has_content(output_path):
            return {"severity": "refusal", "auto_retry": True, "needs_user_input": False,
                    "escalated_message": "CRITICAL: You MUST write the complete file content. No placeholders or stubs."}
        return {"severity": "critical", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}

    def _looks_like_hallucination(self, content: str) -> bool:
        import re
        if not content or len(content.strip()) < 20:
            return True
        lines = content.splitlines()
        placeholder_patterns = [r"TODO", r"placeholder", r"stub", r"fill.*in", r"coming soon",
                                r"auto-generat", r"skipped", r"incomplete", r"not (yet|currently) (implemented|available|generated)", r"_.*_"]
        placeholder_lines = sum(1 for line in lines for p in placeholder_patterns if re.search(p, line, re.IGNORECASE))
        if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
            return True
        if len(content.strip()) < 100:
            return True
        if all(line.startswith("#") or line.startswith("//") or line.strip() == "" for line in lines):
            return True
        return False

    def _ask_user_retry(self, step_label: str, error_detail: str, severity: str) -> str:
        """Ask user what to do after a critical or hallucination failure."""
        severity_label = severity.upper()
        reply = self.ask(
            question=f"Step '{step_label}' failed [{severity_label}]: {error_detail}. What should I do?",
            suggestions=[
                "Retry with more explicit instructions",
                "Skip this step and continue",
                "Abort — I'll fix this manually",
            ],
            timeout=600,
        )
        return (reply or "").lower().strip()

    def write_unit_test(self, task: dict, docs_dir: Path) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._write_unit_test_impl(task, docs_dir)
        except Exception:
            logger.exception("[test_dev] unhandled error in write_unit_test")
            impl_file = task.get("file", "unknown")
            result = {"success": False, "test_file": impl_file, "error": "unhandled exception"}
        self.report_status("idle")
        return result

    def _write_unit_test_impl(self, task: dict, docs_dir: Path) -> dict:
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
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("write unit test",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    result["test_file"] = test_file
                    return result
                if "skip" in decision:
                    target.write_text(f"# Unit test for {impl_file}\n# Auto-generation skipped.\n")
                    result["success"] = True
                else:
                    escalated = result.get("escalated_message", "") or f"CRITICAL: Write the complete test file for {impl_file}. Output only the test code."
                    result = self._run_step(escalated, read_files, target,
                                            "write unit test (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried

        result["test_file"] = test_file
        return result

    def write_acceptance_test(self, use_case_id: str, docs_dir: Path, spec_files: list[Path]) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._write_acceptance_test_impl(use_case_id, docs_dir, spec_files)
        except Exception:
            logger.exception("[test_dev] unhandled error in write_acceptance_test")
            result = {"success": False, "test_file": f"tests/acceptance/{use_case_id}", "error": "unhandled exception"}
        self.report_status("idle")
        return result

    def _write_acceptance_test_impl(self, use_case_id: str, docs_dir: Path, spec_files: list[Path]) -> dict:
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
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("write acceptance test",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    result["test_file"] = test_file
                    return result
                if "skip" in decision:
                    target.write_text(f"# Acceptance test for {use_case_id}\n# Auto-generation skipped.\n")
                    result["success"] = True
                else:
                    escalated = result.get("escalated_message", "") or f"CRITICAL: Write the complete acceptance test for {use_case_id}."
                    result = self._run_step(escalated, read_files, target,
                                            "write acceptance test (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried

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
