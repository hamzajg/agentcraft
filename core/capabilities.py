"""
capabilities.py — machine-readable manifest of this project's agent surface.

build_manifest(repo_root, framework_id=None) -> dict

A read-only projection of the existing registries into one deterministic,
JSON-serialisable shape: the installed agents, each one's class, its active
framework and persona, and the skills it declares. No new source of truth —
it only reports what agents/, frameworks/ and the loaders already describe.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from core.framework_loader import FrameworkLoader

# Where the shipped agents/ and frameworks/ live (this package's root).
AGENTCRAFT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = 1


def _declared_skills(repo_root: Path, agent_id: str) -> list[str]:
    """Skills named in agents/<id>/config.yaml — the agent's own list."""
    cfg = repo_root / "agents" / agent_id / "config.yaml"
    if not cfg.exists():
        return []
    try:
        data = yaml.safe_load(cfg.read_text()) or {}
    except Exception:
        return []
    return sorted(str(s) for s in (data.get("skills") or []))


def _agent_class_name(agent_id: str) -> str:
    """The agent's AiderAgent subclass name (derived fallback if it won't load)."""
    try:
        from agents import _load_agent_class
        return _load_agent_class(agent_id).__name__
    except Exception:
        return "".join(part.title() for part in agent_id.split("_")) + "Agent"


def _agent_entry(repo_root: Path, agent_id: str, loader: FrameworkLoader) -> dict:
    ctx = loader.for_agent(agent_id)
    return {
        "id":              agent_id,
        "class":           _agent_class_name(agent_id),
        "framework":       ctx.framework_id,
        "persona":         ctx.persona_name,
        "declared_skills": _declared_skills(repo_root, agent_id),
    }


def build_manifest(repo_root=None, framework_id: str | None = None) -> dict:
    """Assemble the capability manifest for *repo_root*.

    Deterministic: agents come sorted by id and every list is sorted, so two
    builds of the same repository state produce equal dicts.
    """
    root = Path(repo_root) if repo_root else AGENTCRAFT_ROOT
    loader = FrameworkLoader(framework_id)

    from agents import list_agents
    agents = [_agent_entry(root, aid, loader) for aid in list_agents()]

    return {
        "schema_version": SCHEMA_VERSION,
        "framework":      framework_id,
        "agents":         agents,
    }
