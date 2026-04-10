"""
spec/agent.py — Spec agent.

Responsible for the specification phase only.
Reads input docs, extracts entities, writes spec.md and use_cases.md.

Design principles:
  - Small incremental steps — each step is one focused aider call
  - NO automatic retries — failures are reported, user decides
  - Clear step reporting with progress (N/M)
  - User-controlled retry via clarification system
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
    """Ensure file exists with parent directories, matching docs_agent pattern."""
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
        self._step_results = []  # Track per-step results

    # ── Public entry point (called by orchestrator) ───────────────────────

    def specify(self, docs_dir: Path) -> tuple[Path, Path]:
        """
        Generate specification documents from requirements docs.

        Args:
            docs_dir: Directory containing input requirement/markdown docs.

        Returns:
            Tuple of (spec_file, use_cases_file) paths.
            Always returns Path objects (possibly empty files on failure).
        """
        self.report_status("running")
        self._step_results = []
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

    def get_step_results(self) -> list[dict]:
        """Return per-step results for reporting to user/orchestrator."""
        return list(self._step_results)

    # ── Step runner: single-shot, no auto-retry ──────────────────────────

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str,
                  timeout: int = 180) -> dict:
        """Run a single aider step. NO automatic retry. Returns result dict."""
        logger.info("[spec] step: %s", label)

        result = self.run(
            message=message,
            read_files=read_files,
            edit_files=[output_path],
            timeout=timeout,
            log_callback=self.log_callback,
        )

        success = result.get("success", False) and _file_has_content(output_path)
        step_info = {
            "label": label,
            "success": success,
            "file": str(output_path),
            "exit_code": result.get("exit_code", -1),
        }
        self._step_results.append(step_info)

        if not success:
            logger.warning("[spec] step FAILED: %s (exit=%s)",
                           label, result.get("exit_code", "?"))
        else:
            logger.info("[spec] step OK: %s", label)

        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        """Ask user what to do after a step failure."""
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=[
                "Retry this step",
                "Skip this step and continue",
                "Abort the specification phase",
            ],
            timeout=300,
        )
        return (reply or "").lower().strip()

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

        # Step 1: Extract entities
        entities_file = self._step_extract_entities(doc_files, ai_dir)
        if entities_file is None:
            # User chose to skip or abort
            return self._return_partial_or_empty(spec_file, use_cases_file)

        # Step 2: Write spec.md
        context = doc_files + [entities_file]
        if not self._step_write_spec_file(spec_file, context):
            return self._return_partial_or_empty(spec_file, use_cases_file)

        # Step 3: Write use_cases.md
        context2 = doc_files + [entities_file, spec_file]
        if not self._step_write_use_cases_file(use_cases_file, context2):
            return self._return_partial_or_empty(spec_file, use_cases_file)

        logger.info("[spec] default flow complete — spec.md + use_cases.md")
        return spec_file, use_cases_file

    def _return_partial_or_empty(self, spec_file: Path, uc_file: Path) -> tuple[Path, Path]:
        """Return whatever was generated so far. Orchestrator creates stubs if needed."""
        self.emit_file_written(spec_file)
        if _file_has_content(uc_file):
            self.emit_file_written(uc_file)
        return spec_file, uc_file

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

        # Step 1: Write proposal
        if not self._step_write_proposal(proposal_file, doc_files, project_name):
            return proposal_file, delta_spec_file

        # Step 2: Write delta spec
        ctx = doc_files + [proposal_file]
        if not self._step_write_delta_spec(delta_spec_file, ctx, domain):
            return proposal_file, delta_spec_file

        # Copy delta spec to source-of-truth
        sot_spec = specs_dir / "spec.md"
        sot_spec.write_text(delta_spec_file.read_text())
        self.emit_file_written(sot_spec)

        # Write stubs for downstream agents
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

    # ── Individual step methods (default flow) ───────────────────────────

    def _step_extract_entities(self, doc_files: list[Path], ai_dir: Path) -> Path | None:
        """Step 1: Extract key entities from docs."""
        entities_file = _ensure_file(ai_dir / "entities.md")
        entities_file.write_text("")

        result = self._run_step(
            message=(
                "Read the provided documents. List the main entities (nouns) this system works with.\n"
                "Format: one entity per line, with a 1-sentence description.\n"
                "Maximum 10 entities. No code. No markdown headers.\n"
                "Write the entity list to the file provided."
            ),
            read_files=doc_files,
            output_path=entities_file,
            label="1/3 — extract entities",
            timeout=180,
        )

        if not result.get("success"):
            decision = self._ask_user_retry("extract entities", "aider could not extract entities")
            if "abort" in decision:
                return None
            if "skip" in decision:
                # Create minimal entities file so we can continue
                entities_file.write_text("# Entities\n_No entities extracted automatically._\n")
                return entities_file
            # "retry" — fall through to single retry
            result = self._run_step(
                message=(
                    "CRITICAL: Read the documents and list the main entities.\n"
                    "One per line with a short description. Max 10. Write to the file."
                ),
                read_files=doc_files,
                output_path=entities_file,
                label="1/3 — extract entities (retry)",
                timeout=180,
            )
            if not result.get("success"):
                entities_file.write_text("# Entities\n_Retry also failed._\n")
                return entities_file

        return entities_file

    def _step_write_spec_file(self, output_path: Path, context: list[Path]) -> bool:
        """Step 2: Write spec.md using entities as scaffold."""
        result = self._run_step(
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
            output_path=output_path,
            label="2/3 — write spec.md",
            timeout=1200,
        )

        if not result.get("success"):
            decision = self._ask_user_retry("write spec.md", "aider could not write spec.md")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text("# Specification\n_Auto-generation skipped._\n")
                return True
            # retry
            result = self._run_step(
                message=(
                    "CRITICAL: Write the project specification with all required sections.\n"
                    "You MUST create actual content — no placeholders or stubs."
                ),
                read_files=context,
                output_path=output_path,
                label="2/3 — write spec.md (retry)",
                timeout=1200,
            )
            return result.get("success", False) or _file_has_content(output_path)

        return True

    def _step_write_use_cases_file(self, output_path: Path, context: list[Path]) -> bool:
        """Step 3: Write 3 most important use cases."""
        result = self._run_step(
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
            output_path=output_path,
            label="3/3 — write use_cases.md",
            timeout=1200,
        )

        if not result.get("success"):
            decision = self._ask_user_retry("write use_cases.md", "aider could not write use cases")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text("# Use Cases\n_Auto-generation skipped._\n")
                return True
            # retry
            result = self._run_step(
                message=(
                    "CRITICAL: Write 3 use cases in the specified format.\n"
                    "You MUST create actual content — no placeholders."
                ),
                read_files=context,
                output_path=output_path,
                label="3/3 — write use_cases.md (retry)",
                timeout=1200,
            )
            return result.get("success", False) or _file_has_content(output_path)

        return True

    # ── Individual step methods (OpenSpec flow) ──────────────────────────

    def _step_write_proposal(self, output_path: Path, doc_files: list[Path],
                             project_name: str) -> bool:
        """Step 1: Write OpenSpec proposal."""
        result = self._run_step(
            message=(
                f"Write an OpenSpec proposal for project '{project_name}'.\n\n"
                "Sections:\n"
                "## Why\nOne paragraph — the problem.\n\n"
                "## What Changes\nBullet list of capabilities added.\n\n"
                "## Out of Scope\nBullet list of what is NOT included.\n\n"
                "Keep it under 200 words."
            ),
            read_files=doc_files,
            output_path=output_path,
            label="1/2 — write proposal",
            timeout=180,
        )

        if not result.get("success"):
            decision = self._ask_user_retry("write proposal", "aider could not write proposal")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text(f"# Proposal: {project_name}\n_Auto-generation skipped._\n")
                return True
            # retry
            result = self._run_step(
                message=(
                    f"CRITICAL: Write an OpenSpec proposal for '{project_name}'. "
                    "Include Why, What Changes, Out of Scope. Under 200 words."
                ),
                read_files=doc_files,
                output_path=output_path,
                label="1/2 — write proposal (retry)",
                timeout=180,
            )
            return result.get("success", False) or _file_has_content(output_path)

        return True

    def _step_write_delta_spec(self, output_path: Path, context: list[Path],
                               domain: str) -> bool:
        """Step 2: Write OpenSpec delta spec."""
        result = self._run_step(
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
            output_path=output_path,
            label="2/2 — write delta spec",
            timeout=180,
        )

        if not result.get("success"):
            decision = self._ask_user_retry("write delta spec", "aider could not write delta spec")
            if "abort" in decision:
                return False
            if "skip" in decision:
                output_path.write_text(f"# Delta for {domain}\n_Auto-generation skipped._\n")
                return True
            # retry
            result = self._run_step(
                message=(
                    f"CRITICAL: Write an OpenSpec delta spec for '{domain}'. "
                    "Include 5-8 requirements with scenarios."
                ),
                read_files=context,
                output_path=output_path,
                label="2/2 — write delta spec (retry)",
                timeout=180,
            )
            return result.get("success", False) or _file_has_content(output_path)

        return True

    # ── Utilities ────────────────────────────────────────────────────────

    def _write_stub_if_empty(self, path: Path, content: str) -> None:
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
