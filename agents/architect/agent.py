"""
architect/agent.py — Architect agent.

ROLE: Context gatherer for architecture planning.
Follows the same smart failure classification + auto-retry pattern as all agents.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Architect Agent.

Your role is to analyze requirements and design appropriate system architecture.
"""


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
    return path.exists() and path.stat().st_size > 0


class ArchitectAgent(AiderAgent):
    _role = "architect"

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
            role="architect",
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

    def _run_step(self, message: str, read_files: list[Path] = None,
                  output_path: Path = None, label: str = None, timeout: int = 180) -> dict:
        """
        Run a single aider step with auto-retry for non-critical failures.
        """
        MAX_AUTO_RETRIES = 2

        attempt = self._retry_count.get(label, 0) + 1 if label else 1
        if label:
            self._retry_count[label] = attempt

        logger.info("[architect] step %d: %s", attempt, label or "unknown")

        kwargs = {"message": message, "timeout": timeout, "log_callback": self.log_callback}
        if read_files:
            kwargs["read_files"] = read_files
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
                logger.info("[architect] auto-retrying '%s' (attempt %d/%d, severity=%s)",
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
                logger.info("[architect] step OK: %s", label)
            else:
                logger.warning("[architect] step FAILED [%s]: %s (attempt %d)",
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

    def _log(self, message: str):
        if self.log_callback:
            try:
                self.log_callback(self.role, message)
            except Exception:
                pass
        logger.info("[architect] %s", message)

    def gather_context(self) -> dict:
        return {
            "workspace": self._read_workspace_config(),
            "requirements": self._read_requirements(),
            "existing_docs": self._read_existing_docs(),
            "architecture_style": self._determine_architecture_style(),
        }

    def _read_workspace_config(self) -> dict:
        workspace_yaml = self.workspace / "workspace.yaml"
        if not workspace_yaml.exists():
            workspace_yaml = self.workspace.parent / "workspace.yaml"
        if workspace_yaml.exists():
            try:
                import yaml
                return yaml.safe_load(workspace_yaml.read_text()) or {}
            except Exception as e:
                logger.warning("[architect] Failed to read workspace.yaml: %s", e)
        return {}

    def _read_requirements(self) -> str:
        docs_dir = self.workspace / "docs"
        requirements = []
        for md_file in [docs_dir / "requirements.md"] if (docs_dir / "requirements.md").exists() else []:
            requirements.append(f"## {md_file.name}\n{md_file.read_text()[:2000]}")
        for md_file in [docs_dir / "blueprint.md"] if (docs_dir / "blueprint.md").exists() else []:
            requirements.append(f"## {md_file.name}\n{md_file.read_text()[:1000]}")
        return "\n\n".join(requirements) if requirements else "No requirements found."

    def _read_existing_docs(self) -> dict:
        docs_dir = self.workspace / "docs"
        ai_dir = self.workspace / ".ai"
        docs = {}
        for md_file in list(docs_dir.glob("*.md")) + list(ai_dir.glob("*.md")):
            docs[md_file.name] = md_file.read_text()[:1500]
        return docs

    def _determine_architecture_style(self) -> str:
        workspace = self._read_workspace_config()
        return workspace.get("project", {}).get("architecture", "monolith")

    def design_architecture(self, requirements: str) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._design_architecture_impl(requirements)
        except Exception:
            logger.exception("[architect] unhandled error in design_architecture")
            result = {"architecture": "", "style": "monolith", "error": "unhandled exception"}
        self.report_status("idle")
        return result

    def _design_architecture_impl(self, requirements: str) -> dict:
        self._log("Designing architecture based on requirements")
        architecture = self._determine_architecture_style()

        prompt = f"""Analyze the following requirements and design an appropriate architecture.

## Requirements
{requirements}

## Target Architecture Style
{architecture}

## Task
Design a system architecture that:
1. Fits the requirements and constraints
2. Uses appropriate patterns for {architecture}
3. Is maintainable and scalable

Consider:
- Component boundaries
- Data flow
- Technology choices (let the LLM decide what's appropriate)
- Interface design (let the LLM decide: REST, GraphQL, gRPC, CLI, library, etc.)
- Security
- Error handling

Respond with a detailed architecture description in JSON format:
```json
{{
  "style": "monolith|microservices|event-driven|cli|library|...",
  "components": [
    {{
      "name": "component-name",
      "responsibility": "what it does",
      "dependencies": ["other-component"],
      "technologies": ["tech1", "tech2"]
    }}
  ],
  "data_model": {{
    "entities": [...],
    "relationships": [...]
  }},
  "interface_design": {{
    "type": "determined by LLM based on requirements",
    "details": "..."
  }},
  "rationale": "why this architecture was chosen"
}}
```"""

        result = self._run_step(prompt, label="design architecture", timeout=180)
        return {"architecture": result.get("output", ""), "style": architecture}

    def plan(self, docs_dir: Path) -> list[dict]:
        requirements_parts = []
        if docs_dir.exists():
            for f in sorted(docs_dir.glob("*.md")):
                content = f.read_text()
                requirements_parts.append(f"## {f.stem}\n\n{content}")
        requirements = "\n\n".join(requirements_parts) or "No documentation found."
        arch_context = self._determine_architecture_style()
        return self.plan_iterations(requirements, arch_context)

    def plan_iterations(self, requirements: str, architecture: str = None) -> list[dict]:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._plan_iterations_impl(requirements, architecture)
        except Exception:
            logger.exception("[architect] unhandled error in plan_iterations")
            result = []
        self.report_status("idle")
        return result

    def _plan_iterations_impl(self, requirements: str, architecture: str = None) -> list[dict]:
        self._log("Planning iterations based on requirements")
        arch_context = architecture or self._determine_architecture_style()
        existing_docs = self._read_existing_docs()

        prompt = f"""Based on the following requirements, plan concrete implementation iterations.

## Requirements
{requirements}

## Architecture Style
{arch_context}

## Existing Documentation
{json.dumps(existing_docs, indent=2)}

## Task
Create a phased implementation plan. Each phase should:
- Be independent and testable
- Deliver value incrementally
- Build on previous phases

The number of iterations and phases should be proportional to the project complexity:
- Simple projects (scripts, tools): 1-2 phases, 2-4 iterations
- Medium projects (apps, services): 2-3 phases, 4-8 iterations
- Complex projects (enterprise, distributed): 3+ phases, 8+ iterations

Output ONLY a valid JSON array of iterations:
```json
[
  {{
    "id": 1,
    "phase": 1,
    "name": "short descriptive name",
    "goal": "one sentence goal",
    "files_expected": ["path/to/file"],
    "depends_on": [],
    "acceptance_criteria": ["compiles", "tests pass"]
  }}
]
```

Keep each iteration small and focused (1-4 files).
"""

        result = self._run_step(prompt, label="plan iterations", timeout=300)
        return self._parse_iterations(result.get("output", "[]"))

    def _parse_iterations(self, output: str) -> list[dict]:
        json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []

    def create_architecture_doc(self, design: dict, output_path: Path) -> None:
        self._log(f"Creating architecture doc at {output_path}")
        _ensure_file(output_path).write_text("")

        content = f"""# Architecture

## Style
{design.get('style', 'monolith')}

## Components
"""
        for comp in design.get('components', []):
            content += f"""
### {comp.get('name', 'Unnamed')}
- **Responsibility**: {comp.get('responsibility', 'N/A')}
- **Dependencies**: {', '.join(comp.get('dependencies', [])) or 'None'}
- **Technologies**: {', '.join(comp.get('technologies', []))}
"""
        content += f"""
## Data Model
```json
{json.dumps(design.get('data_model', {}), indent=2)}
```

## Interface Design
{json.dumps(design.get('interface_design', {}), indent=2)}

## Rationale
{design.get('rationale', 'No rationale provided.')}
"""
        output_path.write_text(content)
        self.emit_file_written(output_path)

    def request_clarification(self, question: str, suggestions: list = None) -> str:
        return self.ask(question=question, suggestions=suggestions or [])

    def gather_requirements(self, docs_dir: Path) -> str:
        self._log("Gathering project requirements from user")
        clarification_question = """I'm @architect, working with the Supervisor to plan your project.

To create a proper development plan, I need to understand your vision:

1. **What do you want to build?** (e.g., "a task management app", "an AI chatbot", "a simple calculator")

2. **What are the main features/goals?**

3. **Any technical preferences?** (language, framework, database - or leave it to me to decide)

4. **Scale expectations?** (single user, team, enterprise)"""

        suggestions = [
            "I want to create a web application for task management with user authentication",
            "Build me a simple command-line tool that performs calculations",
            "I need a library module for data processing",
        ]
        return self.ask(question=clarification_question, suggestions=suggestions)
