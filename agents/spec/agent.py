"""
spec/agent.py — Spec agent.

Responsible for the specification phase only.
Reads input docs, extracts entities, writes spec.md and use_cases.md.

Design principles:
  - Small incremental steps — each step is one focused aider call
  - Non-critical failures → auto-retry via orchestrator (non-blocking)
  - Critical failures / hallucination → wait for user input (blocking)
  - Clear step reporting with progress (N/M)
"""

import logging
import re
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else "# Spec Agent"


def _ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
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
        self._step_results = []
        self._retry_count = {}  # label → retry count

    # ── Public entry point ────────────────────────────────────────────────

    def specify(self, docs_dir: Path) -> tuple[Path, Path]:
        """
        Generate specification documents from requirements docs.

        Returns:
            Tuple of (spec_file, use_cases_file) paths.
            Always returns Path objects (possibly empty files on failure).
        """
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
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
        """Return per-step results for reporting to orchestrator."""
        return list(self._step_results)

    # ── Step runner with smart failure classification ─────────────────────

    def _run_step(self, message: str, read_files: list[Path],
                  output_path: Path, label: str,
                  timeout: int = 180) -> dict:
        """
        Run a single aider step with auto-retry for non-critical failures.

        Flow:
          1. Execute step
          2. If failed → classify severity
          3. If transient/refusal → auto-retry (non-blocking, up to MAX_AUTO_RETRIES)
          4. If hallucination/critical → mark needs_user_input for blocking
        """
        MAX_AUTO_RETRIES = 2  # Non-critical auto-retries before escalating to user

        attempt = self._retry_count.get(label, 0) + 1
        self._retry_count[label] = attempt

        logger.info("[spec] step %d: %s", attempt, label)

        result = self.run_stream_to_file(
            message=message, read_files=read_files, output_path=output_path,
        )

        success = result.get("success", False) and _file_has_content(output_path)

        if not success:
            classification = self._classify_failure(result, output_path, label)
            result["severity"] = classification["severity"]
            result["auto_retry"] = classification["auto_retry"]
            result["needs_user_input"] = classification["needs_user_input"]
            result["retry_count"] = attempt
            result["escalated_message"] = classification.get("escalated_message", "")
            result["read_files"] = read_files
            result["timeout"] = timeout

            # Auto-retry for transient/refusal failures (non-blocking)
            if classification["auto_retry"] and attempt <= MAX_AUTO_RETRIES:
                logger.info("[spec] auto-retrying '%s' (attempt %d/%d, severity=%s)",
                            label, attempt + 1, MAX_AUTO_RETRIES + 1, classification["severity"])
                # Retry with escalated message if available
                retry_msg = classification.get("escalated_message") or message
                return self._run_step(retry_msg, read_files, output_path, label, timeout)

            # Auto-retries exhausted → escalate to user if critical/hallucination
            if classification["needs_user_input"]:
                result["needs_user_input"] = True
        else:
            result["severity"] = "success"
            result["auto_retry"] = False
            result["needs_user_input"] = False
            result["retry_count"] = attempt

        step_info = {
            "label": label,
            "success": success,
            "file": str(output_path),
            "exit_code": result.get("exit_code", -1),
            "severity": result.get("severity", "unknown"),
            "attempt": attempt,
        }
        self._step_results.append(step_info)

        if success:
            logger.info("[spec] step OK: %s", label)
        else:
            logger.warning("[spec] step FAILED [%s]: %s (attempt %d)",
                           result.get("severity", "?"), label, attempt)

        return result

    def _classify_failure(self, result: dict, output_path: Path, label: str) -> dict:
        """
        Classify failure into severity levels.

        - "transient" → aider crashed/timed out → AUTO-RETRY
        - "refusal"   → LLM refused to write content → AUTO-RETRY with escalated prompt
        - "hallucination" → file has wrong content (comments only, placeholders, gibberish) → WAIT FOR USER
        - "critical"  → no output, completely empty after success → WAIT FOR USER
        """
        exit_code = result.get("exit_code", -1)
        stderr = result.get("stderr", "")
        # Skip reading if path is a directory or doesn't exist
        content = ""
        if output_path.exists() and output_path.is_file():
            content = output_path.read_text()

        # 1. Transient failure (aider crash, timeout, connection error)
        if exit_code != 0:
            if exit_code == -1 or "timeout" in stderr.lower() or exit_code >= 128:
                return {
                    "severity": "transient",
                    "auto_retry": True,
                    "needs_user_input": False,
                    "escalated_message": "",
                }

        # 2. Hallucination detection (file exists but content is wrong)
        if _file_has_content(output_path):
            if self._looks_like_hallucination(content, label):
                return {
                    "severity": "hallucination",
                    "auto_retry": False,
                    "needs_user_input": True,
                    "escalated_message": "",
                }

        # 3. LLM refusal (aider succeeded but wrote minimal/empty content)
        if exit_code == 0 and not _file_has_content(output_path):
            return {
                "severity": "refusal",
                "auto_retry": True,
                "needs_user_input": False,
                "escalated_message": (
                    "CRITICAL: You MUST create actual substantive content in the file. "
                    "Do NOT write placeholder comments, empty sections, or stubs. "
                    "Write real, detailed specification content now."
                ),
            }

        # 4. Critical failure (unknown error)
        return {
            "severity": "critical",
            "auto_retry": False,
            "needs_user_input": True,
            "escalated_message": "",
        }

    def _looks_like_hallucination(self, content: str, label: str) -> bool:
        """
        Detect if generated content looks like hallucination rather than real content.

        Signs of hallucination:
        - Only comments/placeholders (no substantive content)
        - Extremely short relative to expected output
        - Contains "TODO", "placeholder", "stub", "fill this in"
        - Only markdown headers with no body text
        - Repeated patterns that look like template filling
        """
        if not content or len(content.strip()) < 20:
            return True

        lines = content.splitlines()

        # Check for placeholder/TODO density
        placeholder_patterns = [
            r"TODO", r"placeholder", r"stub", r"fill.*in", r"coming soon",
            r"auto-generat", r"skipped\b", r"incomplete\b", r"abort\b",
            r"not (yet|currently) (implemented|available|generated)",
        ]
        placeholder_lines = 0
        for line in lines:
            for pattern in placeholder_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    placeholder_lines += 1
                    break

        # If >40% of lines are placeholders, likely hallucination
        if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
            return True

        # If content is very short (under 100 chars for a spec file), suspicious
        if len(content.strip()) < 100:
            return True

        # If file is only headers (lines starting with #) and no body text
        header_only = all(line.startswith("#") or line.strip() == "" for line in lines)
        if header_only:
            return True

        return False

    # ── User interaction (only for critical/hallucination) ────────────────

    def _ask_user_retry(self, step_label: str, error_detail: str, severity: str) -> str:
        """Ask user what to do after a critical or hallucination failure."""
        severity_label = severity.upper()
        reply = self.ask(
            question=f"Step '{step_label}' failed [{severity_label}]: {error_detail}. What should I do?",
            suggestions=[
                "Retry with more explicit instructions",
                "Skip this step and continue",
                "Abort — I'll fix this manually",
            ],
            timeout=600,  # 10 minutes for user to respond
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
        """Return whatever was generated so far."""
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

        if _file_has_content(proposal_file) and _file_has_content(delta_spec_file):
            logger.info("[spec] OpenSpec proposal + spec exist — skipping (resume)")
            self.emit_file_written(proposal_file)
            self.emit_file_written(delta_spec_file)
            return proposal_file, delta_spec_file

        proposal_file.write_text("")
        delta_spec_file.write_text("")

        if not self._step_write_proposal(proposal_file, doc_files, project_name):
            return proposal_file, delta_spec_file

        ctx = doc_files + [proposal_file]
        if not self._step_write_delta_spec(delta_spec_file, ctx, domain):
            return proposal_file, delta_spec_file

        sot_spec = specs_dir / "spec.md"
        sot_spec.write_text(delta_spec_file.read_text())
        self.emit_file_written(sot_spec)

        self._write_stub_if_empty(design_file, self._design_stub(change_name))
        self._write_stub_if_empty(tasks_file, self._tasks_stub(change_name))

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

        return self._handle_step_result(result, entities_file, "extract entities",
                                        stub_content="# Entities\n_No entities extracted._\n")

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

        return self._handle_step_result_bool(result, output_path, "write spec.md",
                                             stub_content="# Specification\n_Auto-generation skipped._\n")

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

        return self._handle_step_result_bool(result, output_path, "write use_cases.md",
                                             stub_content="# Use Cases\n_Auto-generation skipped._\n")

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

        return self._handle_step_result_bool(result, output_path, "write proposal",
                                             stub_content=f"# Proposal: {project_name}\n_Auto-generation skipped._\n")

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

        return self._handle_step_result_bool(result, output_path, "write delta spec",
                                             stub_content=f"# Delta for {domain}\n_Auto-generation skipped._\n")

    # ── Step result handling ─────────────────────────────────────────────

    def _handle_step_result(self, result: dict, output_path: Path,
                            label: str, stub_content: str = None) -> Path | None:
        """
        Handle step result and decide next action.

        - auto_retry=True → return None (orchestrator will re-dispatch)
        - needs_user_input=True → ask user, act on decision
        - success → return path
        """
        if result.get("success"):
            return output_path

        # Non-critical failure → signal orchestrator to auto-retry
        if result.get("auto_retry"):
            logger.info("[spec] auto-retry requested for '%s' (severity=%s)",
                        label, result.get("severity", "?"))
            return None  # Orchestrator will re-dispatch

        # Critical/hallucination → block for user input
        if result.get("needs_user_input"):
            decision = self._ask_user_retry(label, result.get("stderr", "no output"),
                                            result.get("severity", "critical"))
            if "abort" in decision:
                return None
            if "skip" in decision:
                if stub_content:
                    output_path.write_text(stub_content)
                return output_path
            # retry with escalated message
            escalated = result.get("escalated_message", "")
            if not escalated:
                escalated = f"CRITICAL: Complete the '{label}' step with real content."
            result2 = self._run_step(
                escalated, result.get("read_files", []), output_path,
                f"{label} (user-retry)", timeout=result.get("timeout", 180),
            )
            if result2.get("success"):
                return output_path
            # Second attempt also failed — create stub
            if stub_content:
                output_path.write_text(stub_content)
            return None

        return None  # Unknown failure — return None for orchestrator

    def _handle_step_result_bool(self, result: dict, output_path: Path,
                                  label: str, stub_content: str = None) -> bool:
        """Same as _handle_step_result but returns bool."""
        r = self._handle_step_result(result, output_path, label, stub_content)
        return r is not None

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
