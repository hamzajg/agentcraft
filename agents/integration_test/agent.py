"""
integration_test/agent.py — Integration and E2E test agent.

Runs after all tasks in an iteration are individually approved.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
import re
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Integration Test Agent. Write integration and E2E tests."""


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
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

        logger.info("[integration_test] step %d: %s", attempt, label)

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
                logger.info("[integration_test] auto-retrying '%s' (attempt %d/%d, severity=%s)",
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
            logger.info("[integration_test] step OK: %s", label)
        else:
            logger.warning("[integration_test] step FAILED [%s]: %s (attempt %d)",
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

    def write_integration_tests(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> list[dict]:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._write_integration_tests_impl(iteration, tasks, docs_dir)
        except Exception:
            logger.exception("[integration_test] unhandled error in write_integration_tests")
            result = [{"success": False, "test_file": f"tests/integration/iter_{iteration.get('id', 'unknown')}", "error": "unhandled exception"}]
        self.report_status("idle")
        return result

    def _write_integration_tests_impl(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> list[dict]:
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
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("write integration tests",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    result["test_file"] = test_file
                    return [result]
                if "skip" in decision:
                    target.write_text(f"# Integration tests for iteration {_iter_id}\n# Auto-generation skipped.\n")
                    result["success"] = True
                else:
                    escalated = result.get("escalated_message", "") or f"CRITICAL: Write the complete integration test file for {test_file}."
                    result = self._run_step(escalated, read_files, target,
                                            "write integration tests (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried

        result["test_file"] = test_file
        return [result]

    def write_e2e_tests(self, phase: int, docs_dir: Path) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._write_e2e(phase, docs_dir)
        except Exception:
            logger.exception("[integration_test] unhandled error in write_e2e_tests")
            result = {"success": False, "test_file": f"tests/e2e/phase_{phase}", "error": "unhandled exception"}
        self.report_status("idle")
        return result

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
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("write E2E tests",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    result["test_file"] = test_file
                    return result
                if "skip" in decision:
                    target.write_text(f"# E2E tests for phase {phase}\n# Auto-generation skipped.\n")
                    result["success"] = True
                else:
                    escalated = result.get("escalated_message", "") or f"CRITICAL: Write the complete E2E test file for phase {phase}."
                    result = self._run_step(escalated, read_files, target,
                                            "write E2E tests (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried

        result["test_file"] = test_file
        return result


def _snake(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_")
