"""
cicd.py — CI/CD and infrastructure agent.

Responsible for infrastructure files when explicitly requested:
  - Containerization (Docker, etc.)
  - CI/CD pipelines
  - Deployment configuration
  - Developer convenience scripts

Runs as a dedicated iteration when infrastructure is requested.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the CI/CD Agent. Set up infrastructure and deployment infrastructure when requested."""


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
    ):
        super().__init__(
            role="cicd",
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

    def build_phase_infra(self, phase: int, docs_dir: Path) -> list[dict]:
        """
        Produce infrastructure files for a completed phase.
        Let the LLM decide what infrastructure is appropriate.
        Returns list of results, one per file written.
        """
        results = []

        # Let the LLM determine what's needed based on the project
        context = self._gather_infrastructure_context(docs_dir)
        results += self._generate_infrastructure(context, docs_dir)

        return results

    def _gather_infrastructure_context(self, docs_dir: Path) -> dict:
        """Gather context about what infrastructure might be needed."""
        read_files = list(docs_dir.glob("*.md"))

        # Check for existing project files
        existing_files = []
        for pattern in ["Makefile", "Dockerfile", "docker-compose.yml", "*.yaml", "*.yml", "package.json", "pom.xml", "Cargo.toml", "go.mod", "requirements.txt"]:
            existing_files.extend(self.workspace.glob(pattern))

        return {
            "read_files": read_files,
            "existing_files": existing_files,
            "workspace": self.workspace,
        }

    def _generate_infrastructure(self, context: dict, docs_dir: Path) -> list[dict]:
        """
        Generate infrastructure files based on project context.
        Let the LLM decide what's appropriate for this project.
        """
        results = []

        read_files = context["read_files"]

        # Ask the LLM to determine what infrastructure is needed
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
        r = self.run(message=message, read_files=read_files, edit_files=[], timeout=120, log_callback=self.log_callback)
        results.append({"output": r.get("output", ""), "file": "infrastructure"})
        return results
