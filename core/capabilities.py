"""
capabilities.py — machine-readable manifest of this project's agent surface.

build_manifest(repo_root, framework_id=None) -> dict

A read-only projection of the existing registries into one deterministic,
JSON-serialisable shape: the installed agents (each one's class, active
framework, persona, and declared + resolved skills), the available frameworks,
and the available skills. No new source of truth — it only reports what
agents/, frameworks/ and the loaders already describe.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from core.framework_loader import FrameworkLoader
from core.skill_runner import FRAMEWORKS_DIR, SKILLS_DIR

# Where the shipped agents/ and frameworks/ live (this package's root).
AGENTCRAFT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = 1


def resolve_skill(name: str, framework_id: str | None = None,
                  frameworks_dir: Path = FRAMEWORKS_DIR,
                  skills_dir: Path = SKILLS_DIR) -> dict:
    """Where a skill name resolves: a framework skill shadows a global one.

    Returns {name, source, exists} with source in framework|global|missing.
    A missing skill is reported, never dropped.
    """
    if framework_id and (frameworks_dir / framework_id / "skills" / name).is_dir():
        return {"name": name, "source": "framework", "exists": True}
    if (skills_dir / name).is_dir():
        return {"name": name, "source": "global", "exists": True}
    return {"name": name, "source": "missing", "exists": False}


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


def _resolved_skills(skill_names, framework_id: str | None) -> list[dict]:
    """Deduped, sorted resolution of every skill name an agent ends up with."""
    return [resolve_skill(name, framework_id) for name in sorted(set(skill_names))]


def _agent_entry(repo_root: Path, agent_id: str, loader: FrameworkLoader,
                 framework_id: str | None) -> dict:
    ctx = loader.for_agent(agent_id)
    return {
        "id":              agent_id,
        "class":           _agent_class_name(agent_id),
        "framework":       ctx.framework_id,
        "persona":         ctx.persona_name,
        "declared_skills": _declared_skills(repo_root, agent_id),
        "resolved_skills": _resolved_skills(ctx.skills, framework_id),
    }


def _frameworks_section() -> list[dict]:
    """Every shipped framework: id, label, global skills and per-agent overrides."""
    section = []
    for fw_id in sorted(FrameworkLoader.list_frameworks()):
        info = FrameworkLoader(fw_id).describe()
        overrides = info.get("agents", {}) or {}
        section.append({
            "id":            fw_id,
            "label":         info.get("label", fw_id),
            "global_skills": sorted(info.get("global_skills", []) or []),
            "agents":        {k: overrides[k] for k in sorted(overrides)},
        })
    return section


def build_manifest(repo_root=None, framework_id: str | None = None) -> dict:
    """Assemble the capability manifest for *repo_root*.

    Deterministic: agents come sorted by id and every list is sorted, so two
    builds of the same repository state produce equal dicts.
    """
    root = Path(repo_root) if repo_root else AGENTCRAFT_ROOT
    loader = FrameworkLoader(framework_id)

    from agents import list_agents
    from core.skill_runner import SkillRunner

    agents = [_agent_entry(root, aid, loader, framework_id) for aid in list_agents()]

    return {
        "schema_version": SCHEMA_VERSION,
        "framework":      framework_id,
        "agents":         agents,
        "frameworks":     _frameworks_section(),
        "skills":         SkillRunner(framework_id=framework_id).list_available(),
    }


def render_json(manifest: dict) -> str:
    """The manifest as indented JSON — the machine-readable stdout form."""
    import json
    return json.dumps(manifest, indent=2)


def render_summary(manifest: dict) -> str:
    """A human-readable inventory of the capability surface for the terminal."""
    agents = manifest.get("agents", [])
    lines = [
        f"AgentCraft capability manifest (schema v{manifest.get('schema_version')})",
        f"Framework: {manifest.get('framework') or 'none'}",
        f"Agents ({len(agents)}):",
    ]
    for agent in agents:
        lines.append(f"  - {agent['id']} ({agent['class']})")
        lines.append(
            f"      framework: {agent.get('framework') or 'none'}"
            f", persona: {agent.get('persona') or 'none'}"
        )
        skills = ", ".join(r["name"] for r in agent.get("resolved_skills", []))
        if skills:
            lines.append(f"      skills: {skills}")

    frameworks = manifest.get("frameworks", [])
    lines.append(f"Frameworks ({len(frameworks)}): "
                 + ", ".join(f["id"] for f in frameworks))
    skills = manifest.get("skills", [])
    lines.append(f"Skills ({len(skills)}): " + ", ".join(skills))
    return "\n".join(lines)
