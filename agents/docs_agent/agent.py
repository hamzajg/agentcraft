"""
docs_agent.py — writes markdown documentation files.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


class DocsAgent(AiderAgent):
    _role = "docs_agent"

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
            role="docs_agent",
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

    def implement(self, task: dict, docs_dir: Path) -> dict:
        target_file = self.workspace / task["file"]
        target_file.parent.mkdir(parents=True, exist_ok=True)

        context_files = [
            self.workspace / f
            for f in task.get("context_files", [])
            if (self.workspace / f).exists()
        ]
        read_files = list(docs_dir.glob("*.md")) + context_files

        message = f"""
Write the following documentation file.

File to create: {task['file']}

Task description:
{task['description']}

Rules:
- Clear, concise technical writing. No filler.
- Use code blocks for all examples.
- Match the style and depth of the source docs.
- Include all sections described in the task.
"""
        logger.info("[docs_agent] writing: %s", task["file"])
        return self.run(
            message=message,
            read_files=read_files,
            edit_files=[target_file],
            timeout=120,
            log_callback=self.log_callback,
        )

    def generate_reference_docs(self, docs_dir: Path, legacy_paths: list[Path]) -> None:
        """
        Generate reference documentation from legacy codebase.
        Creates architecture.md, domain-model.md, and api-design.md.
        """
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Collect legacy source files
        legacy_files = []
        for path in legacy_paths:
            legacy_files.extend(path.rglob("*.py"))
            legacy_files.extend(path.rglob("*.java"))
            legacy_files.extend(path.rglob("*.ts"))
            legacy_files.extend(path.rglob("*.js"))
        
        if not legacy_files:
            logger.warning("[docs_agent] no legacy source files found")
            return
        
        logger.info("[docs_agent] analyzing %d legacy source files", len(legacy_files))
        
        # Generate architecture reference from legacy code
        arch_file = docs_dir / "architecture.md"
        message = f"""
Analyze the following legacy codebase and create an ARCHITECTURE.MD reference document.

Legacy source files to analyze:
{chr(10).join(str(f.relative_to(legacy_paths[0].parent)) for f in legacy_files[:20])}
... and {max(0, len(legacy_files) - 20)} more files

Create architecture.md that documents:
1. **System Architecture**: Current layers, components, and their relationships
2. **Data Model**: Key entities, relationships, storage strategy
3. **Integration Points**: External services, APIs, dependencies
4. **Tech Stack**: Languages, frameworks, libraries in use
5. **Design Patterns**: Key patterns observed in the codebase
6. **Known Issues**: Technical debt or architectural concerns

Write as a reference document for the new development team.
Keep it concise but complete.
"""
        self.run(
            message=message,
            read_files=legacy_files[:20],  # Show first 20 files as examples
            edit_files=[arch_file],
            timeout=180,
            log_callback=self.log_callback,
        )
        
        # Generate domain model reference
        domain_file = docs_dir / "domain-model.md"
        message = """
Based on the legacy codebase, create a DOMAIN-MODEL.MD document that describes:

1. **Core Entities**: Main business objects/entities in the system
2. **Value Objects**: Immutable values like Money, Date, Status enums
3. **Relationships**: How entities relate to each other
4. **Aggregates**: Bounded contexts and aggregate roots
5. **Bounded Contexts**: Domain-driven design boundaries
6. **Business Rules**: Key invariants and constraints
7. **State Machines**: Entity lifecycle and state transitions

Write this as a reference for new developers to understand the business domain.
"""
        self.run(
            message=message,
            read_files=legacy_files[:15],
            edit_files=[domain_file],
            timeout=150,
            log_callback=self.log_callback,
        )
        
        logger.info("[docs_agent] reference docs generated: %s", docs_dir)
