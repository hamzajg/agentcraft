"""
Hermes Skills System — Reusable agent capabilities.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class SkillDefinition:
    """Definition of a skill."""
    id: str
    name: str
    description: str
    category: str = "general"
    skill_type: str = "tool"  # tool, prompt, pipeline
    tools: List[str] = field(default_factory=list)
    system_prompt_addition: str = ""
    config: Dict[str, Any] = field(default_factory=dict)


# ─── Built-in Skills ─────────────────────────────────────────────────────────

BUILTIN_SKILLS: List[SkillDefinition] = [
    SkillDefinition(
        id="github",
        name="GitHub",
        description="Interact with GitHub repositories, issues, PRs, and actions",
        category="development",
        tools=["shell", "git"],
        system_prompt_addition="""You have GitHub access. You can:
- Create branches, commit code, push changes
- Create and manage pull requests
- View issues and comments
- Check CI/CD status
Use the git and shell tools to interact with repositories.""",
    ),
    SkillDefinition(
        id="code-analysis",
        name="Code Analysis",
        description="Analyze codebases, find patterns, detect issues",
        category="development",
        tools=["shell", "filesystem"],
        system_prompt_addition="""You can analyze code thoroughly:
- Read and understand code structure
- Find bugs, security issues, and code smells
- Suggest refactoring improvements
- Analyze dependencies and architecture
Use filesystem and shell tools to explore codebases.""",
    ),
    SkillDefinition(
        id="documentation",
        name="Documentation",
        description="Write, update, and maintain documentation",
        category="content",
        tools=["filesystem"],
        system_prompt_addition="""You are a documentation expert:
- Write clear, comprehensive documentation
- Create README files, API docs, and guides
- Use proper markdown formatting
- Include code examples when appropriate
Create artifacts for all documentation.""",
    ),
    SkillDefinition(
        id="testing",
        name="Testing",
        description="Write and run tests, analyze coverage",
        category="development",
        tools=["shell", "filesystem"],
        system_prompt_addition="""You are a testing expert:
- Write unit, integration, and e2e tests
- Analyze test coverage
- Debug failing tests
- Set up test frameworks
Use shell to run tests and filesystem to write test files.""",
    ),
    SkillDefinition(
        id="devops",
        name="DevOps",
        description="Docker, Kubernetes, CI/CD, and infrastructure",
        category="infrastructure",
        tools=["shell", "filesystem"],
        system_prompt_addition="""You are a DevOps expert:
- Write Dockerfiles and docker-compose files
- Create Kubernetes manifests
- Set up CI/CD pipelines (GitHub Actions, GitLab CI)
- Manage infrastructure as code
Use shell and filesystem tools for all operations.""",
    ),
    SkillDefinition(
        id="research",
        name="Research",
        description="Web research, information gathering, analysis",
        category="analysis",
        tools=["browser", "shell"],
        system_prompt_addition="""You are a research specialist:
- Search the web for current information
- Analyze and synthesize findings
- Provide well-sourced answers
- Track research sources
Use browser tool for web searches and fetching content.""",
    ),
    SkillDefinition(
        id="data-analysis",
        name="Data Analysis",
        description="Analyze data, create reports, generate visualizations",
        category="analysis",
        tools=["shell", "filesystem"],
        system_prompt_addition="""You are a data analyst:
- Analyze datasets and trends
- Create charts and visualizations
- Generate summary reports
- Process CSV, JSON, and other data formats
Use shell for data processing and create artifact reports.""",
    ),
    SkillDefinition(
        id="ui-design",
        name="UI/UX Design",
        description="Design interfaces, create wireframes, review UI code",
        category="design",
        tools=["filesystem"],
        system_prompt_addition="""You are a UI/UX design expert:
- Create clean, intuitive interfaces
- Follow design system principles
- Ensure accessibility (WCAG)
- Review and improve UI code
Create design artifacts and component code.""",
    ),
    SkillDefinition(
        id="security",
        name="Security",
        description="Security auditing, vulnerability scanning, secure coding",
        category="security",
        tools=["shell", "filesystem"],
        system_prompt_addition="""You are a security expert:
- Audit code for vulnerabilities
- Review authentication and authorization
- Check for common security issues (OWASP Top 10)
- Suggest security improvements
Use shell for scanning and filesystem for code review.""",
    ),
    SkillDefinition(
        id="performance",
        name="Performance",
        description="Performance analysis, optimization, profiling",
        category="optimization",
        tools=["shell", "filesystem"],
        system_prompt_addition="""You are a performance expert:
- Profile and benchmark code
- Identify bottlenecks
- Optimize algorithms and data structures
- Improve database queries
Use shell for profiling and filesystem for code optimization.""",
    ),
]


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._load_builtins()

    def _load_builtins(self):
        """Load built-in skills."""
        for skill in BUILTIN_SKILLS:
            self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def list_skills(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def list_by_category(self, category: str) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if s.category == category]

    def get_categories(self) -> List[str]:
        return list(set(s.category for s in self._skills.values()))

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill

    def get_tools_for_skills(self, skill_ids: List[str]) -> List[str]:
        """Get all tool names required by the given skills."""
        tools = set()
        for sid in skill_ids:
            skill = self.get(sid)
            if skill:
                tools.update(skill.tools)
        return list(tools)

    def get_prompt_additions(self, skill_ids: List[str]) -> str:
        """Get combined system prompt additions from skills."""
        additions = []
        for sid in skill_ids:
            skill = self.get(sid)
            if skill and skill.system_prompt_addition:
                additions.append(f"## {skill.name}\n{skill.system_prompt_addition}")
        return "\n\n".join(additions)


# Global skill registry
skill_registry = SkillRegistry()
