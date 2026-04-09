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
        
        # Read project context to generate specific iterations
        project_context = self._read_project_context()
        
        PHASE_DESC = {
            1: (
                "Phase 1 — core logic only.\n"
                "NO Spring web, NO HTTP, NO external calls, NO file persistence.\n"
                "Only: domain model, business logic, in-memory data, interfaces.\n"
                "For this Java CLI calculator project, focus on:\n"
                "- Operation enum (ADD, SUBTRACT, MULTIPLY, DIVIDE)\n"
                "- Calculator core logic with arithmetic operations\n"
                "- In-memory calculation history tracking"
                f"{arch_note}"
            ),
            2: (
                "Phase 2 — CLI layer.\n"
                "Command-line interface, input parsing, output formatting.\n"
                "For this calculator project, focus on:\n"
                "- CLI input parsing (e.g., 'ADD 5 3')\n"
                "- Interactive command loop\n"
                "- History display functionality\n"
                "- Error handling for invalid input"
                f"{arch_note}"
            ),
            3: (
                "Phase 3 — infrastructure only.\n"
                "Dockerfile, build configuration, CI pipeline.\n"
                "For this Java project, focus on:\n"
                "- Maven/Gradle build configuration\n"
                "- Docker containerization\n"
                "- CI/CD pipeline for automated testing and deployment"
                f"{arch_note}"
            ),
        }
        
        # Analyze project context to generate appropriate examples
        project_context = self._read_project_context()
        
        # Determine project type and generate appropriate examples
        is_java_cli = "Java" in project_context and "CLI" in project_context
        is_calculator = "calculator" in project_context.lower()
        
        if is_java_cli and is_calculator:
            # Use the specific calculator examples
            examples = self._get_calculator_examples(phase, start_id)
        else:
            # Generate generic examples based on project type
            examples = self._get_generic_examples(phase, start_id, project_context)
        
        example_json = json.dumps(examples, indent=2)
        
        return (
            f"Based on the project configuration and available documentation, plan concrete iterations for {PHASE_DESC[phase]}\n\n"
            f"Project Context: {project_context}\n\n"
            f"Start iteration IDs from {start_id}.\n"
            f"Each iteration should be 2-4 files max, with a clear, specific goal.\n"
            f"CRITICAL: Generate REAL, ACTIONABLE iterations specific to this project.\n"
            f"Do NOT use generic templates like 'short name' or 'path/to/File.java'.\n"
            f"Adapt to the project's technology stack and requirements.\n\n"
            f"Here are concrete examples for Phase {phase}:\n"
            f"{example_json}\n\n"
            f"Output ONLY a valid JSON array of iterations for Phase {phase}:\n"
        )

    def _read_project_context(self) -> str:
        """Read project configuration and generated content to provide context for planning."""
        context_parts = []
        
        # 1. First read workspace.yaml for initial project configuration
        workspace_yaml = self.workspace.parent / "workspace.yaml"
        if workspace_yaml.exists():
            try:
                import yaml
                ws_config = yaml.safe_load(workspace_yaml.read_text()) or {}
                project_info = ws_config.get("project", {})
                
                context_parts.append(f"Project: {project_info.get('name', 'Unknown')}")
                context_parts.append(f"Description: {project_info.get('description', 'No description')}")
                context_parts.append(f"Type: {project_info.get('type', 'Unknown')}")
                context_parts.append(f"Architecture: {project_info.get('architecture', 'Unknown')}")
                
                # Include output layout expectations
                output_layout = ws_config.get("output_layout", [])
                if output_layout:
                    layout_desc = [f"- {item.get('path', '')}: {item.get('description', '')}" for item in output_layout]
                    context_parts.append(f"Expected Output Layout:\n" + "\n".join(layout_desc))
                    
            except Exception as e:
                logger.warning(f"Failed to read workspace.yaml: {e}")
        
        # 2. Then read .ai content if it exists (generated during workflow)
        ai_dir = self.workspace / ".ai"
        
        # Read spec.md
        spec_file = ai_dir / "spec.md"
        if spec_file.exists():
            spec_content = spec_file.read_text()
            context_parts.append(f"Specification: {spec_content[:500]}...")  # First 500 chars
        
        # Read use_cases.md
        use_cases_file = ai_dir / "use_cases.md"
        if use_cases_file.exists():
            use_cases_content = use_cases_file.read_text()
            context_parts.append(f"Use Cases: {use_cases_content[:500]}...")  # First 500 chars
            
        # Read entities.md if it exists
        entities_file = ai_dir / "entities.md"
        if entities_file.exists():
            entities_content = entities_file.read_text()
            context_parts.append(f"Entities: {entities_content[:300]}...")  # First 300 chars
        
        if not context_parts:
            return "No project context available. Please ensure workspace.yaml exists with project configuration."
        
        return " | ".join(context_parts)

    def _get_calculator_examples(self, phase: int, start_id: int) -> list:
        """Get specific examples for Java CLI calculator project."""
        examples = {
            1: [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Operation Types & Enum",
                    "goal": "Define arithmetic operations (ADD, SUBTRACT, MULTIPLY, DIVIDE) as enum",
                    "layer": "model",
                    "files_expected": ["src/main/java/com/example/Operation.java"],
                    "depends_on": [],
                    "acceptance_criteria": ["Operation enum compiles", "Has ADD, SUBTRACT, MULTIPLY, DIVIDE values", "Each operation has toString() method"]
                },
                {
                    "id": start_id + 1,
                    "phase": phase,
                    "name": "Calculator Core Logic",
                    "goal": "Implement calculator with arithmetic operations and error handling",
                    "layer": "model",
                    "files_expected": ["src/main/java/com/example/Calculator.java"],
                    "depends_on": [start_id],
                    "acceptance_criteria": ["Calculator class compiles", "calculate() method works for all operations", "Division by zero throws appropriate exception"]
                },
                {
                    "id": start_id + 2,
                    "phase": phase,
                    "name": "Calculation History",
                    "goal": "Implement in-memory history tracking for past calculations",
                    "layer": "model",
                    "files_expected": ["src/main/java/com/example/CalculationResult.java", "src/main/java/com/example/History.java"],
                    "depends_on": [start_id + 1],
                    "acceptance_criteria": ["CalculationResult stores operation, operands, result", "History maintains list of results", "History has add() and getAll() methods"]
                }
            ],
            2: [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "CLI Input Parser",
                    "goal": "Parse command-line input like 'ADD 5 3' into operation and operands",
                    "layer": "cli",
                    "files_expected": ["src/main/java/com/example/InputParser.java"],
                    "depends_on": [start_id - 2],  # Depends on Operation enum
                    "acceptance_criteria": ["Parses 'OPERATION operand1 operand2' format", "Validates numeric operands", "Rejects invalid operations", "Returns Operation and double[]"]
                },
                {
                    "id": start_id + 1,
                    "phase": phase,
                    "name": "Interactive CLI Application",
                    "goal": "Build main CLI loop that integrates parser, calculator, and history",
                    "layer": "cli",
                    "files_expected": ["src/main/java/com/example/Main.java"],
                    "depends_on": [start_id, start_id + 1, start_id + 2],  # Depends on parser, calculator, history
                    "acceptance_criteria": ["Reads from stdin in loop", "Displays results after calculations", "'HISTORY' command shows past results", "'EXIT' command terminates gracefully"]
                }
            ],
            3: [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Build Configuration & Docker",
                    "goal": "Create Maven pom.xml and Dockerfile for containerized deployment",
                    "layer": "ops",
                    "files_expected": ["pom.xml", "Dockerfile"],
                    "depends_on": [start_id - 3],  # Depends on main application
                    "acceptance_criteria": ["pom.xml compiles project successfully", "Dockerfile builds runnable image", "Container runs calculator CLI", "All dependencies properly configured"]
                },
                {
                    "id": start_id + 1,
                    "phase": phase,
                    "name": "CI Pipeline",
                    "goal": "Setup GitHub Actions for automated build, test, and deployment",
                    "layer": "ops",
                    "files_expected": [".github/workflows/ci.yml"],
                    "depends_on": [start_id],
                    "acceptance_criteria": ["Pipeline triggers on push/PR", "Runs Maven build and tests", "Builds Docker image", "Fails on compilation errors or test failures"]
                }
            ]
        }
        return examples.get(phase, [])

    def _get_generic_examples(self, phase: int, start_id: int, project_context: str) -> list:
        """Get generic examples based on project type and technology stack."""
        # Analyze project context to determine technology stack
        is_java = "Java" in project_context or "Maven" in project_context
        is_python = "Python" in project_context
        is_web = "web" in project_context.lower() or "api" in project_context.lower()
        is_cli = "cli" in project_context.lower() or "command" in project_context.lower()
        
        if is_java:
            return self._get_java_examples(phase, start_id, is_web, is_cli)
        elif is_python:
            return self._get_python_examples(phase, start_id, is_web, is_cli)
        else:
            return self._get_generic_tech_examples(phase, start_id)

    def _get_java_examples(self, phase: int, start_id: int, is_web: bool = False, is_cli: bool = False) -> list:
        """Get Java-specific examples."""
        if phase == 1:
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Core Domain Model",
                    "goal": "Define core domain classes and business logic",
                    "layer": "model",
                    "files_expected": ["src/main/java/com/example/domain/Model.java"],
                    "depends_on": [],
                    "acceptance_criteria": ["Domain classes compile successfully", "Business logic is implemented", "Unit tests pass"]
                },
                {
                    "id": start_id + 1,
                    "phase": phase,
                    "name": "Data Access Layer",
                    "goal": "Implement data persistence and repository interfaces",
                    "layer": "model",
                    "files_expected": ["src/main/java/com/example/repository/Repository.java"],
                    "depends_on": [start_id],
                    "acceptance_criteria": ["Repository interfaces defined", "Data access methods implemented", "Integration tests pass"]
                }
            ]
        elif phase == 2:
            if is_web:
                return [
                    {
                        "id": start_id,
                        "phase": phase,
                        "name": "REST Controllers",
                        "goal": "Create Spring Boot REST controllers with endpoints",
                        "layer": "api",
                        "files_expected": ["src/main/java/com/example/controller/ApiController.java"],
                        "depends_on": [start_id - 2],
                        "acceptance_criteria": ["Controllers compile", "Endpoints return correct responses", "HTTP status codes are appropriate"]
                    }
                ]
            else:  # CLI
                return [
                    {
                        "id": start_id,
                        "phase": phase,
                        "name": "Command Line Interface",
                        "goal": "Implement CLI with argument parsing and command handling",
                        "layer": "cli",
                        "files_expected": ["src/main/java/com/example/cli/CliApplication.java"],
                        "depends_on": [start_id - 2],
                        "acceptance_criteria": ["CLI accepts command arguments", "Commands execute successfully", "Help text is displayed"]
                    }
                ]
        else:  # Phase 3
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Build & Deployment",
                    "goal": "Configure Maven build and Docker containerization",
                    "layer": "ops",
                    "files_expected": ["pom.xml", "Dockerfile"],
                    "depends_on": [start_id - 3],
                    "acceptance_criteria": ["Maven build succeeds", "Docker image builds", "Application runs in container"]
                }
            ]

    def _get_python_examples(self, phase: int, start_id: int, is_web: bool = False, is_cli: bool = False) -> list:
        """Get Python-specific examples."""
        if phase == 1:
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Core Models & Logic",
                    "goal": "Define core data models and business logic classes",
                    "layer": "model",
                    "files_expected": ["src/models.py"],
                    "depends_on": [],
                    "acceptance_criteria": ["Models are properly defined", "Business logic functions work", "Unit tests pass"]
                }
            ]
        elif phase == 2:
            if is_web:
                return [
                    {
                        "id": start_id,
                        "phase": phase,
                        "name": "FastAPI Routes",
                        "goal": "Create FastAPI route handlers and endpoints",
                        "layer": "api",
                        "files_expected": ["src/routes.py"],
                        "depends_on": [start_id - 1],
                        "acceptance_criteria": ["API endpoints respond correctly", "Request/response models work", "Error handling is implemented"]
                    }
                ]
            else:  # CLI
                return [
                    {
                        "id": start_id,
                        "phase": phase,
                        "name": "CLI Commands",
                        "goal": "Implement Click-based CLI commands",
                        "layer": "cli",
                        "files_expected": ["src/cli.py"],
                        "depends_on": [start_id - 1],
                        "acceptance_criteria": ["CLI commands work", "Arguments are parsed correctly", "Help is displayed"]
                    }
                ]
        else:  # Phase 3
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Packaging & Deployment",
                    "goal": "Configure packaging and container deployment",
                    "layer": "ops",
                    "files_expected": ["requirements.txt", "Dockerfile"],
                    "depends_on": [start_id - 2],
                    "acceptance_criteria": ["Package installs correctly", "Docker container builds", "Application runs in container"]
                }
            ]

    def _get_generic_tech_examples(self, phase: int, start_id: int) -> list:
        """Get generic examples when technology stack is unclear."""
        if phase == 1:
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Core Implementation",
                    "goal": "Implement core functionality and business logic",
                    "layer": "core",
                    "files_expected": ["src/core.py"],
                    "depends_on": [],
                    "acceptance_criteria": ["Core functionality works", "Business logic is correct", "Basic tests pass"]
                }
            ]
        elif phase == 2:
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "User Interface",
                    "goal": "Create user interface for interacting with core functionality",
                    "layer": "ui",
                    "files_expected": ["src/ui.py"],
                    "depends_on": [start_id - 1],
                    "acceptance_criteria": ["UI accepts user input", "Displays results correctly", "Error handling works"]
                }
            ]
        else:  # Phase 3
            return [
                {
                    "id": start_id,
                    "phase": phase,
                    "name": "Build & Deploy",
                    "goal": "Configure build system and deployment",
                    "layer": "ops",
                    "files_expected": ["Dockerfile", "Makefile"],
                    "depends_on": [start_id - 2],
                    "acceptance_criteria": ["Build succeeds", "Deployment works", "Application is accessible"]
                }
            ]

    def plan(self, docs_dir: Path) -> list[dict]:
        self.report_status("running")
        # Load architecture from workspace config
        architecture = self._load_architecture()
        logger.info("[architect] planning for %s architecture", architecture)
        
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir(exist_ok=True)
        iterations_file = ai_dir / "iterations.json"

        # Read docs from provided directory (may be empty initially)
        doc_files = list(docs_dir.glob("*.md")) if docs_dir.exists() else []
        logger.info("[architect] reading %d doc files from %s", len(doc_files), docs_dir)
        
        # Also check .ai directory for any generated content
        ai_doc_files = list(ai_dir.glob("*.md"))
        all_docs = doc_files + ai_doc_files
        
        # Even with no docs, we can still plan based on workspace.yaml context
        if not all_docs:
            logger.info("[architect] no docs found, but will use workspace.yaml context for planning")
        
        logger.info("[architect] total context files: %d (docs: %d, .ai: %d)", 
                   len(all_docs), len(doc_files), len(ai_doc_files))

        # Clear any existing phase files to ensure fresh generation
        for phase_num in [1, 2, 3]:
            phase_file = ai_dir / f"phase{phase_num}.json"
            if phase_file.exists():
                phase_file.unlink()
                logger.info("[architect] cleared existing phase%d.json for fresh generation", phase_num)

        all_iterations: list[dict] = []
        next_id = 1

        # ── Step 1: Phase 1 iterations ────────────────────────────────────────
        logger.info("[architect] planning Phase 1 (core logic)")
        phase1_file = ai_dir / "phase1.json"
        result1 = self.run(
            message=self._phase_prompt(1, next_id, architecture),
            read_files=all_docs,  # Include all available context
            edit_files=[phase1_file],
            log_callback=self.log_callback,
        )
        
        # Try to save phase JSON (handles both file and stdout extraction)
        if not self._save_phase_json(phase1_file, result1):
            logger.error("[architect] Phase 1 planning failed - could not extract iterations")
            return []
        
        phase1 = self.read_json(phase1_file, [])
        phase1 = self._renumber(phase1, next_id, phase=1)
        all_iterations.extend(phase1)
        next_id += len(phase1)

        # ── Step 2: Phase 2 iterations ────────────────────────────────────────
        logger.info("[architect] planning Phase 2 (CLI layer)")
        phase2_file = ai_dir / "phase2.json"
        ctx2 = all_docs + [phase1_file]  # Include phase1 for context
        result2 = self.run(
            message=self._phase_prompt(2, next_id, architecture),
            read_files=ctx2,
            edit_files=[phase2_file],
            log_callback=self.log_callback,
        )
        
        # Try to save phase JSON (handles both file and stdout extraction)
        if self._save_phase_json(phase2_file, result2):
            phase2 = self.read_json(phase2_file, [])
            phase2 = self._renumber(phase2, next_id, phase=2)
            all_iterations.extend(phase2)
            next_id += len(phase2)
        else:
            logger.warning("[architect] Phase 2 planning failed - continuing with Phase 1 only")

        # ── Step 3: Phase 3 (infrastructure) ────────────────────────────────
        logger.info("[architect] planning Phase 3 (infrastructure)")
        phase3_file = ai_dir / "phase3.json"
        ctx3 = all_docs + [phase1_file, phase2_file] if phase2_file.exists() else all_docs + [phase1_file]
        result3 = self.run(
            message=self._phase_prompt(3, next_id, architecture),
            read_files=ctx3,
            edit_files=[phase3_file],
            log_callback=self.log_callback,
        )
        
        # Try to save phase JSON (handles both file and stdout extraction)
        if self._save_phase_json(phase3_file, result3):
            phase3 = self.read_json(phase3_file, [])
            phase3 = self._renumber(phase3, next_id, phase=3)
            all_iterations.extend(phase3)
        else:
            logger.warning("[architect] Phase 3 planning failed or empty - skipping")

        if not all_iterations:
            logger.error("[architect] produced no iterations")
            return []

        iterations_file.write_text(json.dumps(all_iterations, indent=2))
        logger.info("[architect] total: %d iterations across 3 phases", len(all_iterations))
        self.emit_file_written(iterations_file)

        # Post completion update
        self.complete(f"Planning complete: {len(all_iterations)} iterations across 3 phases", file=str(iterations_file))

        # Share on bus for other agents
        self.share_context("iteration_plan", all_iterations)
        self.report_status("idle")
        return all_iterations

        iterations_file.write_text(json.dumps(all_iterations, indent=2))
        logger.info("[architect] total: %d iterations across 3 phases", len(all_iterations))
        self.emit_file_written(iterations_file)

        # Post completion update
        self.complete(f"Planning complete: {len(all_iterations)} iterations across 3 phases", file=str(iterations_file))

        # Share on bus for other agents
        self.share_context("iteration_plan", all_iterations)
        self.report_status("idle")
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

    def _extract_json_from_output(self, output: str) -> dict:
        """
        Try to extract JSON from LLM output.
        Handles cases where aider didn't write to file but LLM generated JSON.
        """
        import re
        # Remove markdown code fences
        output = re.sub(r'```(?:json)?\n?', '', output).strip()
        
        # Find JSON array or object
        for start_ch, end_ch in [('[', ']'), ('{', '}')]:
            s = output.find(start_ch)
            if s == -1:
                continue
            depth = 0
            for i, ch in enumerate(output[s:], s):
                if ch == start_ch:
                    depth += 1
                elif ch == end_ch:
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(output[s:i+1]), True  # (result, is_array)
                    except json.JSONDecodeError:
                        continue
        return None, False

    def _is_template_iteration(self, iteration: dict) -> bool:
        """Check if iteration is just a template placeholder."""
        template_markers = [
            "short name", "one sentence", "path/to/", "File.java",
            "compiles", "model"
        ]
        # Check if too many template markers are present
        markers_found = sum(1 for marker in template_markers if marker.lower() in str(iteration).lower())
        return markers_found >= 3

    def _validate_iterations(self, iterations: list) -> bool:
        """Validate that iterations are real, not templates."""
        if not iterations:
            return False
        
        # Check if all iterations are templates
        template_count = sum(1 for it in iterations if self._is_template_iteration(it))
        
        if template_count == len(iterations):
            logger.warning("[architect] all %d iterations are templates, rejecting", len(iterations))
            return False
        
        if template_count > 0:
            logger.warning("[architect] %d/%d iterations are templates, but proceeding", template_count, len(iterations))
        
        return True

    def _save_phase_json(self, phase_file: Path, result: dict) -> bool:
        """
        Process phase planning result:
        1. If file exists and has content, validate and return
        2. If file is empty but result has JSON in stdout, extract and save it
        3. Return success status
        """
        # If file already has content, validate it
        if phase_file.exists() and phase_file.stat().st_size > 0:
            logger.info("[architect] %s already has content, validating...", phase_file.name)
            existing_data = self.read_json(phase_file, [])
            if self._validate_iterations(existing_data):
                return True
            else:
                logger.warning("[architect] %s contains only templates, will try to replace", phase_file.name)
                # Continue below to extract from stdout
        
        # Try to extract JSON from stdout if file is empty or invalid
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        
        if not stdout:
            logger.error("[architect] no stdout from LLM - stderr: %s", stderr[:200] if stderr else "empty")
            return False
            
        parsed, is_list = self._extract_json_from_output(stdout)
        
        if parsed is not None:
            # If it's a dict and we expected a list, wrap it
            data = parsed if is_list else [parsed] if isinstance(parsed, dict) else parsed
            
            # Validate the extracted data
            if not self._validate_iterations(data):
                logger.error("[architect] extracted JSON contains only templates")
                return False
            
            logger.info("[architect] extracted JSON from stdout (%d items), saving to %s", 
                       len(data) if isinstance(data, list) else 1, phase_file.name)
            phase_file.write_text(json.dumps(data, indent=2))
            return True
        
        logger.error("[architect] could not extract JSON from stdout. First 500 chars: %s", stdout[:500])
        return False

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
        logger.info("[architect] ===== handle_query invoked via AgentBus =====")
        logger.info("[architect] received query from agent bus: %s", question[:80])
        logger.info("[architect] context keys: %s", list(context.keys()) if context else "none")
        
        # Check if this is a phase 0 clarification request
        if "phase 0" in question.lower() or "clarification" in question.lower():
            # Extract the question to ask user
            clarification_plan = context.get("clarification_plan", {})
            user_question = clarification_plan.get("primary_question", question)
            suggestions = clarification_plan.get("suggestions", [])
            
            logger.info("[architect] handling phase 0 clarification request")
            logger.info("[architect] will ask user via comms system")
            
            # Ask user for clarification
            user_response = self.request_clarification(
                question=user_question,
                context=context,
                suggestions=suggestions
            )
            
            if user_response:
                logger.info("[architect] user responded, broadcasting to bus")
                # Broadcast that architect has gathered user input
                self.broadcast("architect.clarification_received", {
                    "response_length": len(user_response),
                    "task_id": context.get("task_id", "unknown"),
                    "preview": user_response[:100]
                })
            else:
                logger.warning("[architect] no user response received")
            
            return user_response
        
        logger.info("[architect] query not phase 0 related, using default LLM handler")
        # Default: use parent class handler (local LLM)
        return super().handle_query(question, context)

    def run(self, message: str, read_files: list = None, edit_files: list = None, timeout: int = None, log_callback: callable = None) -> dict:
        """
        Standard Aider agent run - delegates to parent class.
        """
        # Use provided log_callback or fall back to self.log_callback
        cb = log_callback if log_callback is not None else self.log_callback
        return super().run(message, read_files, edit_files, timeout, log_callback=cb)
