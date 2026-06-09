"""
Hermes Skills — Reusable prompt templates and tool configurations.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class SkillDefinition:
    """A reusable skill with prompt sections and tool configs."""
    id: str
    name: str
    description: str
    category: str = "general"
    tools: List[str] = field(default_factory=list)
    prompt_sections: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._register_builtins()

    def _register_builtins(self):
        builtins = [
            SkillDefinition(
                id="github", name="GitHub", description="GitHub operations via CLI",
                category="development",
                tools=["shell", "git"],
                prompt_sections={"github": "Use `gh` CLI for GitHub operations: PRs, issues, repos."},
            ),
            SkillDefinition(
                id="code_analysis", name="Code Analysis", description="Analyze code quality",
                category="development",
                tools=["shell", "filesystem"],
                prompt_sections={"code_analysis": "Analyze code for bugs, complexity, and improvements."},
            ),
            SkillDefinition(
                id="documentation", name="Documentation", description="Generate docs",
                category="content",
                tools=["filesystem"],
                prompt_sections={"documentation": "Generate documentation including README, API docs, and comments."},
            ),
            SkillDefinition(
                id="testing", name="Testing", description="Write and run tests",
                category="development",
                tools=["shell", "filesystem"],
                prompt_sections={"testing": "Write unit/integration tests. Run them and fix failures."},
            ),
            SkillDefinition(
                id="devops", name="DevOps", description="Infrastructure and deployment",
                category="infrastructure",
                tools=["shell", "filesystem"],
                prompt_sections={"devops": "Handle Docker, Kubernetes, CI/CD, and infrastructure as code."},
            ),
            SkillDefinition(
                id="research", name="Research", description="Web research and analysis",
                category="analysis",
                tools=["shell", "browser"],
                prompt_sections={"research": "Research topics using web search. Summarize findings."},
            ),
            SkillDefinition(
                id="data_analysis", name="Data Analysis", description="Analyze datasets",
                category="analysis",
                tools=["shell", "filesystem"],
                prompt_sections={"data_analysis": "Analyze data using Python/pandas. Generate visualizations."},
            ),
            SkillDefinition(
                id="ui_ux", name="UI/UX Design", description="Design user interfaces",
                category="design",
                tools=["filesystem"],
                prompt_sections={"ui_ux": "Design intuitive UIs with accessibility and responsiveness."},
            ),
            SkillDefinition(
                id="security", name="Security", description="Security analysis and hardening",
                category="security",
                tools=["shell", "filesystem"],
                prompt_sections={"security": "Perform security audits, find vulnerabilities, apply patches."},
            ),
            SkillDefinition(
                id="performance", name="Performance", description="Optimize performance",
                category="optimization",
                tools=["shell", "filesystem"],
                prompt_sections={"performance": "Profile bottlenecks and optimize code performance."},
            ),
        ]
        for skill in builtins:
            self._skills[skill.id] = skill

    def register(self, skill: SkillDefinition):
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def list_skills(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def get_categories(self) -> Dict[str, List[str]]:
        cats: Dict[str, List[str]] = {}
        for s in self._skills.values():
            cats.setdefault(s.category, []).append(s.id)
        return cats

    def get_prompt_additions(self, skill_ids: List[str]) -> str:
        """Return concatenated prompt sections for given skill IDs."""
        parts = []
        for sid in skill_ids:
            skill = self._skills.get(sid)
            if skill:
                for section, text in skill.prompt_sections.items():
                    parts.append(f"[{section}] {text}")
        return "\n".join(parts)

    def get_tools_for_skills(self, skill_ids: List[str]) -> List[str]:
        """Return unique tool names required by given skill IDs."""
        tools = set()
        for sid in skill_ids:
            skill = self._skills.get(sid)
            if skill:
                tools.update(skill.tools)
        return sorted(tools)


skill_registry = SkillRegistry()
