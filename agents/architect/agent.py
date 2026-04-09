"""
architect/agent.py — Architect agent.

ROLE: Context gatherer for architecture planning.

This agent:
- Reads project requirements and documentation
- Gathers context about the workspace and existing code
- Prepares architecture planning prompts for the LLM
- Writes architecture decisions to documentation

ALL ARCHITECTURE DECISIONS ARE MADE BY LLM.
No hardcoded project-specific examples or logic.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Architect Agent.

Your role is to analyze requirements and design appropriate system architecture.
"""


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
    ):
        super().__init__(
            role="architect",
            model=model,
            workspace=workspace,
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or [],
            framework_id=framework_id,
            max_retries=2,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def _log(self, message: str):
        """Send log message to comms server if callback is set."""
        if self.log_callback:
            try:
                self.log_callback(self.role, message)
            except Exception:
                pass
        logger.info("[architect] %s", message)

    def gather_context(self) -> dict:
        """
        Gather all context needed for architecture planning.
        
        Returns:
            Dictionary containing all relevant context for architecture decisions.
        """
        context = {
            "workspace": self._read_workspace_config(),
            "requirements": self._read_requirements(),
            "existing_docs": self._read_existing_docs(),
            "architecture_style": self._determine_architecture_style(),
        }
        return context

    def _read_workspace_config(self) -> dict:
        """Read workspace.yaml configuration."""
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
        """Read requirements documentation."""
        docs_dir = self.workspace / "docs"
        ai_dir = self.workspace / ".ai"
        
        requirements = []
        
        for md_file in (docs_dir / "requirements.md").exists() and [docs_dir / "requirements.md"] or []:
            requirements.append(f"## {md_file.name}\n{md_file.read_text()[:2000]}")
        
        for md_file in (docs_dir / "blueprint.md").exists() and [docs_dir / "blueprint.md"] or []:
            requirements.append(f"## {md_file.name}\n{md_file.read_text()[:1000]}")
        
        return "\n\n".join(requirements) if requirements else "No requirements found."

    def _read_existing_docs(self) -> dict:
        """Read all existing documentation."""
        docs_dir = self.workspace / "docs"
        ai_dir = self.workspace / ".ai"
        
        docs = {}
        
        for md_file in docs_dir.glob("*.md"):
            docs[md_file.name] = md_file.read_text()[:1500]
        
        for md_file in ai_dir.glob("*.md"):
            docs[md_file.name] = md_file.read_text()[:1500]
        
        return docs

    def _determine_architecture_style(self) -> str:
        """Determine architecture style from workspace config."""
        workspace = self._read_workspace_config()
        return workspace.get("project", {}).get("architecture", "monolith")

    def design_architecture(self, requirements: str) -> dict:
        """
        Design architecture based on requirements using LLM.
        
        Args:
            requirements: Project requirements text
            
        Returns:
            Architecture design decisions from LLM
        """
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
- Technology choices
- API design
- Security
- Error handling

Respond with a detailed architecture description in JSON format:
```json
{{
  "style": "monolith|microservices|event-driven|...",
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
  "api_design": {{
    "style": "REST|GraphQL|gRPC",
    "endpoints": [...]
  }},
  "rationale": "why this architecture was chosen"
}}
```"""

        response = self.run(message=prompt, timeout=180)
        
        return {
            "architecture": response.get("output", ""),
            "style": architecture,
        }

    def plan_iterations(self, requirements: str, architecture: str = None) -> list[dict]:
        """
        Plan iterations based on requirements using LLM.
        
        Args:
            requirements: Project requirements
            architecture: Optional architecture context
            
        Returns:
            List of planned iterations
        """
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

Output ONLY a valid JSON array of iterations:
```json
[
  {{
    "id": 1,
    "phase": 1,
    "name": "short descriptive name",
    "goal": "one sentence goal",
    "layer": "model|api|infrastructure",
    "files_expected": ["path/to/File.java"],
    "depends_on": [],
    "acceptance_criteria": ["compiles", "tests pass"]
  }}
]
```

Generate 6-12 iterations across 3 phases. Keep each iteration small (2-4 files).
"""

        result = self.run(message=prompt, timeout=300)
        
        return self._parse_iterations(result.get("output", "[]"))

    def _parse_iterations(self, output: str) -> list[dict]:
        """Parse iterations from LLM output."""
        import re
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
        """
        Create architecture documentation from design.
        
        Args:
            design: Architecture design dict
            output_path: Where to write the doc
        """
        self._log(f"Creating architecture doc at {output_path}")
        
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

## API Design
{json.dumps(design.get('api_design', {}), indent=2)}

## Rationale
{design.get('rationale', 'No rationale provided.')}
"""
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        self.emit_file_written(output_path)

    def request_clarification(self, question: str, suggestions: list = None) -> str:
        """
        Request clarification from user.
        
        Args:
            question: The question to ask
            suggestions: Optional suggested answers
            
        Returns:
            User's response
        """
        return self.ask(question=question, suggestions=suggestions or [])
