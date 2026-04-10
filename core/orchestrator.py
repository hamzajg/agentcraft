"""
orchestrator.py — autonomous agent loop with RAG, local LLM, skills, and frameworks.

Startup sequence:
  1. RagClient.setup()         — open/create LanceDB store
  2. Index docs/               — collection="docs"
  3. Index legacy source/      — collection="legacy"  (if workspace.yaml legacy: set)
  4. Spec phase                — reads docs, writes spec.md + use_cases.md → indexed
  5. Architect                 — reads spec → iterations.json
  6. For each iteration:
       Planner → tasks
       For each task: worker → immediate review → rework if needed
       Integration tests (if LLM decides they're needed) → indexed
       Reviewer holistic pass
  7. CI/CD (if LLM decides it's needed)
  8. RagClient.close()         — clean up temp files

Workflow principles:
  - Small iterations (1-3 tasks each)
  - Immediate feedback after every task (not deferred)
  - Adaptive planning (LLM decides scope, CI/CD, integration tests)
  - Walking skeleton first, then increment
"""

import json
import logging
import time
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.bus import AgentBus
from core.event_stream import ES
from core.control import CC, BuildStopped, BuildPaused
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx

from agents import (
    SpecAgent, ArchitectAgent, PlannerAgent,
    TestDevAgent, BackendDevAgent, ConfigAgent, DocsAgent,
    IntegrationTestAgent, ReviewerAgent, CiCdAgent, SupervisorAgent,
)
from core.framework_loader import FrameworkLoader
from core.skill_runner import SkillRunner

logger = logging.getLogger(__name__)


# ── Run log data classes ──────────────────────────────────────────────────────

@dataclass
class TaskResult:
    task_id: str; file: str; agent: str
    approved: bool; attempts: int
    final_verdict: str; duration_s: float


@dataclass
class IterationResult:
    iteration_id: int; phase: int; name: str; approved: bool
    task_results: list = field(default_factory=list)
    integration_tests_written: bool = False
    duration_s: float = 0.0
    delivered_artifacts: list = field(default_factory=list)
    retrospective_notes: str = ""


@dataclass
class RunLog:
    started_at: str; model: str; framework_id: Optional[str]
    docs_dir: str; workspace: str
    rag_enabled: bool = False
    spec_produced: bool = False
    iterations: list = field(default_factory=list)
    completed: bool = False
    total_duration_s: float = 0.0


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Orchestrates autonomous agent teams with an iterative delivery model.

    Each iteration is small (1-3 tasks), gets immediate review, and delivers
    working artifacts. After each phase, the LLM decides whether to continue
    adapting the plan or wrap up.
    """

    WORKER_MAP = {
        "test_dev":    TestDevAgent,
        "backend_dev": BackendDevAgent,
        "config_agent": ConfigAgent,
        "docs_agent":  DocsAgent,
    }

    def __init__(
        self,
        model: str,
        docs_dir: Path,
        workspace: Path,
        framework_id: Optional[str] = None,
        max_rework_per_task: int = 3,
        max_rework_per_iter: int = 2,
        start_from_iteration: int = 1,
        skip_spec: bool = False,
        rag_config: Optional[dict] = None,
        legacy_dirs: Optional[list[Path]] = None,
        parallel: bool = False,
    ):
        self.model               = model
        self.docs_dir            = docs_dir
        self.workspace           = workspace
        self.framework_id        = framework_id
        self.max_rework_per_task = max_rework_per_task
        self.max_rework_per_iter = max_rework_per_iter
        self.start_from          = start_from_iteration
        self.skip_spec           = skip_spec
        self.rag_config          = rag_config or {}
        self.legacy_dirs         = legacy_dirs or []
        self.parallel            = parallel

        self.log_client = httpx.Client()
        self.log_callback = lambda agent_id, msg: self._send_log(agent_id, msg)

        # High-level updates via comms client
        from comms.clarification_client import ClarificationClient
        self._comms = ClarificationClient(agent_id="orchestrator", task_id="bootstrap")

        # Configure EventStream and ControlChannel for remote mode if URL is present
        import os
        comms_url = os.environ.get("COMMS_SERVER_URL", "http://localhost:7000")
        if comms_url:
            from core.event_stream import ES
            from core.control import CC
            ES.set_remote(comms_url)
            CC.set_remote(comms_url)

        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / ".ai").mkdir(exist_ok=True)

        # Load architecture from workspace config
        self.architecture = self._load_architecture()

        # Framework loader
        self.fw = FrameworkLoader(framework_id)

        # RAG client (lazy — set up in run())
        self._rag = None
        self._llm = None

        # Singleton agents (constructed after RAG/LLM ready)
        self._agents_built = False

        self.run_log = RunLog(
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            model=model, framework_id=framework_id,
            docs_dir=str(docs_dir), workspace=str(workspace),
        )

    def _load_architecture(self) -> str:
        """Load architecture style from workspace.yaml."""
        try:
            ws_file = self.workspace.parent / "workspace.yaml"
            if ws_file.exists():
                import yaml
                ws = yaml.safe_load(ws_file.read_text()) or {}
                arch = ws.get("project", {}).get("architecture", "monolith")
                if isinstance(arch, str):
                    logger.info("[orchestrator] Architecture: %s", arch)
                    return arch
        except Exception as e:
            logger.warning("Failed to load architecture: %s", e)
        return "monolith"

    def _log(self, message: str):
        """Send log message to comms server if callback is set."""
        if self.log_callback:
            try:
                self.log_callback("orchestrator", message)
            except Exception:
                pass
        logger.info("[orchestrator] %s", message)

    def _send_log(self, agent_id: str, message: str):
        """Send log message to comms server."""
        try:
            import os
            comms_url = os.environ.get("COMMS_SERVER_URL", "http://localhost:7000")
            with httpx.Client(timeout=5) as client:
                resp = client.post(f"{comms_url}/api/log", json={
                    "agent_id": agent_id,
                    "message": message,
                })
                resp.raise_for_status()
        except Exception as e:
            logger.warning("[orchestrator] failed to send log to comms: %s", e)

    def _docs_exist(self) -> bool:
        """Check if docs directory has any files."""
        docs_dir = self.workspace.parent / "docs"
        if not docs_dir.exists():
            return False
        return any(docs_dir.iterdir())

    def _check_empty_docs(self) -> list[dict]:
        """Check for empty documents and return list of {file, responsible_agent}."""
        empty_docs = []
        responsible_agents = {
            "spec.md": "@spec",
            "use_cases.md": "@spec",
            "architecture.md": "@architect",
            "plan.md": "@planner",
        }
        for md_file in self.docs_dir.glob("*.md"):
            if md_file.stat().st_size < 50:
                agent = responsible_agents.get(md_file.name, "@supervisor")
                empty_docs.append({
                    "file": str(md_file.relative_to(self.workspace.parent)),
                    "responsible": agent,
                })
        return empty_docs

    def _supervisor_status(self, message: str):
        """Post status message from supervisor to chat."""
        try:
            if hasattr(self, 'supervisor') and self.supervisor:
                self.supervisor.info(message)
            else:
                self._comms.info(message)
        except Exception as e:
            logger.warning("[orchestrator] supervisor status failed: %s", e)

    def _confirm_architecture_session(self) -> bool:
        """Use LLM to decide if architecture session is needed."""
        docs_exist = self._docs_exist()
        
        prompt = f"""You are the Orchestrator deciding if an architecture session is needed.

Current state:
- Docs exist: {docs_exist}
- Workspace: {self.workspace}

Do we need to start an architecture collaboration session?

Consider:
1. If docs are missing or insufficient, we need a session to define the project
2. If docs exist and seem complete, we can skip the session
3. Architecture session involves Supervisor and Architect gathering vision and generating docs

Respond with JSON:
{{
  "need_session": true/false,
  "reason": "brief explanation"
}}"""

        try:
            # Use LLM to decide
            result = {"output": self._llm.generate(prompt=prompt)}
            
            # Parse JSON response
            import json
            import re
            output = result.get("output", "")
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                decision = json.loads(json_match.group(1))
            else:
                decision = json.loads(output)
            
            need_session = decision.get("need_session", not docs_exist)  # fallback to docs_exist
            reason = decision.get("reason", "")
            
            self._log(f"LLM decision on architecture session: {'needed' if need_session else 'not needed'} - {reason}")
            
            return need_session
            
        except Exception as e:
            self._log(f"LLM decision failed: {e}, falling back to docs check")
            logger.warning("[orchestrator] LLM arch session decision failed: %s", e)
            return not docs_exist  # fallback

    # ── Agent factory ─────────────────────────────────────────────────────────

    def _build_agents(self):
        if self._agents_built:
            return
        self.supervisor       = self._make(SupervisorAgent)
        self.spec_agent       = self._make(SpecAgent)
        self.architect        = self._make(ArchitectAgent)
        self.planner          = self._make(PlannerAgent)
        self.reviewer         = self._make(ReviewerAgent)
        self.integration_test = self._make(IntegrationTestAgent)
        self.cicd             = self._make(CiCdAgent)
        self._agents_built    = True

    def _make(self, AgentClass, task_id=None, iteration_id=None):
        role = getattr(AgentClass, "_role", None) or \
               AgentClass.__name__.lower().replace("agent", "")
        ctx  = self.fw.for_agent(role)
        agent = AgentClass(
            model=self.model,
            workspace=self.workspace,
            system_prompt=ctx.system_prompt,
            skills=ctx.skills,
            framework_id=self.framework_id,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=self._rag,
            llm_client=self._llm,
        )
        agent.log_callback = self.log_callback
        return agent

    # ── Main run ──────────────────────────────────────────────────────────────

    def prepare(self) -> None:
        """Prepare the orchestrator for execution (setup phase)."""
        self._banner("AGENT TEAM PREPARATION")

        # ── Phase: RAG setup ──────────────────────────────────────────────────
        self._setup_event_store()
        self._setup_rag()
        self._setup_llm()
        AgentBus.reset()          # fresh bus per build run
        self._build_agents()
        self._register_all_on_bus()
        self.run_log.rag_enabled = self._rag is not None and self._rag.enabled
        self._save_log()

        self._banner("PREPARATION COMPLETE")

    def run(self) -> RunLog:
        total_start = time.time()

        # ── Setup event store (persistent) ────────────────────────────────
        self._setup_event_store()

        # ── Check for existing build state (resume detection) ────────────
        stored_state = self._load_build_state()
        if stored_state and self.start_from == 1:
            status = stored_state.get("build_status", "idle")
            if status in ("running", "paused", "stopped", "error"):
                resume_from = stored_state.get("resume_from_iteration", 1)
                if resume_from > 1:
                    self._log(f"Detected previous {status} build — resuming from iteration {resume_from}")
                    self.start_from = resume_from
                    self._supervisor_status(f"Resuming from iteration {resume_from}. Previous build was {status}.")
            elif status == "done":
                self._log("Previous build completed — starting fresh")
                self._supervisor_status("Previous build completed. Starting fresh run.")
            # idle: no previous build, normal start

        self._banner("AUTONOMOUS AGENT TEAM — START")
        ES.emit("build_started", {
            "model": self.model, "framework": self.framework_id or "none",
        })

        # ── Phase: RAG setup ──────────────────────────────────────────────────
        self._setup_rag()
        self._setup_llm()
        AgentBus.reset()          # fresh bus per build run
        CC.reset()                # fresh control flags
        ES.clear()                # clear in-memory ring (file store persists)
        self._build_agents()
        self._register_all_on_bus()
        self.run_log.rag_enabled = self._rag is not None and self._rag.enabled
        self._save_log()

        # Check for empty documents and notify responsible agents
        empty_docs = self._check_empty_docs()
        if empty_docs:
            for doc in empty_docs:
                self._supervisor_status(
                    f"Document '{doc['file']}' is empty. {doc['responsible']} please complete this task."
                )

        # ── Phase 0 Check: Empty docs collaboration ──────────────────────────
        phase_0_docs_empty = not any(self.docs_dir.glob("*.md"))
        if phase_0_docs_empty:
            logger.info("[orchestrator] docs/ is empty — supervisor deciding phase 0 strategy")
            
            # Get project type from workspace config
            ws = {}
            try:
                import yaml
                ws_file = self.workspace.parent / "workspace.yaml"
                if ws_file.exists():
                    ws = yaml.safe_load(ws_file.read_text()) or {}
            except:
                pass
            
            project_type = ws.get("project", {}).get("type", "greenfield")
            architecture = ws.get("project", {}).get("architecture", "monolith")
            
            # Confirm with the human before starting the architecture session
            if self.start_from == 1 and not self._confirm_architecture_session():
                logger.info("[orchestrator] architecture session postponed by user")
                self.run_log.completed = True
                self.run_log.total_duration_s = round(time.time() - total_start, 1)
                self._save_log()
                self._banner("ARCHITECTURE SESSION POSTPONED")
                return self.run_log
            
            # Use LLM to decide phase 0 strategy
            phase_0_prompt = f"""You are the Orchestrator deciding Phase 0 strategy.

Project details:
- Project type: {project_type}
- Architecture: {architecture}
- Workspace: {self.workspace}

Decide the Phase 0 strategy based on project type.

For legacy projects: scan existing codebase and generate reference docs.
For greenfield projects: collaborate with user to define vision and generate initial docs.

Respond with JSON matching this structure:
{{
  "strategy": "legacy_scan" or "greenfield_clarify",
  "action": "brief description",
  "agents_involved": ["supervisor", "architect", ...],
  "next_steps": ["step1", "step2", ...],
  "architecture_notes": ["note1", "note2", ...]
}}"""

            try:
                result = {"output": self._llm.generate(prompt=phase_0_prompt)}
                
                # Parse response
                import json
                import re
                output = result.get("output", "")
                json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
                if json_match:
                    phase_0_decision = json.loads(json_match.group(1))
                else:
                    phase_0_decision = json.loads(output)
                
                self._log(f"LLM decided phase 0 strategy: {phase_0_decision.get('strategy')}")
                
            except Exception as e:
                self._log(f"LLM phase 0 decision failed: {e}, using fallback")
                logger.warning("[orchestrator] LLM phase 0 decision failed: %s", e)
                
                # Fallback based on project_type
                if project_type == "legacy":
                    phase_0_decision = {
                        "strategy": "legacy_scan",
                        "action": "Scan existing codebase and generate reference documentation",
                        "agents_involved": ["docs_agent"],
                        "next_steps": ["Scan legacy source", "Index in RAG", "Generate reference docs"],
                        "architecture_notes": []
                    }
                else:
                    phase_0_decision = {
                        "strategy": "greenfield_clarify",
                        "action": "Supervisor defines phase 0 plan and collaborates with architect for clarification",
                        "agents_involved": ["supervisor", "architect"],
                        "next_steps": ["Define clarification plan", "Architect asks user", "Generate docs"],
                        "architecture_notes": []
                    }
            
            if self.start_from == 1:
                self._banner("PHASE 0 — COLLABORATION")
                self._comms.info("Starting Phase 0: Documentation & Collaboration")
                ES.emit("phase_started", {"phase": 0})
            try:
                phase0_start = time.time()
                if phase_0_decision["strategy"] == "legacy_scan":
                    # Legacy project: scan existing source and generate reference docs
                    logger.info("[orchestrator] PHASE 0: legacy scanning and reference docs")
                    
                    # Have DocsAgent scan legacy code and generate reference docs
                    docs_agent = self._make(DocsAgent)
                    docs_agent.log_callback = self.log_callback
                    legacy_sources = ws.get("project", {}).get("legacy_source_dirs", ["src"])
                    
                    legacy_paths = []
                    for src in legacy_sources:
                        p = self.workspace.parent / src
                        if p.exists():
                            legacy_paths.append(p)
                    
                    if legacy_paths:
                        # Index legacy code in RAG if enabled
                        if self._rag and self._rag.enabled:
                            for src_path in legacy_paths:
                                logger.info("[orchestrator] indexing legacy source: %s", src_path)
                                # Scan all common source file types
                                source_extensions = [
                                    "*.py", "*.java", "*.ts", "*.tsx", "*.js", "*.jsx",
                                    "*.go", "*.rs", "*.rb", "*.cs", "*.cpp", "*.c", "*.h",
                                    "*.kt", "*.swift", "*.scala", "*.php", "*.sh",
                                    "*.yaml", "*.yml", "*.json", "*.toml", "*.xml",
                                ]
                                for ext in source_extensions:
                                    for src_file in src_path.rglob(ext):
                                        self._rag.ingest_file(src_file, "legacy")
                        
                        # Generate reference docs from legacy code
                        logger.info("[orchestrator] generating reference docs from legacy code")
                        docs_agent.generate_reference_docs(self.docs_dir, legacy_paths)
                    
                    logger.info("[orchestrator] phase 0 legacy scanning complete")
                    
                else:  # greenfield_clarify
                    # Greenfield project: supervisor defines plan, architect collaborates with user for specs
                    logger.info("[orchestrator] PHASE 0: greenfield clarification with supervisor-architect collaboration")
                    
                    # Supervisor executes phase 0 plan using architect for clarification
                    workspace_config = {
                        "docs_dir": str(self.docs_dir),
                        "project": {
                            "architecture": architecture,
                            "type": project_type
                        }
                    }
                    
                    success = self.supervisor.execute_phase_0_plan(workspace_config)
                    
                    if not success:
                        logger.warning("[orchestrator] phase 0 collaboration failed - no user response")
                        if self._rag:
                            self._rag.close()
                        self.run_log.completed = True
                        self.run_log.total_duration_s = round(time.time() - total_start, 1)
                        self._save_log()
                        self._banner("PHASE 0 — COLLABORATION FAILED")
                        return self.run_log
                
                # Check if docs were generated
                if any(self.docs_dir.glob("*.md")):
                    logger.info("[orchestrator] phase 0 docs ready - continuing to phase 1")
                    ES.emit("phase_done", {"phase": 0, "duration_s": round(time.time() - phase0_start, 1)})
                else:
                    logger.warning("[orchestrator] phase 0 incomplete - no docs generated")
                    if self._rag:
                        self._rag.close()
                    self.run_log.completed = True
                    self.run_log.total_duration_s = round(time.time() - total_start, 1)
                    self._save_log()
                    self._banner("PHASE 0 — DOCS NEEDED")
                    return self.run_log
                    
            except Exception as e:
                logger.error("[orchestrator] phase 0 failed: %s", e)
                if self._rag:
                    self._rag.close()
                self.run_log.completed = True
                self.run_log.total_duration_s = round(time.time() - total_start, 1)
                self._save_log()
                self._banner("PHASE 0 — ERROR")
                return self.run_log

        # ── Phase: Spec ───────────────────────────────────────────────────────
        self._comms.info("Starting Phase: Specification (generating spec.md and use_cases.md)")
        spec_files = self._run_spec_phase()
        self.run_log.spec_produced = bool(spec_files)
        self._comms.complete(f"Specification complete: {len(spec_files)} files generated")

        # Index spec output immediately
        if self._rag and self._rag.enabled:
            for f in spec_files:
                self._rag.ingest_file(f, "docs")
        self._save_log()

        # If docs/ is still empty after phase 0+spec, stop here.
        if not any(self.docs_dir.glob("*.md")):
            logger.info("[orchestrator] docs/ is empty — completed bootstrap at phase 1")
            logger.info("[orchestrator] agents are ready. Add docs/ or start agent collaboration")
            self._supervisor_status("Bootstrap complete. No documents found. Please add documentation or start agent collaboration.")
            if self._rag:
                self._rag.close()
            self.run_log.completed = True
            self.run_log.total_duration_s = round(time.time() - total_start, 1)
            self._save_log()
            self._banner("COMPLETE — phase 1 bootstrap")
            return self.run_log

        # ── Phase: Architecture ───────────────────────────────────────────────
        # With openspec framework, include the full change folder as docs context
        if self.framework_id == "openspec":
            openspec_change = self.workspace / "openspec" / "changes"
            if openspec_change.exists():
                # Collect all md files from the most recent change folder
                change_dirs = [d for d in openspec_change.iterdir()
                               if d.is_dir() and d.name != "archive"]
                extra = []
                for cd in change_dirs:
                    extra.extend(cd.rglob("*.md"))
                spec_files = list(set(spec_files + extra))
        combined = self._combined_docs_dir(spec_files)
        self._comms.info(f"Starting Phase: Architecture Planning (for {self.architecture} architecture)")
        iterations = self.architect.plan(combined)
        if not iterations:
            logger.error("[orchestrator] architect produced no iterations — aborting")
            self._comms.info("Architecture planning failed — no iterations produced")
            return self.run_log

        logger.info("[orchestrator] %d iterations, %d phases",
                    len(iterations), len({i.get("phase", 1) for i in iterations}))
        self._comms.complete(f"Architecture planning complete: {len(iterations)} iterations across {len({i.get('phase', 1) for i in iterations})} phases")
        self._save_log()

        # ── Phase: Iteration execution ────────────────────────────────────────
        
        # Auto-resume: Check if we have a previous run log with completed iterations
        if self.start_from == 1 and self.run_log.iterations:
            # Find the last completed iteration
            last_completed = None
            completed_phases = set()
            for iter_result in self.run_log.iterations:
                if iter_result.approved:
                    last_completed = iter_result.iteration_id
                    # Track which phases are already complete
                    iter_data = next((i for i in iterations if i["id"] == iter_result.iteration_id), None)
                    if iter_data:
                        completed_phases.add(iter_data.get("phase", 1))
            
            if last_completed:
                # Find the next iteration to run
                next_iteration = last_completed + 1
                logger.info("\n[AUTO-RESUME] Detected previous run - last completed: iteration %d", last_completed)
                logger.info("[AUTO-RESUME] Resuming from iteration %d", next_iteration)
                logger.info("[AUTO-RESUME] Already completed phases: %s\n", sorted(completed_phases))
                self.start_from = next_iteration
                self._supervisor_status(
                    f"Auto-resuming from iteration {next_iteration}. Completed: {len(self.run_log.iterations)} iterations, {len(completed_phases)} phases."
                )
        else:
            completed_phases = set()
        for iteration in iterations:
            if iteration["id"] < self.start_from:
                continue
            phase       = iteration.get("phase", 1)
            
            # Emit phase_started if it's the first iteration of this phase
            if not any(ir.phase == phase for ir in self.run_log.iterations):
                ES.emit("phase_started", {"phase": phase, "name": iteration.get("name", "")})

            self._comms.info(f"Starting Iteration {iteration['id']} (Phase {phase}): {iteration['name']}")
            try:
                CC.check_stop()
            except BuildStopped:
                ES.emit("stopped", {})
                break
            iter_result = self._run_iteration(iteration)
            self.run_log.iterations.append(iter_result)
            self._save_log()

            if not iter_result.approved:
                logger.error("[orchestrator] iter %d failed — stopping", iteration["id"])
                self._comms.info(f"Iteration {iteration['id']} failed.")
                break
            # Approval gate and pause check
            try:
                gate_ok = CC.wait_approval(iteration["id"])
                if not gate_ok:
                    logger.info("[orchestrator] iter %d rejected by user", iteration["id"])
                    break
                CC.check_after_iter()
            except BuildStopped:
                ES.emit("stopped", {})
                break
            
            self._comms.complete(f"Iteration {iteration['id']} complete and approved.")

            remaining = [i for i in iterations
                         if i.get("phase", 1) == phase and i["id"] > iteration["id"]]
            if not remaining and phase not in completed_phases:
                completed_phases.add(phase)

                # Phase retrospective — adapt the plan
                phase_adaptation = self._phase_retrospective(phase, iteration, iterations)
                if phase_adaptation.get("replan", False):
                    self._log(f"Adapting remaining iterations based on retrospective")
                    iterations = self._replan_remaining(iterations, phase, completed_phases, iterations)

                # Let LLM decide if CI/CD infrastructure is needed for this phase
                cicd_decision = self._decide_cicd_needed(phase, iteration)
                if cicd_decision.get("needed", False):
                    logger.info("\n  [PHASE %d COMPLETE] Running CI/CD infrastructure...", phase)
                    self._run_cicd_phase(phase)
                else:
                    logger.info("\n  [PHASE %d COMPLETE] No CI/CD infrastructure needed.", phase)

                # Count iterations in this phase
                phase_iterations = [ir for ir in self.run_log.iterations if ir.phase == phase]
                ES.emit("phase_done", {
                    "phase": phase,
                    "iterations": len(phase_iterations),
                    "approved": sum(1 for ir in phase_iterations if ir.approved),
                    "duration_s": iter_result.duration_s,
                    "replan": phase_adaptation.get("replan", False),
                })
                self._save_log()

        # ── Cleanup ───────────────────────────────────────────────────────────
        if self._rag:
            self._rag.close()

        self.run_log.completed        = True
        self.run_log.total_duration_s = round(time.time() - total_start, 1)
        self._save_log()
        self._banner(f"COMPLETE — {self.run_log.total_duration_s:.0f}s")
        ES.emit("build_done", {
            "duration_s": self.run_log.total_duration_s,
            "approved":   sum(1 for i in self.run_log.iterations if i.approved),
            "total":      len(self.run_log.iterations),
            "phases":     len(set(i.phase for i in self.run_log.iterations)),
            "artifacts":  list(set(a for i in self.run_log.iterations for a in i.delivered_artifacts)),
        })
        return self.run_log

    def _phase_retrospective(self, phase: int, iteration: dict, all_iterations: list) -> dict:
        """Phase retrospective — evaluate what was delivered and decide if plan needs adapting."""
        delivered = []
        for ir in self.run_log.iterations:
            if ir.phase == phase:
                delivered.extend(ir.delivered_artifacts)

        goal = iteration.get("goal", iteration.get("name", ""))

        prompt = f"""You are evaluating Phase {phase} to decide if the remaining plan needs adapting.

## Phase Goal
{goal}

## Delivered Artifacts
{chr(10).join(f'- {a}' for a in delivered)}

## Task
1. Has the phase goal been substantially met?
2. Do remaining iterations need to be adjusted based on what we learned?
3. Should we add, remove, or modify remaining work?

Respond with JSON:
```json
{{
  "goal_met": true/false,
  "replan": true/false,
  "reason": "brief explanation",
  "adaptations": ["add tests", "simplify scope", "extend phase"]
}}
```"""
        return self._llm_json(prompt)

    def _replan_remaining(self, iterations: list, current_phase: int,
                          completed_phases: set, original_iterations: list) -> list:
        """Use LLM to replan remaining iterations based on what was learned."""
        # Gather what was delivered
        delivered = []
        for ir in self.run_log.iterations:
            delivered.extend(ir.delivered_artifacts)

        remaining = [i for i in iterations if i.get("phase", 1) > current_phase]

        if not remaining:
            return iterations

        remaining_json = json.dumps(remaining, indent=2)
        delivered_json = json.dumps(delivered, indent=2)

        prompt = f"""You are replanning the remaining iterations based on what was delivered.

## Delivered So Far
{delivered_json}

## Current Remaining Plan
{remaining_json}

## Task
Adjust the remaining iterations to:
1. Remove redundant work if capabilities were already delivered
2. Add missing pieces if gaps were discovered
3. Keep iterations small and focused

Return the adjusted remaining iterations as a JSON array with the same structure.
Only modify iterations for phases NOT yet completed.
If no changes needed, return the original remaining iterations."""

        try:
            new_remaining = self._llm_json(prompt)
            if isinstance(new_remaining, list) and new_remaining:
                # Rebuild full iteration list: completed + adjusted remaining
                completed = [i for i in iterations if i.get("id") <= (max(
                    (ir.iteration_id for ir in self.run_log.iterations), default=0))]
                return completed + new_remaining
        except Exception as e:
            self._log(f"Replanning failed: {e}")

        return iterations

    # ── LLM helpers ─────────────────────────────────────────────────────────

    def _llm_json(self, prompt: str) -> dict:
        """Query LLM and parse JSON response."""
        response = self._llm.generate(prompt=prompt)
        import re
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        return json.loads(response)

    def _llm_text(self, prompt: str) -> str:
        """Query LLM and return text."""
        return self._llm.generate(prompt=prompt)

    # ── Build state persistence ─────────────────────────────────────────

    def _setup_event_store(self) -> None:
        """Initialize the persistent file-backed event store."""
        from core.event_stream import FileEventStore
        store_path = self.workspace / ".ai" / "events.jsonl"
        store = FileEventStore(store_path)
        ES.set_file_store(store)
        self._log(f"Event store: {store_path}")

    def _load_build_state(self) -> Optional[dict]:
        """Reconstruct current build state from the event log."""
        store = ES.get_file_store()
        if store is None:
            return None
        return store.reconstruct_state()

    def _decide_cicd_needed(self, phase: int, iteration: dict) -> dict:
        """Let the LLM decide if CI/CD infrastructure is needed for a phase."""
        prompt = f"""You are the Orchestrator deciding if CI/CD infrastructure is needed.

Phase {phase} just completed.
Iteration: {iteration.get('name', '')}
Phase goal: {iteration.get('goal', '')}

Decide if CI/CD infrastructure (Docker, CI pipelines, deployment config) is needed.

Consider:
- Was infrastructure/deployment mentioned in requirements?
- Is this a production/deployable project?
- Would containerization or CI/CD add value?

For simple scripts, CLI tools, or libraries: likely NO.
For web apps, APIs, or deployable services: likely YES.

Respond with JSON:
{{
  "needed": true/false,
  "reason": "brief explanation"
}}"""
        try:
            result = {"output": self._llm.generate(prompt=prompt)}
            import json, re
            output = result.get("output", "")
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(output)
        except Exception as e:
            self._log(f"LLM CI/CD decision failed: {e}, defaulting to no CI/CD")
            return {"needed": False, "reason": "LLM decision failed, defaulting to no CI/CD"}

    def _decide_integration_tests_needed(self, backend_tasks: list) -> dict:
        """Let the LLM decide if integration tests are needed."""
        if not backend_tasks:
            return {"needed": False, "reason": "No backend tasks to integration test"}

        task_files = [t.get("file", "") for t in backend_tasks]
        prompt = f"""You are the Orchestrator deciding if integration tests are needed.

Files just implemented:
{chr(10).join(f'- {f}' for f in task_files)}

Decide if integration tests (cross-component testing) are needed.

Consider:
- Are there multiple components that need to work together?
- Is this a complex system with integration points?
- Would integration testing add value?

For simple single-file projects: likely NO.
For multi-component systems: likely YES.

Respond with JSON:
{{
  "needed": true/false,
  "reason": "brief explanation"
}}"""
        try:
            result = {"output": self._llm.generate(prompt=prompt)}
            import json, re
            output = result.get("output", "")
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(output)
        except Exception as e:
            self._log(f"LLM integration test decision failed: {e}, defaulting to yes")
            return {"needed": True, "reason": "LLM decision failed, defaulting to integration tests"}

    # ── Bus wiring ───────────────────────────────────────────────────────────

    def _register_all_on_bus(self):
        """Register all built agents on the AgentBus so they can be queried/delegated."""
        bus = AgentBus.instance()
        for attr in vars(self):
            obj = getattr(self, attr)
            from core.base import AiderAgent
            if isinstance(obj, AiderAgent):
                bus.register_agent(obj.role, obj)
        logger.info("[orchestrator] all agents registered on AgentBus")

    # ── RAG and LLM setup ─────────────────────────────────────────────────────

    def _setup_rag(self):
        if not self.rag_config.get("enabled", False):
            logger.info("[orchestrator] RAG disabled (set rag.enabled: true in workspace.yaml)")
            return

        from rag import RagClient
        store_path    = self.workspace / ".rag"
        embed_model   = self.rag_config.get("embed_model", "nomic-embed-text")
        self._rag     = RagClient(store_path=store_path, embed_model=embed_model)

        if not self._rag.setup():
            logger.warning("[orchestrator] RAG setup failed — continuing without RAG")
            self._rag = None
            return

        logger.info("[orchestrator] RAG enabled (LanceDB + %s)", embed_model)

        # Index docs
        logger.info("[orchestrator] indexing docs/...")
        self._rag.ingest_directory(self.docs_dir, collection="docs")

        # Index legacy source dirs
        for legacy_dir in self.legacy_dirs:
            logger.info("[orchestrator] indexing legacy source: %s", legacy_dir)
            self._rag.ingest_directory(legacy_dir, collection="legacy")

        # Index any existing output (resume case)
        if (self.workspace / "api-gateway").exists():
            logger.info("[orchestrator] indexing existing codebase (resume)...")
            self._rag.ingest_directory(self.workspace, collection="codebase")

    def _setup_llm(self):
        from core.llm import OllamaClient
        llm_model  = self.rag_config.get("llm_model", self.model)
        self._llm  = OllamaClient(model=llm_model, temperature=0.2)
        if self._llm.is_available():
            logger.info("[orchestrator] local LLM ready: %s", llm_model)
        else:
            logger.warning("[orchestrator] Ollama LLM not available (%s) — "
                           "planning fallback will be limited", llm_model)

    # ── Spec phase ────────────────────────────────────────────────────────────

    def _run_spec_phase(self) -> list[Path]:
        if self.skip_spec:
            ai_dir = self.workspace / ".ai"
            return [p for p in [ai_dir/"spec.md", ai_dir/"use_cases.md"] if p.exists()]

        start = time.time()
        ES.emit("phase_started", {"phase": 0})
        logger.info("[orchestrator] PHASE 0: spec...")
        self._comms.info("Starting Phase: Specification (generating spec.md and use_cases.md)")
        spec_file, uc_file = self.spec_agent.specify(self.docs_dir)

        # Report step-by-step results to user
        step_results = self.spec_agent.get_step_results()
        failed_steps = [s for s in step_results if not s["success"]]
        if failed_steps:
            failed_labels = ", ".join(f"{s['label']} [{s.get('severity', '?')}]" for s in failed_steps)
            logger.warning("[orchestrator] spec phase failed steps: %s", failed_labels)
            # Determine if any need user input (hallucination/critical)
            user_blocking = [s for s in failed_steps if s.get("severity") in ("hallucination", "critical")]
            if user_blocking:
                self._comms.info(f"Spec generation requires user input: {len(user_blocking)} critical step(s)")
            else:
                self._comms.info(f"Spec generation had {len(failed_steps)} failed step(s) — auto-retries exhausted")

        # Last-resort: create stubs for empty files
        ai_dir = self.workspace / ".ai"
        for f in [spec_file, uc_file]:
            if f is not None and (not f.exists() or f.stat().st_size == 0):
                logger.warning(f"[orchestrator] creating stub {f.name} (spec agent could not generate content)")
                f.write_text(f"# {f.name}\n\n_Auto-generated stub. Content pending manual input._")

        ES.emit("phase_done", {"phase": 0, "duration_s": round(time.time() - start, 1)})

        if spec_file and spec_file.exists() and spec_file.stat().st_size > 0:
            da = self._make(DocsAgent)
            da.run(
                message="Review and enrich spec.md and use_cases.md.",
                read_files=list(self.docs_dir.glob("*.md")),
                edit_files=[spec_file] + ([uc_file] if uc_file and uc_file.exists() else []),
                timeout=180,
                log_callback=self.log_callback,
            )

        results = [f for f in [spec_file, uc_file] if f and f.exists()]
        self._comms.complete(f"Specification complete: {len(results)} files generated")
        return results

    # ── Iteration ─────────────────────────────────────────────────────────────

    def _run_iteration(self, iteration: dict) -> IterationResult:
        start = time.time()
        phase = iteration.get("phase", 1)
        logger.info("--- ITER %d (ph%d): %s ---", iteration["id"], phase, iteration["name"])
        ES.emit("iter_started", {
            "id": iteration["id"], "name": iteration["name"], "phase": phase,
        })

        result = IterationResult(
            iteration_id=iteration["id"], phase=phase,
            name=iteration["name"], approved=False,
        )
        prior = self._prior_task_files(iteration["id"])

        for attempt in range(1, self.max_rework_per_iter + 1):
            tasks = self.planner.decompose(iteration, self.docs_dir, prior)
            if not tasks:
                break
            
            # Apply architecture-aware agent assignments
            for task in tasks:
                original_agent = task.get("agent", "backend_dev")
                # Use LLM to decide agent assignment
                agent_prompt = f"""You are the Orchestrator assigning an agent for this task.

Task: {task}

Available agents:
- backend_dev: implements code (any language, framework, or type)
- test_dev: writes tests (unit, integration, acceptance)
- config_agent: creates configuration files
- docs_agent: writes documentation
- cicd: creates infrastructure/CI/CD files

Choose the most appropriate agent based on:
1. Task type (implementation, testing, config, docs, infrastructure)
2. The nature of the file being created

Respond with JSON:
{{
  "agent": "agent_name",
  "reason": "brief explanation"
}}"""

                try:
                    result = {"output": self._llm.generate(prompt=agent_prompt)}
                    
                    # Parse response
                    import json
                    import re
                    output = result.get("output", "")
                    json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
                    if json_match:
                        decision = json.loads(json_match.group(1))
                    else:
                        decision = json.loads(output)
                    
                    architecture_agent = decision.get("agent", task.get("agent", "backend_dev"))
                    self._log(f"LLM assigned agent: {architecture_agent} for task {task.get('name', '')}")
                    
                except Exception as e:
                    self._log(f"LLM agent assignment failed: {e}, using default")
                    logger.warning("[orchestrator] LLM agent assignment failed: %s", e)
                    architecture_agent = task.get("agent", "backend_dev")  # fallback
                if architecture_agent != original_agent:
                    logger.info("[orchestrator] architecture override: %s -> %s for task '%s'", 
                              original_agent, architecture_agent, task.get("name", ""))
                    task["agent"] = architecture_agent
            
            self._warn_tdd(tasks, iteration["id"])
            result.task_results = []
            all_ok = True
            if self.parallel:
                # Run tasks in parallel
                with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
                    future_to_task = {executor.submit(self._run_task, task, iteration["id"]): task for task in tasks}
                    for future in as_completed(future_to_task):
                        try:
                            CC.check_stop()
                        except BuildStopped:
                            executor.shutdown(wait=False, cancel_futures=True)
                            ES.emit("stopped", {})
                            return result
                        tr = future.result()
                        result.task_results.append(tr)
                        self._log_task_result(tr)
                        if not tr.approved:
                            all_ok = False
            else:
                # Run tasks sequentially (default)
                for task in tasks:
                    tr = self._run_task(task, iteration["id"])
                    ES.emit("task_done", {
                        "id": task.get("id"), "agent": task.get("agent"),
                        "file": task.get("file"), "verdict": tr.final_verdict,
                        "attempts": tr.attempts, "duration_s": tr.duration_s,
                    })
                    try:
                        CC.check_after_task()
                    except BuildStopped:
                        ES.emit("stopped", {})
                        result.task_results.append(tr)
                        return result
                    result.task_results.append(tr)
                    self._log_task_result(tr)
                    if not tr.approved:
                        all_ok = False

            if not all_ok:
                continue

            backend_tasks = [t for t in tasks if t.get("agent") == "backend_dev"]
            if backend_tasks:
                # Let LLM decide if integration tests are needed
                it_decision = self._decide_integration_tests_needed(backend_tasks)
                if it_decision.get("needed", False):
                    it_results = self.integration_test.write_integration_tests(
                        iteration, backend_tasks, self.docs_dir)
                    result.integration_tests_written = True
                    # Index integration tests into RAG
                    if self._rag and self._rag.enabled:
                        for r in it_results:
                            if r.get("test_file"):
                                p = self.workspace / r["test_file"]
                                if p.exists():
                                    self._rag.ingest_file(p, "codebase")
                else:
                    self._log(f"Integration tests skipped: {it_decision.get('reason', 'not needed')}")

            verdict = self.reviewer.review_iteration(iteration, tasks, self.docs_dir)
            logger.info("[orchestrator] holistic iter %d: %s",
                        iteration["id"], verdict.label)
            if verdict.approved:
                result.approved = True
                break
            for s in verdict.suggestions:
                logger.warning("  [reviewer] %s", s)

        result.duration_s = round(time.time() - start, 1)

        # Collect delivered artifacts
        result.delivered_artifacts = [
            tr.file for tr in result.task_results if tr.approved
        ]

        # Iteration retrospective (brief)
        if result.approved:
            result.retrospective_notes = self._iteration_retrospective(result, phase)

        status = "✓ APPROVED" if result.approved else "✗ REJECTED"
        logger.info("\n  %s Iteration %d completed in %.1fs\n", status, iteration["id"], result.duration_s)

        # Emit iteration done event
        ES.emit("iter_done", {
            "id": iteration["id"],
            "phase": phase,
            "name": iteration["name"],
            "approved": result.approved,
            "tasks": len(result.task_results),
            "artifacts": result.delivered_artifacts,
            "duration_s": result.duration_s,
            "retrospective": result.retrospective_notes,
        })

        return result

    # ── Task dispatch ─────────────────────────────────────────────────────────

    def _run_task(self, task: dict, iteration_id: int) -> TaskResult:
        start     = time.time()
        agent_key = task.get("agent", "backend_dev")
        ES.emit("task_started", {
            "id": task.get("id"), "agent": agent_key,
            "file": task.get("file"), "description": task.get("description","")[:120],
            "iteration_id": iteration_id,
        })
        # Inject any pending directive
        directive = CC.pop_directive()
        if directive:
            task = dict(task)
            task["description"] = task.get("description","") + f"\n\nDIRECTIVE:\n{directive}"
            ES.emit("directive_injected", {"text": directive, "task_id": task.get("id")})
        if agent_key == "test_dev":
            return self._run_test_dev(task, iteration_id, start)
        return self._run_worker(task, agent_key, iteration_id, start)

    def _run_test_dev(self, task: dict, iteration_id: int, start: float) -> TaskResult:
        agent = self._make(TestDevAgent, task["id"], iteration_id)
        approved, feedback, attempt = False, None, 0
        for attempt in range(1, self.max_rework_per_task + 1):
            t = dict(task)
            if feedback: t["description"] += f"\n\nREVIEWER FEEDBACK:\n{feedback}"
            result = agent.write_unit_test(t, self.docs_dir)
            if not result.get("success"):
                feedback = result.get("stderr", "")[:300]; continue
            verdict = self.reviewer.review(t, self.docs_dir)
            if verdict.approved: approved = True; break
            feedback = verdict.reason + (
                "\n" + "\n".join(f"- {s}" for s in verdict.suggestions)
                if verdict.suggestions else "")
        return TaskResult(task_id=task["id"], file=task["file"], agent="test_dev",
                          approved=approved, attempts=attempt,
                          final_verdict="APPROVED" if approved else "REWORK",
                          duration_s=round(time.time() - start, 1))

    def _run_worker(self, task: dict, agent_key: str,
                    iteration_id: int, start: float) -> TaskResult:
        AgentCls = self.WORKER_MAP.get(agent_key, BackendDevAgent)
        agent    = self._make(AgentCls, task["id"], iteration_id)
        approved, feedback, attempt = False, None, 0
        for attempt in range(1, self.max_rework_per_task + 1):
            t = dict(task)
            if feedback: t["description"] += f"\n\nREVIEWER FEEDBACK:\n{feedback}"
            result = agent.implement(t, self.docs_dir)
            if not result.get("success"):
                feedback = result.get("stderr", "")[:300]; continue
            # Index the written file into RAG immediately
            if self._rag and self._rag.enabled:
                target = self.workspace / task["file"]
                if target.exists():
                    self._rag.ingest_file(target, "codebase")
            verdict = self.reviewer.review(t, self.docs_dir)
            if verdict.approved: approved = True; break
            feedback = verdict.reason + (
                "\n" + "\n".join(f"- {s}" for s in verdict.suggestions)
                if verdict.suggestions else "")
        return TaskResult(task_id=task["id"], file=task["file"], agent=agent_key,
                          approved=approved, attempts=attempt,
                          final_verdict="APPROVED" if approved else "REWORK",
                          duration_s=round(time.time() - start, 1))
        
    def _log_task_result(self, result: TaskResult):
        """Log task completion status."""
        status = "✓" if result.approved else "✗"
        duration = f"{result.duration_s:.1f}s"
        attempts = f"({result.attempts} attempt{'s' if result.attempts > 1 else ''})"
        msg = f"  {status} [{result.agent.upper()}] {result.final_verdict} — {duration} {attempts}"
        logger.info(msg)
        self._send_log("orchestrator", msg)

    # ── CI/CD ─────────────────────────────────────────────────────────────────

    def _run_cicd_phase(self, phase: int):
        logger.info("[orchestrator] CI/CD phase %d", phase)
        for r in self.cicd.build_phase_infra(phase, self.docs_dir):
            logger.info("[cicd] %s → %s", r.get("file","?"),
                        "ok" if r.get("success") else "FAILED")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _warn_tdd(self, tasks, iter_id):
        """Warn if implementation files don't have corresponding test files."""
        # Generic approach: check if any file has a corresponding test file
        impl_files = {t["file"] for t in tasks if t.get("agent") in ("backend_dev", "worker")}
        test_files = {t["file"] for t in tasks if t.get("agent") == "test_dev"}

        # Check for any test-related patterns (generic)
        for impl in impl_files:
            impl_name = Path(impl).stem
            has_test = any(
                impl_name in tf and ("test" in tf.lower() or "spec" in tf.lower() or "Test" in tf or "Spec" in tf)
                for tf in test_files
            )
            if not has_test:
                logger.warning("[orchestrator] TDD WARNING iter %d: no test file found for %s", iter_id, impl)

    def _iteration_retrospective(self, result: IterationResult, phase: int) -> str:
        """Brief iteration retrospective — what was delivered, any concerns."""
        artifact_list = ", ".join(result.delivered_artifacts) if result.delivered_artifacts else "none"

        prompt = f"""You are conducting a brief retrospective on Iteration {result.iteration_id} (Phase {phase}).

## Delivered
{artifact_list}

## Task Results
{chr(10).join(f'- {tr.agent}: {tr.file} — {tr.final_verdict} ({tr.attempts} attempt(s))' for tr in result.task_results)}

## Task
Provide one sentence on what went well and one sentence on any concern or improvement.

Respond with a short text (no JSON)."""

        try:
            return self._llm_text(prompt).strip()[:200]
        except Exception:
            return ""

    def _combined_docs_dir(self, spec_files):
        combined = self.workspace / ".ai" / "combined_docs"
        combined.mkdir(exist_ok=True)
        for f in self.docs_dir.glob("*.md"):
            (combined / f.name).write_text(f.read_text())
        for f in spec_files:
            (combined / f.name).write_text(f.read_text())
        return combined

    def _prior_task_files(self, current_id):
        ai_dir = self.workspace / ".ai"
        return [ai_dir / f"tasks_iter_{i}.json"
                for i in range(1, current_id)
                if (ai_dir / f"tasks_iter_{i}.json").exists()]

    def _save_log(self):
        (self.workspace / ".ai" / "run_log.json").write_text(
            json.dumps(asdict(self.run_log), indent=2))

    def _banner(self, msg):
        sep = "=" * 60
        logger.info(sep)
        logger.info(msg)
        logger.info(sep)
        self._send_log("orchestrator", sep)
        self._send_log("orchestrator", msg)
        self._send_log("orchestrator", sep)
