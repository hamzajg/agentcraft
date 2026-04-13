"""
cicd/agent.py — CI/CD and infrastructure agent.

Responsible for infrastructure files when explicitly requested.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
import re
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else "# CI/CD Agent"


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
    return path.exists() and path.stat().st_size > 0


class CiCdAgent(AiderAgent):
    _role = "cicd"

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
            role="cicd",
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
                  output_path: Path = None, label: str = None, timeout: int = 120) -> dict:
        """
        Run a single aider step with auto-retry for non-critical failures.
        """
        MAX_AUTO_RETRIES = 2

        attempt = self._retry_count.get(label, 0) + 1 if label else 1
        if label:
            self._retry_count[label] = attempt

        logger.info("[cicd] step %d: %s", attempt, label or "unknown")

        kwargs = {"message": message, "read_files": read_files, "timeout": timeout, "log_callback": self.log_callback}
        if output_path:
            kwargs["edit_files"] = [output_path]
        result = self.run(**kwargs)

        success = result.get("success", False)
        if output_path:
            success = success and _file_has_content(output_path)

        if not success and label:
            classification = self._classify_failure(result, output_path or Path(""), label)
            result["severity"] = classification["severity"]
            result["auto_retry"] = classification["auto_retry"]
            result["needs_user_input"] = classification["needs_user_input"]
            result["retry_count"] = attempt
            result["escalated_message"] = classification.get("escalated_message", "")
            result["read_files"] = read_files
            result["timeout"] = timeout

            if classification["auto_retry"] and attempt <= MAX_AUTO_RETRIES:
                logger.info("[cicd] auto-retrying '%s' (attempt %d/%d, severity=%s)",
                            label, attempt + 1, MAX_AUTO_RETRIES + 1, classification["severity"])
                retry_msg = classification.get("escalated_message") or message
                return self._run_step(retry_msg, read_files, output_path, label, timeout)

            if classification["needs_user_input"]:
                result["needs_user_input"] = True
        elif label:
            result["severity"] = "success"
            result["auto_retry"] = False
            result["needs_user_input"] = False
            result["retry_count"] = attempt

        if label:
            self._step_results.append({
                "label": label, "success": success, "file": str(output_path) if output_path else "",
                "exit_code": result.get("exit_code", -1), "severity": result.get("severity", "?"),
                "attempt": attempt,
            })
            if success:
                logger.info("[cicd] step OK: %s", label)
            else:
                logger.warning("[cicd] step FAILED [%s]: %s (attempt %d)",
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
                                r"auto-generat", r"skipped\b", r"incomplete\b", r"not (yet|currently) (implemented|available|generated)"]
        placeholder_lines = sum(1 for line in lines for p in placeholder_patterns if re.search(p, line, re.IGNORECASE))
        if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
            return True
        if len(content.strip()) < 100:
            return True
        if all(line.lstrip().startswith(("#", "//", "/*", "*", "*/")) or line.strip() == "" for line in lines if line.strip()):
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

    def build_phase_infra(self, phase: int, docs_dir: Path) -> list[dict]:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            results = self._build_phase_infra_impl(phase, docs_dir)
        except Exception:
            logger.exception("[cicd] unhandled error in build_phase_infra")
            results = [{"success": False, "error": "unhandled exception"}]
        self.report_status("idle")
        return results

    def _build_phase_infra_impl(self, phase: int, docs_dir: Path) -> list[dict]:
        results = []
        context = self._gather_infrastructure_context(docs_dir)
        results += self._generate_infrastructure(context, docs_dir)
        return results

    def _gather_infrastructure_context(self, docs_dir: Path) -> dict:
        read_files = list(docs_dir.glob("*.md"))
        existing_files = []
        for pattern in ["Makefile", "Dockerfile", "docker-compose.yml", "*.yaml", "*.yml", "package.json", "pom.xml", "Cargo.toml", "go.mod", "requirements.txt"]:
            existing_files.extend(self.workspace.glob(pattern))
        return {"read_files": read_files, "existing_files": existing_files, "workspace": self.workspace}

    def _generate_infrastructure(self, context: dict, docs_dir: Path) -> list[dict]:
        results = []
        read_files = context["read_files"]

        message = """
Based on the project context, determine what infrastructure files are needed.

Consider:
- Does the project need a build script/Makefile?
- Does the project need containerization (Docker)?
- Does the project need CI/CD pipeline configuration?
- Does the project need deployment configuration?

If infrastructure is needed, generate the appropriate files.
If no infrastructure is needed, return an empty result.

Output files to workspace as appropriate for the project type.
"""
        logger.info("[cicd] determining infrastructure needs")
        result = self._run_step(message, read_files, label="determine infrastructure needs", timeout=120)
        results.append({"output": result.get("output", ""), "file": "infrastructure"})
        return results
