"""
cicd/agent.py — CI/CD and infrastructure agent.

Responsible for infrastructure files when explicitly requested.
Follows the same incremental step + user-controlled retry pattern as all agents.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the CI/CD Agent. Set up infrastructure and deployment infrastructure when requested."""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
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

    def get_step_results(self) -> list[dict]:
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path = None, label: str = None, timeout: int = 120) -> dict:
        kwargs = {"message": message, "read_files": read_files, "timeout": timeout, "log_callback": self.log_callback}
        if output_path:
            kwargs["edit_files"] = [output_path]
        result = self.run(**kwargs)
        if label:
            success = result.get("success", False)
            if output_path:
                success = success and _file_has_content(output_path)
            self._step_results.append({"label": label, "success": success, "file": str(output_path) if output_path else ""})
            if not success:
                logger.warning("[cicd] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
        )
        return (reply or "").lower().strip()

    def build_phase_infra(self, phase: int, docs_dir: Path) -> list[dict]:
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

        # Step 1: Determine what's needed
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
