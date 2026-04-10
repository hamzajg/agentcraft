"""
spec/agent.py — Spec agent.

Responsible for the specification phase only.
Reads input docs, extracts entities, writes spec.md and use_cases.md.

Follows the same structure as docs_agent:
  - Public entry point: specify(docs_dir) -> (spec_file, use_cases_file)
  - Internal steps with clear context chaining
  - Resume support (skip non-empty files)
  - Proper file validation after each aider run
"""

import logging
import re
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    (Path(__file__).parent / "prompt.md").read_text()
    if (Path(__file__).parent / "prompt.md").exists()
    else "You are the Spec Agent. Create precise, unambiguous specification documents from requirements."
)


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories (like docs_agent and other agents do)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
    return path.exists() and path.stat().st_size > 0


class SpecAgent(AiderAgent):
    _role = "spec"

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
        **kwargs,
    ):
        super().__init__(
            role="spec",
            model=model,
            workspace=workspace,
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or ["deep-research", "create-doc", "agent-collaboration"],
            framework_id=framework_id,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
            **kwargs,
        )
        self._is_openspec = framework_id == "openspec"

    # ── Public entry point (called by orchestrator) ───────────────────────

    def specify(self, docs_dir: Path) -> tuple[Path, Path]:
        """
        Generate specification documents from requirements docs.

        Args:
            docs_dir: Directory containing input requirement/markdown docs.

        Returns:
            Tuple of (spec_file, use_cases_file) paths.
            Always returns Path objects (possibly empty files on failure).
            The orchestrator creates stubs if content is missing.
        """
        self.report_status("running")
        try:
            if self._is_openspec:
                result = self._specify_openspec(docs_dir)
            else:
                result = self._specify_default(docs_dir)
        except Exception:
            logger.exception("[spec] unhandled error in specify phase")
            ai_dir = self._ai_dir() if self.workspace else Path(".ai")
            result = (_ensure_file(ai_dir / "spec.md"), _ensure_file(ai_dir / "use_cases.md"))
        self.report_status("idle")
        return result

    # ── Default (non-OpenSpec) flow ──────────────────────────────────────

    def _specify_default(self, docs_dir: Path) -> tuple[Path, Path]:
        ai_dir = self._ai_dir()
        spec_file = _ensure_file(ai_dir / "spec.md")
        use_cases_file = _ensure_file(ai_dir / "use_cases.md")
        doc_files = list(docs_dir.glob("*.md"))

        if not doc_files:
            logger.warning("[spec] no input docs found in %s — generating from scratch", docs_dir)

        # Resume: skip if both files already have content
        if _file_has_content(spec_file) and _file_has_content(use_cases_file):
            logger.info("[spec] spec.md and use_cases.md already exist — skipping (resume)")
            self.emit_file_written(spec_file)
            self.emit_file_written(use_cases_file)
            return spec_file, use_cases_file

        # Clear any stale content from previous failed runs
        spec_file.write_text("")
        use_cases_file.write_text("")

        # Step 1: Extract entities (fast, focused scaffolding)
        entities_file = self._extract_entities(doc_files, ai_dir)
        if entities_file is None:
            logger.error("[spec] entity extraction failed — cannot continue")
            return spec_file, use_cases_file  # return empty paths, orchestrator creates stubs

        # Step 2: Write spec.md (bounded by entity list)
        context = doc_files + [entities_file]
        if not self._write_spec_file(spec_file, context):
            return spec_file, use_cases_file  # return empty paths, orchestrator creates stubs

        # Step 3: Write use_cases.md (top 3 use cases)
        context2 = doc_files + [entities_file, spec_file]
        if not self._write_use_cases_file(use_cases_file, context2):
            return spec_file, use_cases_file  # return partial, orchestrator handles

        logger.info("[spec] default flow complete — spec.md + use_cases.md")
        return spec_file, use_cases_file

    # ── OpenSpec flow ────────────────────────────────────────────────────

    def _specify_openspec(self, docs_dir: Path) -> tuple[Path, Path]:
        doc_files = list(docs_dir.glob("*.md"))
        project_name = self._project_name()
        domain = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        change_name = f"initial-{domain}"

        openspec_root = self.workspace / "openspec"
        specs_dir = openspec_root / "specs" / domain
        change_dir = openspec_root / "changes" / change_name
        change_specs = change_dir / "specs" / domain

        for d in [specs_dir, change_dir, change_specs]:
            d.mkdir(parents=True, exist_ok=True)

        proposal_file = _ensure_file(change_dir / "proposal.md")
        delta_spec_file = _ensure_file(change_specs / "spec.md")
        design_file = _ensure_file(change_dir / "design.md")
        tasks_file = _ensure_file(change_dir / "tasks.md")

        # Resume: skip if proposal and delta spec both have content
        if _file_has_content(proposal_file) and _file_has_content(delta_spec_file):
            logger.info("[spec] OpenSpec proposal + spec exist — skipping (resume)")
            self.emit_file_written(proposal_file)
            self.emit_file_written(delta_spec_file)
            return proposal_file, delta_spec_file

        # Clear stale content
        proposal_file.write_text("")
        delta_spec_file.write_text("")

        # Step 1: Write proposal (why + what)
        if not self._write_openspec_proposal(proposal_file, doc_files, project_name):
            return proposal_file, delta_spec_file  # return empty paths, orchestrator creates stubs

        # Step 2: Write delta spec (requirements with scenarios)
        ctx = doc_files + [proposal_file]
        if not self._write_openspec_delta_spec(delta_spec_file, ctx, domain):
            return proposal_file, delta_spec_file  # return empty paths, orchestrator creates stubs

        # Copy delta spec to source-of-truth location
        sot_spec = specs_dir / "spec.md"
        sot_spec.write_text(delta_spec_file.read_text())
        self.emit_file_written(sot_spec)

        # Write stubs for downstream agents (architect, planner)
        self._write_stub_if_empty(design_file, self._design_stub(change_name))
        self._write_stub_if_empty(tasks_file, self._tasks_stub(change_name))

        # Write AGENTS.md navigation hint
        agents_md = openspec_root / "AGENTS.md"
        agents_md.write_text(
            "# OpenSpec\n\n"
            "open openspec/changes/ to find the active change.\n"
            "Read proposal.md → specs/ → design.md → tasks.md before coding.\n"
        )
        self.emit_file_written(agents_md)

        logger.info("[spec] openspec flow complete")
        return proposal_file, delta_spec_file

    # ── Internal step methods (default flow) ─────────────────────────────

    def _extract_entities(self, doc_files: list[Path], ai_dir: Path) -> Path | None:
        """Step 1: Extract key entities from docs — fast, focused."""
        entities_file = _ensure_file(ai_dir / "entities.md")
        entities_file.write_text("")  # clear stale

        logger.info("[spec] step 1/3 — extract entities (%d docs)", len(doc_files))

        result = self.run(
            message=(
                "Read the provided documents. List the main entities (nouns) this system works with.\n"
                "Format: one entity per line, with a 1-sentence description.\n"
                "Maximum 10 entities. No code. No markdown headers.\n"
                "Write the entity list to the file provided."
            ),
            read_files=doc_files,
            edit_files=[entities_file],
            timeout=180,
            log_callback=self.log_callback,
        )

        if not self._check_result(result, entities_file, "entities.md"):
            return None
        return entities_file

    def _write_spec_file(self, output_path: Path, context: list[Path]) -> bool:
        """Step 2: Write spec.md using entities as scaffold."""
        logger.info("[spec] step 2/3 — write spec.md")

        result = self.run(
            message=(
                "Write the project specification.\n\n"
                "Include these sections (adapt to the project type):\n"
                "## Problem\nOne paragraph describing what this solves.\n\n"
                "## Entities\nFor each entity: name, fields (name:type), key behaviour.\n\n"
                "## Interface\nDescribe how users/systems interact with this project.\n"
                "  - For APIs: endpoints, methods, request/response\n"
                "  - For CLI: commands, arguments, output format\n"
                "  - For libraries: public functions/classes, parameters, return values\n"
                "  - For GUIs: screens, user flows, interactions\n\n"
                "## Rules\nBullet list of system-wide rules (invariants).\n\n"
                "Keep it short. One sentence per point. No filler."
            ),
            read_files=context,
            edit_files=[output_path],
            timeout=1200,
            log_callback=self.log_callback,
        )

        return self._check_result(result, output_path, "spec.md")

    def _write_use_cases_file(self, output_path: Path, context: list[Path]) -> bool:
        """Step 3: Write 3 most important use cases."""
        logger.info("[spec] step 3/3 — write use cases")

        result = self.run(
            message=(
                "Write use_cases.md with the 3 most important use cases.\n\n"
                "Each use case format:\n"
                "## UC-N: title\n"
                "Given: ...\n"
                "When: ...\n"
                "Then: ...\n"
                "Error: what goes wrong and why.\n\n"
                "Keep each case to 6 lines max. Focus on the critical paths."
            ),
            read_files=context,
            edit_files=[output_path],
            timeout=1200,
            log_callback=self.log_callback,
        )

        return self._check_result(result, output_path, "use_cases.md")

    # ── Internal step methods (OpenSpec flow) ────────────────────────────

    def _write_openspec_proposal(
        self, output_path: Path, doc_files: list[Path], project_name: str
    ) -> bool:
        """Step 1: Write OpenSpec proposal (why + what)."""
        logger.info("[spec] openspec step 1/3 — proposal")

        result = self.run(
            message=(
                f"Write an OpenSpec proposal for project '{project_name}'.\n\n"
                "Sections:\n"
                "## Why\nOne paragraph — the problem.\n\n"
                "## What Changes\nBullet list of capabilities added.\n\n"
                "## Out of Scope\nBullet list of what is NOT included.\n\n"
                "Keep it under 200 words."
            ),
            read_files=doc_files,
            edit_files=[output_path],
            timeout=180,
            log_callback=self.log_callback,
        )

        return self._check_result(result, output_path, "proposal.md")

    def _write_openspec_delta_spec(
        self, output_path: Path, context: list[Path], domain: str
    ) -> bool:
        """Step 2: Write OpenSpec delta spec (requirements + scenarios)."""
        logger.info("[spec] openspec step 2/3 — delta spec")

        result = self.run(
            message=(
                f"Write an OpenSpec delta spec for domain '{domain}'.\n\n"
                "Format:\n"
                f"# Delta for {domain}\n\n"
                "## ADDED Requirements\n\n"
                "### Requirement: <name>\n"
                "The system SHALL <behaviour>.\n\n"
                "#### Scenario: <name>\n"
                "- GIVEN ...\n"
                "- WHEN ...\n"
                "- THEN ...\n\n"
                "Write 5-8 requirements. Keep each scenario to 3 lines."
            ),
            read_files=context,
            edit_files=[output_path],
            timeout=180,
            log_callback=self.log_callback,
        )

        return self._check_result(result, output_path, "delta spec.md")

    # ── Utilities ────────────────────────────────────────────────────────

    def _check_result(self, result: dict, file_path: Path, label: str) -> bool:
        """Validate that aider run succeeded and wrote content to file."""
        success = result.get("success", False)
        has_content = _file_has_content(file_path)

        logger.info("[spec] %s: success=%s, file_exists=%s, size=%d",
                     label, success, has_content,
                     file_path.stat().st_size if has_content else 0)

        if not success:
            logger.error("[spec] %s failed — aider exit code: %d",
                         label, result.get("exit_code", -1))
            stderr = result.get("stderr", "")[:300]
            if stderr:
                logger.error("[spec] %s stderr: %s", label, stderr)

        if not has_content:
            logger.error("[spec] %s — file empty or not created", label)
            if file_path.exists():
                file_path.unlink()
            return False

        self.emit_file_written(file_path)
        return True

    def _write_stub_if_empty(self, path: Path, content: str) -> None:
        """Write stub content if file is empty (for downstream agent placeholders)."""
        if not _file_has_content(path):
            path.write_text(content)
            self.emit_file_written(path)

    @staticmethod
    def _design_stub(change_name: str) -> str:
        return (
            f"# Design: {change_name}\n\n"
            "_Architect fills this._\n\n"
            "## Approach\n\n## Key Decisions\n\n## Component Changes\n"
        )

    @staticmethod
    def _tasks_stub(change_name: str) -> str:
        return (
            f"# Tasks: {change_name}\n\n"
            "_Planner fills this._\n\n"
            "- [ ] 1.1 \n- [ ] 1.2 \n"
        )

    def _project_name(self) -> str:
        """Read project name from workspace.yaml, fallback to 'project'."""
        try:
            import yaml
            ws = self.workspace / "workspace.yaml"
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
