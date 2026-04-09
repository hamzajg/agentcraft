"""
spec/agent.py — Spec agent.

Baby-step approach:
  Step 1: extract entities only (fast, focused)
  Step 2: write spec.md using entity list as scaffold (bounded output)
  Step 3: write 3 use cases max (not all of them)
"""

import logging
import re
import time
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Spec Agent. Create specification documents from requirements."""


class SpecAgent(AiderAgent):
    _role = "spec"

    def __init__(self, model: str, workspace: Path,
                 system_prompt: str = None, skills: list = None,
                 framework_id: str = None, task_id: str = None,
                 iteration_id: int = None, **kwargs):
        super().__init__(
            role="spec",
            model=model,
            workspace=workspace,
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or [],
            framework_id=framework_id,
            task_id=task_id,
            iteration_id=iteration_id,
            **kwargs,
        )
        self._is_openspec = (framework_id == "openspec")

    def specify(self, docs_dir: Path) -> tuple[Path, Path]:
        self.report_status("running")
        if self._is_openspec:
            result = self._specify_openspec(docs_dir)
        else:
            result = self._specify_default(docs_dir)
        self.report_status("idle")
        return result

    def _specify_default(self, docs_dir: Path) -> tuple[Path, Path]:
        ai_dir = self._ai_dir()
        spec_file      = ai_dir / "spec.md"
        use_cases_file = ai_dir / "use_cases.md"
        doc_files      = list(docs_dir.glob("*.md"))

        if not doc_files:
            logger.warning("[spec] no docs found in %s", docs_dir)
            return spec_file, use_cases_file

        # Resume logic: skip if files already exist and are non-empty
        if spec_file.exists() and spec_file.stat().st_size > 0:
            if use_cases_file.exists() and use_cases_file.stat().st_size > 0:
                logger.info("[spec] spec.md and use_cases.md already exist — skipping generation (resume mode)")
                self.emit_file_written(spec_file)
                self.emit_file_written(use_cases_file)
                return spec_file, use_cases_file

        logger.info("[spec] step 1/3 — extract entities (%d docs)", len(doc_files))

        # ── Step 1: extract key entities — small, fast ────────────────────────
        entities_file = ai_dir / "entities.md"
        
        # Remove file if it exists (might be empty from previous failed run)
        if entities_file.exists():
            entities_file.unlink()
        
        result1 = self.run(
            message=(
                f"Read the docs. List the main entities (nouns) this system works with.\n"
                f"Format: one entity per line, with 1-sentence description.\n"
                f"Max 10 entities. No code. No headers.\n"
                f"\n"
                f"CREATE the file '{entities_file.name}' and write the entity list to it."
            ),
            read_files=doc_files,
            edit_files=[entities_file],  # Will only be added to CLI if exists
            log_callback=self.log_callback,
        )
        
        # Check if file was actually written
        success = result1.get("success", False)
        file_exists = entities_file.exists()
        file_size = entities_file.stat().st_size if file_exists else 0
        
        logger.info("[spec] step 1 result: success=%s, file_exists=%s, size=%d", 
                   success, file_exists, file_size)
        
        if not success:
            logger.error("[spec] step 1 failed - aider exit code: %d", result1.get("exit_code", -1))
            logger.error("[spec] stderr: %s", result1.get("stderr", "")[:200])
        
        if not file_exists or file_size == 0:
            logger.error("[spec] step 1 failed - entities.md is empty or not created")
            if file_exists:
                entities_file.unlink()  # Remove empty file
            return None, None

        # ── Step 2: write spec.md — bounded by entity list ────────────────────
        context = doc_files + [entities_file]
        logger.info("[spec] step 2/3 — write spec.md")
        result2 = self.run(
            message=(
                "Write spec.md for this project.\n\n"
                "Include these sections (adapt to the project type):\n"
                "## Problem\nOne paragraph.\n\n"
                "## Entities\nFor each entity: name, fields (name:type), key behaviour.\n\n"
                "## Interface\nDescribe how users/systems interact with this project.\n"
                "  - For APIs: endpoints, methods, request/response\n"
                "  - For CLI: commands, arguments, output format\n"
                "  - For libraries: public functions/classes, parameters, return values\n"
                "  - For GUIs: screens, user flows, interactions\n\n"
                "## Rules\nBullet list of system-wide rules (invariants).\n\n"
                "Keep it short. One sentence per point."
            ),
            read_files=context,
            edit_files=[spec_file],
            timeout=1200,  # 20 minutes for complex spec writing
            log_callback=self.log_callback,
        )
        
        # Check if file was actually written
        if not result2.get("success") or not spec_file.exists() or spec_file.stat().st_size == 0:
            logger.error("[spec] step 2 failed - spec.md is empty or not created")
            if spec_file.exists():
                spec_file.unlink()  # Remove empty file
            return None, None

        # ── Step 3: write 3 use cases ─────────────────────────────────────────
        context2 = context + [spec_file]
        logger.info("[spec] step 3/3 — write use cases")
        result3 = self.run(
            message=(
                "Write use_cases.md with the 3 most important use cases.\n\n"
                "Each use case:\n"
                "## UC-N: title\n"
                "Given: ...\n"
                "When: ...\n"
                "Then: ...\n"
                "Error: what goes wrong and why.\n\n"
                "Keep each case to 6 lines max."
            ),
            read_files=context2,
            edit_files=[use_cases_file],
            timeout=1200,  # 20 minutes for use case writing
            log_callback=self.log_callback,
        )
        
        # Check if file was actually written
        if not result3.get("success") or not use_cases_file.exists() or use_cases_file.stat().st_size == 0:
            logger.error("[spec] step 3 failed - use_cases.md is empty or not created")
            if use_cases_file.exists():
                use_cases_file.unlink()  # Remove empty file
            return None, None

        logger.info("[spec] done — spec.md + use_cases.md")
        return spec_file, use_cases_file

    def _specify_openspec(self, docs_dir: Path) -> tuple[Path, Path]:
        doc_files    = list(docs_dir.glob("*.md"))
        project_name = self._project_name()
        domain       = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        change_name  = f"initial-{domain}"

        openspec_root = self.workspace / "openspec"
        specs_dir     = openspec_root / "specs" / domain
        change_dir    = openspec_root / "changes" / change_name
        change_specs  = change_dir / "specs" / domain

        for d in [specs_dir, change_dir, change_specs]:
            d.mkdir(parents=True, exist_ok=True)

        proposal_file   = change_dir / "proposal.md"
        delta_spec_file = change_specs / "spec.md"
        design_file     = change_dir / "design.md"
        tasks_file      = change_dir / "tasks.md"

        # Resume logic: skip if files already exist and are non-empty
        if proposal_file.exists() and proposal_file.stat().st_size > 0:
            if delta_spec_file.exists() and delta_spec_file.stat().st_size > 0:
                logger.info("[spec] OpenSpec proposal and spec already exist — skipping (resume mode)")
                self.emit_file_written(proposal_file)
                self.emit_file_written(delta_spec_file)
                return proposal_file, delta_spec_file

        # Step 1: proposal (why + what)
        logger.info("[spec] openspec step 1/3 — proposal")
        self.run(
            message=(
                f"Write an OpenSpec proposal for project '{project_name}'.\n\n"
                "Sections:\n"
                "## Why\nOne paragraph — the problem.\n\n"
                "## What Changes\nBullet list of capabilities added.\n\n"
                "## Out of Scope\nBullet list of what is NOT included.\n\n"
                "Keep it under 200 words."
            ),
            read_files=doc_files,
            edit_files=[proposal_file],
            timeout=90,
        )

        # Step 2: delta spec (requirements)
        logger.info("[spec] openspec step 2/3 — delta spec")
        ctx = doc_files + ([proposal_file] if proposal_file.exists() else [])
        self.run(
            message=(
                f"Write an OpenSpec delta spec for domain '{domain}'.\n\n"
                "Format:\n"
                "# Delta for " + domain + "\n\n"
                "## ADDED Requirements\n\n"
                "### Requirement: <name>\n"
                "The system SHALL <behaviour>.\n\n"
                "#### Scenario: <name>\n"
                "- GIVEN ...\n"
                "- WHEN ...\n"
                "- THEN ...\n\n"
                "Write 5-8 requirements. Keep each scenario to 3 lines."
            ),
            read_files=ctx,
            edit_files=[delta_spec_file],
            timeout=120,
        )

        # Copy to source-of-truth
        if delta_spec_file.exists():
            sot_spec = specs_dir.joinpath("spec.md")
            sot_spec.write_text(delta_spec_file.read_text())
            self.emit_file_written(sot_spec)

        # Stubs for architect/planner
        if not design_file.exists():
            design_file.write_text(
                f"# Design: {change_name}\n\n"
                "_Architect fills this._\n\n"
                "## Approach\n\n## Key Decisions\n\n## Component Changes\n"
            )
            self.emit_file_written(design_file)
        if not tasks_file.exists():
            tasks_file.write_text(
                f"# Tasks: {change_name}\n\n"
                "_Planner fills this._\n\n"
                "- [ ] 1.1 \n- [ ] 1.2 \n"
            )
            self.emit_file_written(tasks_file)

        agents_md = openspec_root / "AGENTS.md"
        agents_md.write_text(
            "# OpenSpec\n\nopen openspec/changes/ to find the active change.\n"
            "Read proposal.md → specs/ → design.md → tasks.md before coding.\n"
        )
        self.emit_file_written(agents_md)

        logger.info("[spec] openspec done")
        return proposal_file, delta_spec_file

    def _project_name(self) -> str:
        try:
            import yaml
            ws = (self.workspace / "workspace.yaml")
            if not ws.exists():
                ws = self.workspace.parent / "workspace.yaml"
            if ws.exists():
                return yaml.safe_load(ws.read_text()).get("project", {}).get("name", "project")
        except Exception:
            pass
        return "project"

    def _ai_dir(self) -> Path:
        d = self.workspace / ".ai"
        d.mkdir(exist_ok=True)
        return d
