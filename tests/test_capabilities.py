"""
Tests for the capability manifest (core/capabilities.py).

The manifest is a read-only projection of the agent registry, so these tests
pin its shape and determinism against the real repo — no LLM, no aider.
"""
from pathlib import Path

from core.capabilities import SCHEMA_VERSION, build_manifest, resolve_skill

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


class TestSkillResolution:
    def test_framework_skill_shadows_global(self, tmp_path: Path):
        (tmp_path / "frameworks" / "fw" / "skills" / "shared").mkdir(parents=True)
        (tmp_path / "skills" / "shared").mkdir(parents=True)
        entry = resolve_skill(
            "shared", "fw",
            frameworks_dir=tmp_path / "frameworks",
            skills_dir=tmp_path / "skills",
        )
        assert entry == {"name": "shared", "source": "framework", "exists": True}

    def test_global_skill_used_when_framework_has_none(self, tmp_path: Path):
        (tmp_path / "skills" / "only-global").mkdir(parents=True)
        entry = resolve_skill(
            "only-global", "fw",
            frameworks_dir=tmp_path / "frameworks",
            skills_dir=tmp_path / "skills",
        )
        assert entry == {"name": "only-global", "source": "global", "exists": True}

    def test_a_missing_skill_is_reported_rather_than_dropped(self, tmp_path: Path):
        entry = resolve_skill(
            "nowhere", "fw",
            frameworks_dir=tmp_path / "frameworks",
            skills_dir=tmp_path / "skills",
        )
        assert entry == {"name": "nowhere", "source": "missing", "exists": False}

    def test_resolved_skills_cover_every_declared_skill(self):
        manifest = build_manifest(REPO_ROOT, framework_id="openspec")
        for agent in manifest["agents"]:
            names = [r["name"] for r in agent["resolved_skills"]]
            assert names == sorted(names)
            assert len(names) == len(set(names))
            for declared in agent["declared_skills"]:
                assert declared in names

    def test_real_resolution_marks_framework_and_global_sources(self):
        manifest = build_manifest(REPO_ROOT, framework_id="openspec")
        architect = next(a for a in manifest["agents"] if a["id"] == "architect")
        by_name = {r["name"]: r for r in architect["resolved_skills"]}
        assert by_name["openspec-propose"]["source"] == "framework"
        assert by_name["create-doc"]["source"] == "global"
        assert all(r["exists"] for r in architect["resolved_skills"])


class TestFrameworksSection:
    def test_lists_frameworks_with_their_global_skills(self):
        from core.framework_loader import FrameworkLoader
        manifest = build_manifest(REPO_ROOT)
        by_id = {f["id"]: f for f in manifest["frameworks"]}
        assert set(by_id) == set(FrameworkLoader.list_frameworks())
        assert by_id["openspec"]["label"] == "OpenSpec (Spec-Driven Development)"
        assert by_id["openspec"]["global_skills"] == sorted(
            ["run-checklist", "openspec-review"])
        assert by_id["bmad-method"]["global_skills"] == ["run-checklist"]

    def test_lists_available_skills_for_the_active_framework(self):
        manifest = build_manifest(REPO_ROOT, framework_id="openspec")
        assert manifest["skills"] == sorted(manifest["skills"])
        assert "openspec-propose" in manifest["skills"]   # framework skill
        assert "run-checklist" in manifest["skills"]      # global skill
