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

    def _phase_prompt(self, phase: int, start_id: int) -> str:
        """Generate prompt for planning a specific phase."""
        PHASE_DESC = {
            1: (
                "Phase 1 — core logic only.\n"
                "NO Spring web, NO HTTP, NO external calls, NO file persistence.\n"
                "Only: domain model, business logic, in-memory data, interfaces."
            ),
            2: (
                "Phase 2 — API layer.\n"
                "Spring Boot controllers, HTTP routes, wire real implementations.\n"
                "Reads Phase 1 files as context."
            ),
            3: (
                "Phase 3 — infrastructure only.\n"
                "Dockerfile, docker-compose, CI pipeline.\n"
                "Usually 1 iteration is enough."
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

    def plan(self, docs_dir: Path) -> list[dict]:
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir(exist_ok=True)
        iterations_file = ai_dir / "iterations.json"

        doc_files = list(docs_dir.glob("*.md"))
        if not doc_files:
            logger.info("[architect] no docs found in %s - entering phase 0 collaboration", docs_dir)
            
            # Phase 0: No docs yet - ask user for project guidance
            try:
                from comms.clarification_client import ClarificationClient
                clarifier = ClarificationClient(
                    agent_id="architect", 
                    task_id="phase-0-planning",
                    iteration_id=0
                )
                
                question = """
I'm the Architect agent, and I see we don't have any project documentation yet. 

To create a proper development plan, I need to understand what kind of project you want to build. Please tell me:

1. **What is your project about?** (e.g., "a task management web app", "an AI chatbot platform", "a data analytics dashboard")

2. **What are the main features/goals?** (e.g., "users can create and assign tasks", "integrate with external APIs")

3. **Any technical preferences?** (e.g., "React frontend", "Python backend", "microservices architecture")

Or, if you prefer, you can create documentation files in the `docs/` directory first:
- `docs/blueprint.md` - high-level project vision
- `docs/requirements.md` - detailed requirements  
- `docs/architecture.md` - technical approach

What would you like to do? I can help create documentation or answer questions about the development process.
"""
                
                reply = clarifier.ask(
                    question=question,
                    suggestions=[
                        "I want to create docs/blueprint.md for a task management app",
                        "Help me plan a web application project",
                        "I already have docs ready - please check docs/ directory",
                        "Tell me what documentation I should create first"
                    ],
                    timeout=3600  # 1 hour for initial planning
                )
                
                logger.info("[architect] received guidance: %s", reply[:100])
                
                # Process user's reply - generate initial iterations from their description
                logger.info("[architect] processing user guidance to generate initial iterations...")
                
                # Create a basic blueprint doc from user's description  
                blueprint_path = docs_dir / "blueprint.md"
                blueprint_content = f"""# Project Blueprint

## User's Vision
{reply}

## Initial Structure
Based on your description, here's a starting structure for this project:

### Phases
1. **Phase 1: Core Models** - Define data models and domain entities
2. **Phase 2: API Foundation** - Build base API endpoints and services
3. **Phase 3: Integration** - Add features and integrations
4. **Phase 4: Polish** - Testing, documentation, deployment prep

## Next Steps
The agents will now analyze this vision and create detailed iteration plans.
Review and adjust these in your docs/ directory if needed.
"""
                blueprint_path.write_text(blueprint_content)
                logger.info("[architect] created blueprint.md from user guidance")
                
                self.share_context("phase0.blueprint", {
                    "path": str(blueprint_path.relative_to(self.workspace)),
                    "vision": reply,
                    "summary": "Initial project blueprint generated from user guidance.",
                })
                self.broadcast("docs_generated", {
                    "path": str(blueprint_path.relative_to(self.workspace)),
                    "reason": "phase0 planning",
                    "notes": "Architect generated initial project blueprint from user input.",
                })
                
                # Generate a basic iteration plan directly from user input in phase 0
                # No need to call Aider for simple iteration generation
                logger.info("[architect] generating basic iterations from user guidance...")
                
                basic_iterations = [
                    {
                        "id": 1,
                        "phase": 1,
                        "name": "Project foundation & core models",
                        "goal": "Set up project structure and define core domain entities",
                        "layer": "model",
                        "files_expected": ["src/main/java/.../models/Task.java", "src/main/java/.../models/User.java"],
                        "depends_on": [],
                        "acceptance_criteria": [
                            "Core entity models compile",
                            "All required fields present",
                            "Basic validation logic works"
                        ]
                    },
                    {
                        "id": 2,
                        "phase": 1,
                        "name": "Service layer for business logic",
                        "goal": "Implement core business services (task management, user auth)",
                        "layer": "service-core",
                        "files_expected": ["src/main/java/.../services/TaskService.java", "src/main/java/.../services/AuthService.java"],
                        "depends_on": [1],
                        "acceptance_criteria": [
                            "Services created and tested",
                            "Business rules enforced",
                            "In-memory data structures work"
                        ]
                    },
                    {
                        "id": 3,
                        "phase": 1,
                        "name": "CLI interface & application entry point",
                        "goal": "Create CLI that exercises core business logic",
                        "layer": "cli",
                        "files_expected": ["src/main/java/.../Application.java", "src/main/java/.../cli/CliInterface.java"],
                        "depends_on": [1, 2],
                        "acceptance_criteria": [
                            "CLI runs successfully",
                            "Can create tasks, users, and teams via CLI",
                            "All core functionality accessible through CLI"
                        ]
                    },
                    {
                        "id": 4,
                        "phase": 2,
                        "name": "REST API controllers",
                        "goal": "Expose business logic via HTTP endpoints",
                        "layer": "controller",
                        "files_expected": ["src/main/java/.../controllers/TaskController.java", "src/main/java/.../controllers/AuthController.java"],
                        "depends_on": [1, 2],
                        "acceptance_criteria": [
                            "Controllers created and mapped",
                            "Endpoints respond to HTTP requests",
                            "Request/response serialization works"
                        ]
                    },
                    {
                        "id": 5,
                        "phase": 2,
                        "name": "Spring Boot integration & configuration",
                        "goal": "Wire Spring Boot with business logic and controllers",
                        "layer": "config",
                        "files_expected": ["src/main/resources/application.properties", "src/main/java/.../config/AppConfig.java"],
                        "depends_on": [1, 2, 4],
                        "acceptance_criteria": [
                            "Spring Boot starts successfully",
                            "Dependency injection configured",
                            "Server listens on configured port"
                        ]
                    },
                    {
                        "id": 6,
                        "phase": 3,
                        "name": "CI/CD pipeline setup",
                        "goal": "Configure GitHub Actions and deployment",
                        "layer": "cicd",
                        "files_expected": [".github/workflows/build.yml", ".github/workflows/deploy.yml"],
                        "depends_on": [],
                        "acceptance_criteria": [
                            "GitHub Actions workflows created",
                            "Build pipeline works",
                            "Tests run automatically on push"
                        ]
                    },
                    {
                        "id": 7,
                        "phase": 3,
                        "name": "Docker containerization",
                        "goal": "Create Docker image for deployment",
                        "layer": "infra",
                        "files_expected": ["Dockerfile", "docker-compose.yml"],
                        "depends_on": [1, 2, 4, 5],
                        "acceptance_criteria": [
                            "Docker image builds successfully",
                            "Container runs the application",
                            "All services accessible from container"
                        ]
                    }
                ]
                
                # Save the basic iterations
                iterations_file = ai_dir / "iterations.json"
                iterations_file.write_text(json.dumps(basic_iterations, indent=2))
                logger.info("[architect] generated %d basic iterations from phase 0 user input", len(basic_iterations))
                return basic_iterations
                
            except ImportError:
                logger.warning("[architect] comms not available - cannot collaborate in phase 0")
                return []
            except Exception as e:
                logger.error("[architect] clarification failed: %s", e)
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
            message=self._phase_prompt(1, next_id),
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
            message=self._phase_prompt(2, next_id),
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
            message=self._phase_prompt(3, next_id),
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

    def run(self, message: str, read_files: list = None, edit_files: list = None, timeout: int = 300) -> dict:
        """
        Handle chat interactions, especially for phase 0 collaboration.
        """
        # Check if we're in phase 0 (empty docs scenario)
        docs_dir = self.workspace.parent / "docs"  # workspace is typically .ai subdir
        if not docs_dir.exists():
            docs_dir = self.workspace / "docs"  # fallback
        doc_files = list(docs_dir.glob("*.md")) if docs_dir.exists() else []

        if not doc_files:
            # Phase 0: No docs yet - provide collaboration guidance
            if "create" in message.lower() or "draft" in message.lower() or "help" in message.lower():
                # User is asking for help creating docs - provide actual assistance
                # Extract what they're asking to create
                doc_type = "document"
                if "blueprint" in message.lower():
                    doc_type = "blueprint.md"
                elif "requirements" in message.lower():
                    doc_type = "requirements.md"
                elif "architecture" in message.lower():
                    doc_type = "architecture.md"
                elif "api" in message.lower():
                    doc_type = "api-design.md"
                elif "domain" in message.lower():
                    doc_type = "domain-model.md"
                
                phase_0_help_message = f"""
I'll help you create that documentation! Let me provide guidance and a template for `{doc_type}`.

**Your request:** {message}

Since we're in phase 0 with empty docs, I can help you create initial documentation. Here's how we can proceed:

## Template for {doc_type}

I can provide you with a structured template and guidance. Would you like me to:

1. **Give you a complete template** you can copy into `docs/{doc_type}`
2. **Walk through the sections** one by one with explanations
3. **Ask questions** to understand your project better first

For example, if you tell me about your task management application, I can create a tailored blueprint that includes:
- Project vision and goals
- Core features and user stories  
- Technical architecture decisions
- Success criteria and metrics

What would you like me to focus on first? Or shall I provide a general template you can customize?
"""
                return {
                    "success": True,
                    "stdout": phase_0_help_message,
                    "stderr": "",
                    "exit_code": 0
                }
            else:
                # General phase 0 guidance
                phase_0_message = f"""
I see we're in the initial phase 0 bootstrap with empty docs/. As the architect, I can help you plan and specify your project.

**Current State:**
- Project initialized but no documentation exists yet
- All agents are loaded and ready for collaboration
- RAG system initialized for future document indexing

**Next Steps for Collaboration:**

1. **Project Vision & Requirements**
   - Create `docs/blueprint.md`: High-level project vision, goals, and success criteria
   - Create `docs/requirements.md`: Functional and non-functional requirements
   - Create `docs/constraints.md`: Technical constraints, architecture decisions

2. **Technical Specification**
   - Create `docs/architecture.md`: System architecture, components, data flow
   - Create `docs/api-design.md`: API contracts, endpoints, data models
   - Create `docs/domain-model.md`: Core business entities and relationships

3. **Implementation Planning**
   - Once docs are ready, I'll create a phased iteration plan
   - Each phase builds incrementally: core logic → APIs → infrastructure

**How to proceed:**
- Tell me about your project idea and I'll help create the initial documentation
- Or create the docs yourself and run `python agentcraft build` to start the full process
- Use `python agentcraft comms` for multi-agent collaboration UI

What would you like to work on first? I can help draft any of these documents or answer questions about the development approach.

**Your message:** {message}
"""
                return {
                    "success": True,
                    "stdout": phase_0_message,
                    "stderr": "",
                    "exit_code": 0
                }

        # Normal operation with docs present - use standard Aider flow
        return super().run(message, read_files, edit_files, timeout, log_callback=self.log_callback)
