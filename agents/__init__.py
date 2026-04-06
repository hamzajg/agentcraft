"""
agents/__init__.py — agent registry.

Each agent lives in its own subfolder:
  agents/<name>/
    agent.py      — AgentClass
    config.yaml   — skills, personas, framework_skills
    prompt.md     — system prompt

Adding a new agent: create the folder with those three files.
Removing an agent: delete the folder.
"""
from importlib import import_module
from pathlib import Path
import sys

# Ensure core/ is importable
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

def _load_agent_class(agent_name: str):
    """Dynamically load the agent class from agents/<n>/agent.py."""
    mod = import_module(f"agents.{agent_name}.agent")
    # Find the class — convention: the module exports exactly one AiderAgent subclass
    from core.base import AiderAgent
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if (isinstance(obj, type) and issubclass(obj, AiderAgent)
                and obj is not AiderAgent):
            return obj
    raise ImportError(f"No AiderAgent subclass found in agents/{agent_name}/agent.py")


def list_agents() -> list[str]:
    """Return names of all installed agent folders."""
    agents_dir = Path(__file__).parent
    return sorted(
        d.name for d in agents_dir.iterdir()
        if d.is_dir() and (d / "agent.py").exists()
    )


# Eager imports for backward compatibility with orchestrator
try:
    from agents.spec.agent             import SpecAgent
    from agents.architect.agent        import ArchitectAgent
    from agents.planner.agent          import PlannerAgent
    from agents.test_dev.agent         import TestDevAgent
    from agents.backend_dev.agent      import BackendDevAgent
    from agents.config_agent.agent     import ConfigAgent
    from agents.docs_agent.agent       import DocsAgent
    from agents.integration_test.agent import IntegrationTestAgent
    from agents.reviewer.agent         import ReviewerAgent, ReviewVerdict
    from agents.cicd.agent             import CiCdAgent
    from agents.supervisor.agent       import SupervisorAgent
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning("Agent import warning: %s", e)

__all__ = [
    "SpecAgent", "ArchitectAgent", "PlannerAgent",
    "TestDevAgent", "BackendDevAgent", "ConfigAgent", "DocsAgent",
    "IntegrationTestAgent", "ReviewerAgent", "ReviewVerdict", "CiCdAgent",
    "SupervisorAgent",
    "list_agents", "_load_agent_class",
]
