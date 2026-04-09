"""
docs_agent.py — writes markdown documentation files.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Docs Agent. Generate clear, concise markdown documentation."""


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
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or ["technical-writing", "requirements-analysis", "architecture-design"],
            framework_id=framework_id,
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

    def generate_phase0_docs(
        self,
        user_input: str,
        docs_dir: Path,
        architecture: str = "monolith",
    ) -> dict[str, Path]:
        """
        Generate Phase 0 documentation from user input using AI.
        
        Args:
            user_input: Raw user description of what they want to build
            docs_dir: Directory to write docs to
            architecture: Target architecture style (monolith, microservices, etc.)
            
        Returns:
            Dict mapping doc name -> Path of generated files
        """
        self.report_status("running")
        docs_dir.mkdir(parents=True, exist_ok=True)
        generated = {}

        # Step 1: Generate Requirements
        requirements_path = docs_dir / "requirements.md"
        self._generate_requirements(user_input, architecture, requirements_path)
        generated["requirements"] = requirements_path
        self.emit_file_written(requirements_path)

        # Step 2: Generate Architecture
        architecture_path = docs_dir / "architecture.md"
        self._generate_architecture(user_input, architecture, architecture_path, [requirements_path])
        generated["architecture"] = architecture_path
        self.emit_file_written(architecture_path)

        # Step 3: Generate Blueprint
        blueprint_path = docs_dir / "blueprint.md"
        self._generate_blueprint(user_input, architecture, blueprint_path, [requirements_path, architecture_path])
        generated["blueprint"] = blueprint_path
        self.emit_file_written(blueprint_path)

        self.share_context("phase0_docs_generated", {
            "requirements": str(requirements_path),
            "architecture": str(architecture_path),
            "blueprint": str(blueprint_path),
        })

        self.report_status("idle")
        logger.info("[docs_agent] Phase 0: generated %d documentation files", len(generated))
        return generated

    def _generate_requirements(self, user_input: str, architecture: str, output_path: Path) -> None:
        """Generate comprehensive requirements document."""
        logger.info("[docs_agent] generating requirements.md")

        prompt = f"""Write requirements.md for this project.

## User's Vision
{user_input}

## Target Architecture
{architecture}

## Task
Create a comprehensive requirements document with these sections:

### Project Overview
- Problem statement (what pain point does this solve?)
- Target users (who will use this?)
- Core value proposition (why would someone use this?)

### Functional Requirements
For each major feature:
- **FR-###**: The system SHALL [behavior]. Include concrete examples.
- Focus on user-visible behavior, not implementation

### Non-Functional Requirements
- **Performance**: Response times, throughput, resource usage
- **Scalability**: Expected load, growth patterns
- **Reliability**: Availability targets, error handling
- **Security**: Authentication, authorization, data protection
- **Maintainability**: Code standards, documentation needs

### User Stories
Write 3-5 key user stories in format:
As a [user type], I want [goal] so that [benefit].

### Out of Scope
Explicitly state what is NOT included in MVP.

### Constraints
- Technical constraints (languages, frameworks, existing systems)
- Business constraints (budget, timeline, compliance)

Write this for an AI development team. Be precise but concise."""

        self.run(
            message=prompt,
            read_files=[],
            edit_files=[output_path],
            timeout=180,
            log_callback=self.log_callback,
        )

    def _generate_architecture(
        self,
        user_input: str,
        architecture: str,
        output_path: Path,
        context: list[Path],
    ) -> None:
        """Generate architecture document."""
        logger.info("[docs_agent] generating architecture.md")

        prompt = f"""Write architecture.md for this project.

## User's Vision
{user_input}

## Target Architecture Style
{architecture}

## Task
Create an architecture document with these sections. Let the LLM decide what's appropriate for this project:

### Architecture Style
- Overall pattern
- Key characteristics and trade-offs made

### System Components
For each major component (if applicable):
- **Component name**: Responsibility, boundaries
- Dependencies on other components

### Data Architecture
If applicable:
- Data model overview (key entities)
- Storage strategy (databases, caches)
- Data flow between components

### Interface Design (if applicable)
- Interface patterns (API, CLI, library, GUI, etc.)
- Request/response formats or interaction patterns
- Error handling approach

### Technology Stack
- Languages and frameworks
- Key libraries and their purposes
- Development tools

### Design Patterns
- Architectural patterns in use
- Key design decisions and rationale

### Security Architecture
If applicable:
- Authentication approach
- Authorization model
- Data protection measures

Write this for an AI development team. Make it actionable.
Let the LLM decide which sections are relevant and what content to include."""

        self.run(
            message=prompt,
            read_files=context,
            edit_files=[output_path],
            timeout=180,
            log_callback=self.log_callback,
        )

    def _generate_blueprint(
        self,
        user_input: str,
        architecture: str,
        output_path: Path,
        context: list[Path],
    ) -> None:
        """Generate project blueprint document."""
        logger.info("[docs_agent] generating blueprint.md")

        prompt = f"""Write blueprint.md for this project.

## User's Vision
{user_input}

## Task
Create a project blueprint with these sections. Let the LLM decide what phases and structure are appropriate:

### Project Summary
- One paragraph describing the project
- Key success criteria

### Development Phases
Let the LLM decide appropriate phases based on the project complexity:
- Simple projects: 1-2 phases
- Medium projects: 2-3 phases
- Complex projects: 3+ phases

### Project Structure
Recommended directory/file structure for the codebase.

### Key Milestones
- Milestone 1: [What ships in first iteration]
- Milestone 2: [What ships in second iteration]
- Milestone 3: [What ships in final iteration]

### Definition of Done
What constitutes "complete" for each phase:
- Code compiles and passes tests
- Documentation updated
- Review approved

### Risks and Mitigations
- Key technical risks
- Mitigation strategies

This guides the AI agent team's work. Make phases clear and actionable."""

        self.run(
            message=prompt,
            read_files=context,
            edit_files=[output_path],
            timeout=180,
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
        source_extensions = [
            "*.py", "*.java", "*.ts", "*.tsx", "*.js", "*.jsx",
            "*.go", "*.rs", "*.rb", "*.cs", "*.cpp", "*.c", "*.h",
            "*.kt", "*.swift", "*.scala", "*.php", "*.sh",
        ]
        for path in legacy_paths:
            for ext in source_extensions:
                legacy_files.extend(path.rglob(ext))
        
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
            read_files=legacy_files[:20],
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
