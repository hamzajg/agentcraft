"""
docs_agent/agent.py — writes markdown documentation files.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import logging
import re
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Docs Agent. Generate clear, concise markdown documentation."""


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
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
        self._retry_count = {}

    def get_step_results(self) -> list[dict]:
        """Return per-step results for reporting to orchestrator."""
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str, timeout: int = 180) -> dict:
        """
        Run a single aider step with auto-retry for non-critical failures.
        """
        MAX_AUTO_RETRIES = 2

        attempt = self._retry_count.get(label, 0) + 1
        self._retry_count[label] = attempt

        logger.info("[docs_agent] step %d: %s", attempt, label)

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
                logger.info("[docs_agent] auto-retrying '%s' (attempt %d/%d, severity=%s)",
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
            logger.info("[docs_agent] step OK: %s", label)
        else:
            logger.warning("[docs_agent] step FAILED [%s]: %s (attempt %d)",
                           result.get("severity", "?"), label, attempt)
        return result

    def _classify_failure(self, result: dict, output_path: Path, label: str) -> dict:
        import re
        exit_code = result.get("exit_code", -1)
        stderr = result.get("stderr", "")
        content = output_path.read_text() if output_path.exists() else ""
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

    def implement(self, task: dict, docs_dir: Path) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._implement_impl(task, docs_dir)
        except Exception:
            logger.exception("[docs_agent] unhandled error in implement")
            result = {"success": False, "file": task.get("file", "unknown"), "error": "unhandled exception"}
        self.report_status("idle")
        return result

    def _implement_impl(self, task: dict, docs_dir: Path) -> dict:
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
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("write doc",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    result["success"] = False
                    return result
                if "skip" in decision:
                    target_file.write_text(f"# {task['file']}\n# Auto-generation skipped.\n")
                    result["success"] = True
                else:
                    escalated = result.get("escalated_message", "") or f"CRITICAL: WRITE the complete {task['file']} documentation with real content."
                    result = self._run_step(escalated, read_files, target_file,
                                            "write doc (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried
        return result

    def generate_phase0_docs(
        self,
        user_input: str,
        docs_dir: Path,
        architecture: str = "monolith",
    ) -> dict[str, Path]:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        docs_dir.mkdir(parents=True, exist_ok=True)
        generated = {}

        try:
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
        except Exception:
            logger.exception("[docs_agent] unhandled error in generate_phase0_docs")
        finally:
            self.report_status("idle")

        logger.info("[docs_agent] Phase 0: generated %d documentation files", len(generated))
        return generated

    def _step_generate_requirements(self, user_input, architecture, output_path):
        """Step 1: Generate requirements.md."""
        _ensure_file(output_path).write_text("")
        label = "generate requirements"
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

        result = self._run_step(prompt, [], output_path, label, timeout=180)

        if not result.get("success"):
            if result.get("needs_user_input"):
                decision = self._ask_user_retry(label,
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    return False
                if "skip" in decision:
                    output_path.write_text("# Requirements\n# Auto-generation skipped.\n")
                    return True
                escalated = result.get("escalated_message", "") or "CRITICAL: Write comprehensive requirements.md with all sections."
                result = self._run_step(escalated, [], output_path, f"{label} (user-retry)", timeout=180)
            elif result.get("auto_retry"):
                pass  # Already auto-retried
        return result.get("success", False) or _file_has_content(output_path)

    def _step_generate_architecture(self, user_input, architecture, output_path, context):
        """Step 2: Generate architecture.md."""
        _ensure_file(output_path).write_text("")
        label = "generate architecture"
        prompt = f"""Write architecture.md for this project.

## User's Vision
{user_input}

## Target Architecture Style
{architecture}

## Task
Create an architecture document with these sections. Let the LLM decide what's appropriate for this project:

### Architecture Style
-Overall pattern
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

        result = self._run_step(prompt, context, output_path, label, timeout=180)

        if not result.get("success"):
            if result.get("needs_user_input"):
                decision = self._ask_user_retry(label,
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    return False
                if "skip" in decision:
                    output_path.write_text("# Architecture\n# Auto-generation skipped.\n")
                    return True
                escalated = result.get("escalated_message", "") or "CRITICAL: Write the complete architecture.md document."
                result = self._run_step(escalated, context, output_path, f"{label} (user-retry)", timeout=180)
            elif result.get("auto_retry"):
                pass  # Already auto-retried
        return result.get("success", False) or _file_has_content(output_path)

    def _step_generate_blueprint(self, user_input, architecture, output_path, context):
        """Step 3: Generate blueprint.md."""
        _ensure_file(output_path).write_text("")
        label = "generate blueprint"
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

        result = self._run_step(prompt, context, output_path, label, timeout=180)

        if not result.get("success"):
            if result.get("needs_user_input"):
                decision = self._ask_user_retry(label,
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    return False
                if "skip" in decision:
                    output_path.write_text("# Blueprint\n# Auto-generation skipped.\n")
                    return True
                escalated = result.get("escalated_message", "") or "CRITICAL: Write the complete blueprint.md document."
                result = self._run_step(escalated, context, output_path, f"{label} (user-retry)", timeout=180)
            elif result.get("auto_retry"):
                pass  # Already auto-retried
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
