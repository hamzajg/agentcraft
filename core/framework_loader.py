"""
framework_loader.py — loads a framework and resolves per-agent context.

A framework bundles personas + skill overrides for a methodology (e.g. BMAD).
FrameworkLoader.for_agent(id) -> AgentContext with merged prompt + skill list.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

FRAMEWORKS_DIR    = Path(__file__).parent.parent / "frameworks"
AGENT_CONFIGS_DIR = Path(__file__).parent.parent / "agents"


@dataclass
class AgentContext:
    agent_id:      str
    system_prompt: str
    skills:        list
    persona_name:  Optional[str] = None
    framework_id:  Optional[str] = None


class FrameworkLoader:

    def __init__(self, framework_id: Optional[str] = None):
        self.framework_id  = framework_id
        self._fw_config:   Optional[dict] = None
        self._agent_confs: dict[str, dict] = {}

        if framework_id:
            fw_yaml = FRAMEWORKS_DIR / framework_id / "framework.yaml"
            if fw_yaml.exists():
                with fw_yaml.open() as f:
                    self._fw_config = yaml.safe_load(f)
                logger.info("[framework] loaded '%s': %s",
                            framework_id, self._fw_config.get("label", framework_id))
            else:
                logger.error("[framework] not found: %s", fw_yaml)

    def for_agent(self, agent_id: str) -> AgentContext:
        """Return merged system_prompt and skill list for this agent."""
        conf        = self._agent_conf(agent_id)
        base_prompt = self._read_prompt(conf.get("prompt", f"prompts/{agent_id}.md"))
        skills      = list(conf.get("skills", []))
        persona_name: Optional[str] = None
        persona_text: Optional[str] = None

        if self.framework_id and self._fw_config:
            # Global skills
            for s in self._fw_config.get("global_skills", []):
                if s not in skills:
                    skills.append(s)
            # Per-agent overrides
            fw_agent = self._fw_config.get("agents", {}).get(agent_id, {})
            for s in fw_agent.get("skills", []):
                if s not in skills:
                    skills.append(s)
            # Persona
            persona_name = fw_agent.get("persona") or \
                           conf.get("personas", {}).get(self.framework_id)
            if persona_name:
                persona_text = self._read_persona(persona_name)

        system_prompt = base_prompt
        if persona_text:
            system_prompt = base_prompt.rstrip() + "\n\n---\n\n" + persona_text

        logger.debug("[framework] agent '%s' → persona=%s skills=%s",
                     agent_id, persona_name, skills)
        return AgentContext(
            agent_id=agent_id,
            system_prompt=system_prompt,
            skills=skills,
            persona_name=persona_name,
            framework_id=self.framework_id,
        )

    def describe(self) -> dict:
        if not self._fw_config:
            return {"framework": None}
        return {
            "framework":     self.framework_id,
            "label":         self._fw_config.get("label", self.framework_id),
            "global_skills": self._fw_config.get("global_skills", []),
            "agents":        self._fw_config.get("agents", {}),
        }

    @staticmethod
    def list_frameworks() -> list:
        if not FRAMEWORKS_DIR.exists():
            return []
        return [d.name for d in FRAMEWORKS_DIR.iterdir() if d.is_dir()]

    def _agent_conf(self, agent_id: str) -> dict:
        if agent_id not in self._agent_confs:
            # New layout: agents/<id>/config.yaml
            f = AGENT_CONFIGS_DIR / agent_id / "config.yaml"
            if not f.exists():
                # Fallback for any legacy agent_configs/ layout
                f = AGENT_CONFIGS_DIR / f"{agent_id}.yaml"
            self._agent_confs[agent_id] = yaml.safe_load(f.read_text()) if f.exists() else {}
        return self._agent_confs[agent_id]

    def _read_prompt(self, rel_path: str) -> str:
        # Try relative to repo root first, then relative to core/
        root = Path(__file__).parent.parent
        for base in [root, root / "core"]:
            p = base / rel_path
            if p.exists():
                return p.read_text()
        # New layout: agents/<id>/prompt.md
        # rel_path looks like "prompts/spec.md" — convert to agents/spec/prompt.md
        import re
        m = re.match(r"prompts/(\w+)\.md", rel_path)
        if m:
            p = root / "agents" / m.group(1) / "prompt.md"
            if p.exists():
                return p.read_text()
        return "# Agent\nYou are a helpful AI agent." 

    def _read_persona(self, persona_name: str) -> Optional[str]:
        f = FRAMEWORKS_DIR / self.framework_id / "personas" / f"{persona_name}.md"
        return f.read_text() if f.exists() else None
