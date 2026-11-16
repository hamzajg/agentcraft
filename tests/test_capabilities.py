"""
Tests for the capability manifest (core/capabilities.py).

The manifest is a read-only projection of the agent registry, so these tests
pin its shape and determinism against the real repo — no LLM, no aider.
"""
from pathlib import Path

from core.capabilities import SCHEMA_VERSION, build_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestAgentsSection:
    def test_lists_every_installed_agent_with_its_class(self):
        from agents import list_agents
        manifest = build_manifest(REPO_ROOT)
        ids = [a["id"] for a in manifest["agents"]]
        assert ids == sorted(list_agents())
        assert "architect" in ids
        architect = next(a for a in manifest["agents"] if a["id"] == "architect")
        assert architect["class"] == "ArchitectAgent"

    def test_is_deterministic_and_carries_a_schema_version(self):
        assert build_manifest(REPO_ROOT) == build_manifest(REPO_ROOT)
        assert build_manifest(REPO_ROOT)["schema_version"] == SCHEMA_VERSION
        assert isinstance(SCHEMA_VERSION, int)

    def test_reports_active_framework_and_persona_per_agent(self):
        manifest = build_manifest(REPO_ROOT, framework_id="openspec")
        assert manifest["framework"] == "openspec"
        architect = next(a for a in manifest["agents"] if a["id"] == "architect")
        assert architect["framework"] == "openspec"
        assert architect["persona"] == "openspec-architect"

    def test_no_framework_yields_no_persona(self):
        manifest = build_manifest(REPO_ROOT)
        assert manifest["framework"] is None
        assert all(a["persona"] is None for a in manifest["agents"])

    def test_declared_skills_are_sorted_for_each_agent(self):
        manifest = build_manifest(REPO_ROOT)
        for agent in manifest["agents"]:
            assert agent["declared_skills"] == sorted(agent["declared_skills"])
