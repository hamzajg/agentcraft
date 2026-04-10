"""
docs_agent/agent.py — writes markdown documentation files.
Follows the same incremental step + user-controlled retry pattern as all agents.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Docs Agent. Generate clear, concise markdown documentation."""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


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
        **kwargs,
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
            **kwargs,
        )
        self._step_results = []

    def get_step_results(self) -> list[dict]:
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str, timeout: int = 180) -> dict:
        result = self.run(
            message=message, read_files=read_files, edit_files=[output_path],
            timeout=timeout, log_callback=self.log_callback,
        )
        success = result.get("success", False) and _file_has_content(output_path)
        self._step_results.append({"label": label, "success": success, "file": str(output_path)})
        if not success:
            logger.warning("[docs_agent] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
        )
        return (reply or "").lower().strip()

    def implement(self, task: dict, docs_dir: Path) -> dict:
        target_file = _ensure_file(self.workspace / task["file"])
        target_file.write_text("")

        context_files = [
            self.workspace / f for f in task.get("context_files", [])
            if (self.workspace / f).exists()
        ]
        read_files = list(docs_dir.glob("*.md")) + context_files

        message = (
            f"Write the following documentation file.\n\n"
            f"File to create: {task['file']}\n\n"
            f"Task description:\n{task['description']}\n\n"
            "Rules:\n"
            "- Clear, concise technical writing. No filler.\n"
            "- Use code blocks for all examples.\n"
            "- Match the style and depth of the source docs.\n"
            "- Include all sections described in the task.\n"
        )
        logger.info("[docs_agent] writing: %s", task["file"])

        result = self._run_step(message, read_files, target_file, "write doc", timeout=120)
        if not result.get("success"):
            decision = self._ask_user_retry("write doc", "aider could not write documentation")
            if "abort" in decision:
                result["success"] = False
                return result
            if "skip" in decision:
                target_file.write_text(f"# {task['file']}\n# Auto-generation skipped.\n")
                result["success"] = True
            else:
                result = self._run_step(
                    f"CRITICAL: Write the complete {task['file']} documentation.",
                    read_files, target_file, "write doc (retry)", timeout=120,
                )
        return result

    def generate_phase0_docs(
        self,
        user_input: str,
        docs_dir: Path,
        architecture: str = "monolith",
    ) -> dict[str, Path]:
        self.report_status("running")
        docs_dir.mkdir(parents=True, exist_ok=True)
        generated = {}

        requirements_path = docs_dir / "requirements.md"
        if self._step_generate_requirements(user_input, architecture, requirements_path):
            generated["requirements"] = requirements_path
            self.emit_file_written(requirements_path)

        architecture_path = docs_dir / "architecture.md"
        ctx = [requirements_path] if "requirements" in generated else []
        if self._step_generate_architecture(user_input, architecture, architecture_path, ctx):
            generated["architecture"] = architecture_path
            self.emit_file_written(architecture_path)

        blueprint_path = docs_dir / "blueprint.md"
        ctx2 = [f for f in [requirements_path, architecture_path] if f in generated.values()]
        if self._step_generate_blueprint(user_input, architecture, blueprint_path, ctx2):
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

    def _step_generate_requirements(self, user_input, architecture, output_path):
        _ensure_file(output_path).write_text("")
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

        result = self._run_step(prompt, [], output_path, "generate requirements", timeout=180)
        if not result.get("success"):
            decision = self._ask_user_retry("generate requirements", "aider could not write requirements")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text("# Requirements\n# Auto-generation skipped.\n")
                return True
            result = self._run_step(
                "CRITICAL: Write comprehensive requirements.md with all sections.",
                [], output_path, "generate requirements (retry)", timeout=180,
            )
        return result.get("success", False) or _file_has_content(output_path)

    def _step_generate_architecture(self, user_input, architecture, output_path, context):
        _ensure_file(output_path).write_text("")
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

        result = self._run_step(prompt, context, output_path, "generate architecture", timeout=180)
        if not result.get("success"):
            decision = self._ask_user_retry("generate architecture", "aider could not write architecture")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text("# Architecture\n# Auto-generation skipped.\n")
                return True
            result = self._run_step(
                "CRITICAL: Write the complete architecture.md document.",
                context, output_path, "generate architecture (retry)", timeout=180,
            )
        return result.get("success", False) or _file_has_content(output_path)

    def _step_generate_blueprint(self, user_input, architecture, output_path, context):
        _ensure_file(output_path).write_text("")
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

**CRITICAL RULES for Project Structure section:**
- Use a simple indented text list (NOT a code block or `tree` command output).
- Use 2-space indentation per level.
- Prefix directories with a trailing `/`.
- Prefix files with NO trailing slash.
- Keep the tree to the top ~20-30 entries — only the most important files/folders.
- Do NOT include every possible file — only the core structure.
- Example format:
```
src/
  main.py
  utils/
    helpers.py
    config.py
tests/
  test_main.py
README.md
```
- Stay focused — do NOT add files or folders that aren't implied by the requirements.

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

        result = self._run_step(prompt, context, output_path, "generate blueprint", timeout=180)
        if not result.get("success"):
            decision = self._ask_user_retry("generate blueprint", "aider could not write blueprint")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text("# Blueprint\n# Auto-generation skipped.\n")
                return True
            result = self._run_step(
                "CRITICAL: Write the complete blueprint.md document.",
                context, output_path, "generate blueprint (retry)", timeout=180,
            )
        return result.get("success", False) or _file_has_content(output_path)

    def generate_reference_docs(self, docs_dir: Path, legacy_paths: list[Path]) -> None:
        docs_dir.mkdir(parents=True, exist_ok=True)

        legacy_files = []
        for path in legacy_paths:
            for ext in ["*.py", "*.java", "*.ts", "*.tsx", "*.js", "*.jsx", "*.go", "*.rs", "*.rb", "*.cs", "*.cpp", "*.c", "*.h", "*.kt", "*.swift", "*.scala", "*.php", "*.sh"]:
                legacy_files.extend(path.rglob(ext))

        if not legacy_files:
            logger.warning("[docs_agent] no legacy source files found")
            return

        logger.info("[docs_agent] analyzing %d legacy source files", len(legacy_files))

        arch_file = docs_dir / "architecture.md"
        _ensure_file(arch_file).write_text("")
        message = (
            f"Analyze the following legacy codebase and create an ARCHITECTURE.MD reference document.\n\n"
            f"Legacy source files to analyze:\n"
            f"{chr(10).join(str(f.relative_to(legacy_paths[0].parent)) for f in legacy_files[:20])}\n"
            f"... and {max(0, len(legacy_files) - 20)} more files\n\n"
            "Create architecture.md that documents:\n"
            "1. **System Architecture**: Current layers, components, and their relationships\n"
            "2. **Data Model**: Key entities, relationships, storage strategy\n"
            "3. **Integration Points**: External services, APIs, dependencies\n"
            "4. **Tech Stack**: Languages, frameworks, libraries in use\n"
            "5. **Design Patterns**: Key patterns observed in the codebase\n"
            "6. **Known Issues**: Technical debt or architectural concerns\n\n"
            "Write as a reference document for the new development team.\n"
            "Keep it concise but complete."
        )
        self._run_step(message, legacy_files[:20], arch_file, "generate arch from legacy", timeout=180)

        domain_file = docs_dir / "domain-model.md"
        _ensure_file(domain_file).write_text("")
        message = (
            "Based on the legacy codebase, create a DOMAIN-MODEL.MD document that describes:\n\n"
            "1. **Core Entities**: Main business objects/entities in the system\n"
            "2. **Value Objects**: Immutable values like Money, Date, Status enums\n"
            "3. **Relationships**: How entities relate to each other\n"
            "4. **Aggregates**: Bounded contexts and aggregate roots\n"
            "5. **Bounded Contexts**: Domain-driven design boundaries\n"
            "6. **Business Rules**: Key invariants and constraints\n"
            "7. **State Machines**: Entity lifecycle and state transitions\n\n"
            "Write this as a reference for new developers to understand the business domain."
        )
        self._run_step(message, legacy_files[:15], domain_file, "generate domain model", timeout=150)

        logger.info("[docs_agent] reference docs generated: %s", docs_dir)
