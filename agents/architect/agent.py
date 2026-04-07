"""
architect/agent.py — Architect agent.

Baby-step approach:
  Step 1: identify layers/components (fast)
  Step 2: plan Phase 1 only (small scope)
  Step 3: plan Phase 2 only
  Step 4: plan Phase 3 only
  Merge all phases into iterations.json
"""

import json
import logging
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)
SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


class ArchitectAgent(AiderAgent):
    _role = "architect"

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
    ):
        super().__init__(
            role="architect",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills,
            framework_id=framework_id,
            max_retries=2,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def _phase_prompt(self, phase: int, start_id: int, architecture: str = None) -> str:
        """Generate prompt for planning a specific phase."""
        arch_note = ""
        if architecture == "microservice":
            arch_note = "\nARCHITECTURE: Microservice - Plan for service boundaries, API contracts, and inter-service communication."
        elif architecture == "monolith":
            arch_note = "\nARCHITECTURE: Monolith - Plan for modular structure within single application."
        
        PHASE_DESC = {
            1: (
                "Phase 1 — core logic only.\n"
                "NO Spring web, NO HTTP, NO external calls, NO file persistence.\n"
                "Only: domain model, business logic, in-memory data, interfaces."
                f"{arch_note}"
            ),
            2: (
                "Phase 2 — API layer.\n"
                "Spring Boot controllers, HTTP routes, wire real implementations.\n"
                "Reads Phase 1 files as context."
                f"{arch_note}"
            ),
            3: (
                "Phase 3 — infrastructure only.\n"
                "Dockerfile, docker-compose, CI pipeline.\n"
                "Usually 1 iteration is enough."
                f"{arch_note}"
            ),
        }
        return (
            f"Plan the iterations for {PHASE_DESC[phase]}\n\n"
            f"Start iteration IDs from {start_id}.\n"
            f"Each iteration: 2-4 files max. Simple goal. Clear files_expected.\n\n"
            "Output ONLY valid JSON array:\n"
            "[\n"
            "  {\n"
            f'    "id": {start_id},\n'
            f'    "phase": {phase},\n'
            '    "name": "short name",\n'
            '    "goal": "one sentence",\n'
            '    "layer": "model",\n'
            '    "files_expected": ["path/to/File.java"],\n'
            '    "depends_on": [],\n'
            '    "acceptance_criteria": ["compiles"]\n'
            "  }\n"
            "]" 
        )

    def _load_architecture(self) -> str:
        """Load architecture style from workspace.yaml."""
        try:
            ws_file = self.workspace.parent / "workspace.yaml"
            if ws_file.exists():
                import yaml
                ws = yaml.safe_load(ws_file.read_text()) or {}
                return ws.get("project", {}).get("architecture", "monolith")
        except Exception as e:
            logger.warning("Failed to load architecture from workspace.yaml: %s", e)
        return "monolith"

    def plan(self, docs_dir: Path) -> list[dict]:
        # Load architecture from workspace config
        architecture = self._load_architecture()
        logger.info("[architect] planning for %s architecture", architecture)
        
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir(exist_ok=True)
        iterations_file = ai_dir / "iterations.json"

        doc_files = list(docs_dir.glob("*.md"))
        if not doc_files:
            logger.info("[architect] no docs found in %s - cannot plan without documentation", docs_dir)
            logger.info("[architect] supervisor should have initiated phase 0 collaboration")
            return []

        logger.info("[architect] reading %d doc files", len(doc_files))
        spec_file = ai_dir / "spec.md"
        ctx = doc_files + ([spec_file] if spec_file.exists() else [])

        if not ctx:
            logger.error("[architect] no context files found")
            return []

        all_iterations: list[dict] = []
        next_id = 1

        # ── Step 1: Phase 1 iterations ────────────────────────────────────────
        logger.info("[architect] planning Phase 1 (core logic)")
        phase1_file = ai_dir / "phase1.json"
        self.run(
            message=self._phase_prompt(1, next_id, architecture),
            read_files=ctx,
            edit_files=[phase1_file],
            timeout=120,
        )
        phase1 = self.read_json(phase1_file, [])
        phase1 = self._renumber(phase1, next_id, phase=1)
        all_iterations.extend(phase1)
        next_id += len(phase1)

        # ── Step 2: Phase 2 iterations ────────────────────────────────────────
        logger.info("[architect] planning Phase 2 (API layer)")
        phase2_file = ai_dir / "phase2.json"
        ctx2 = ctx + ([phase1_file] if phase1_file.exists() else [])
        self.run(
            message=self._phase_prompt(2, next_id, architecture),
            read_files=ctx2,
            edit_files=[phase2_file],
            timeout=120,
        )
        phase2 = self.read_json(phase2_file, [])
        phase2 = self._renumber(phase2, next_id, phase=2)
        all_iterations.extend(phase2)
        next_id += len(phase2)

        # ── Step 3: Phase 3 (infra — minimal, often just 1 iteration) ─────────
        logger.info("[architect] planning Phase 3 (infra)")
        phase3_file = ai_dir / "phase3.json"
        self.run(
            message=self._phase_prompt(3, next_id, architecture),
            read_files=ctx,
            edit_files=[phase3_file],
            timeout=90,
        )
        phase3 = self.read_json(phase3_file, [])
        phase3 = self._renumber(phase3, next_id, phase=3)
        all_iterations.extend(phase3)

        if not all_iterations:
            logger.error("[architect] produced no iterations")
            return []

        iterations_file.write_text(json.dumps(all_iterations, indent=2))
        logger.info("[architect] total: %d iterations across 3 phases", len(all_iterations))

        # Share on bus for other agents
        self.share_context("iteration_plan", all_iterations)
        return all_iterations

    def read_json(self, path: Path, default):
        """Read and parse JSON file, handling markdown code fences."""
        if not path.exists():
            return default
        try:
            text = path.read_text().strip()
            # Strip markdown fences if model added them
            if text.startswith("```"):
                text = "\n".join(
                    line for line in text.splitlines()
                    if not line.strip().startswith("```")
                )
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("[architect] JSON parse error in %s: %s", path.name, e)
            return default

    @staticmethod
    def _renumber(iterations: list, start_id: int, phase: int) -> list:
        """Ensure sequential IDs and phase label."""
        for i, it in enumerate(iterations):
            it["id"]    = start_id + i
            it["phase"] = phase
        return iterations

    def request_clarification(self, question: str, context: dict = None, suggestions: list = None) -> str:
        """
        Request clarification from user via comms system.
        Used when architect needs more information about project requirements.
        
        Args:
            question: The clarification question to ask
            context: Additional context about what needs clarification
            suggestions: Suggested answers for the user
            
        Returns:
            User's response
        """
        try:
            from comms.clarification_client import ClarificationClient
            clarifier = ClarificationClient(
                agent_id="architect", 
                task_id=context.get("task_id", "clarification") if context else "clarification",
                iteration_id=context.get("iteration_id", 0) if context else 0
            )
            
            reply = clarifier.ask(
                question=question,
                suggestions=suggestions or [],
                timeout=3600
            )
            
            logger.info("[architect] received clarification: %s", reply[:100])
            return reply
            
        except ImportError:
            logger.warning("[architect] comms not available - cannot request clarification")
            return ""
        except Exception as e:
            logger.error("[architect] clarification request failed: %s", e)
            return ""

    def handle_query(self, question: str, context: dict) -> str:
        """
        Handle queries from other agents via AgentBus.
        Specifically handles phase 0 clarification requests from supervisor.
        """
        logger.info("[architect] received query from agent bus: %s", question[:80])
        
        # Check if this is a phase 0 clarification request
        if "phase 0" in question.lower() or "clarification" in question.lower():
            # Extract the question to ask user
            clarification_plan = context.get("clarification_plan", {})
            user_question = clarification_plan.get("primary_question", question)
            suggestions = clarification_plan.get("suggestions", [])
            
            logger.info("[architect] handling phase 0 clarification request")
            
            # Ask user for clarification
            user_response = self.request_clarification(
                question=user_question,
                context=context,
                suggestions=suggestions
            )
            
            if user_response:
                # Broadcast that architect has gathered user input
                self.broadcast("architect.clarification_received", {
                    "response_length": len(user_response),
                    "task_id": context.get("task_id", "unknown")
                })
            
            return user_response
        
        # Default: use parent class handler (local LLM)
        return super().handle_query(question, context)

    def run(self, message: str, read_files: list = None, edit_files: list = None, timeout: int = 300) -> dict:
        """
        Standard Aider agent run - delegates to parent class.
        """
        return super().run(message, read_files, edit_files, timeout, log_callback=self.log_callback)
