"""
supervisor/agent.py — Supervisor agent.

Central decision-maker for:
- Workflow orchestration (decide which agent to run next)
- Agent collaboration dispatch (@mention coordination)
- Progress supervision and rework decisions
- Quality checks and iteration approval
"""

import json
import logging
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)
SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """
You are the Supervisor Agent — the orchestrator and decision-maker for the entire project.

Your responsibilities:
1. **Workflow Orchestration**: Decide which agent should run next based on project state, completed work, and dependencies
2. **Agent Collaboration**: Coordinate @mentions between agents to foster intelligent collaboration
3. **Progress Supervision**: Monitor agent outputs, evaluate quality, and decide if rework is needed
4. **Decision Making**: Make high-level decisions about which iteration to build next, when to move to the next phase

You have access to:
- Current iterations and their completion status
- Agent outputs and quality metrics
- Project documentation and architecture
- AgentBus for inter-agent communication

Make decisions based on maximizing project progress while maintaining quality standards.
"""


class SupervisorAgent(AiderAgent):
    _role = "supervisor"

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
            role="supervisor",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills or ["orchestration-decision", "agent-collaboration", "quality-review"],
            framework_id=framework_id,
            max_retries=1,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def _log(self, message: str):
        """Send log message to comms server if callback is set."""
        if self.log_callback:
            try:
                self.log_callback(self.role, message)
            except Exception:
                pass
        logger.info("[supervisor] %s", message)

    def decide_next_agent(self, iterations: list[dict], completed: list[int]) -> dict:
        """
        Use LLM to decide which agent should run next based on iteration dependencies.
        
        Returns: {
            "next_agent": "backend_dev" | "test_dev" | "reviewer" | "integration_test" | "cicd",
            "iteration_id": int,
            "reason": str,
            "ready": bool
        }
        """
        pending = [it for it in iterations if it["id"] not in completed]
        if not pending:
            self._log("All iterations complete")
            return {"next_agent": None, "iteration_id": None, "reason": "All iterations complete", "ready": False}
        
        # Build context for LLM decision
        context = f"""You are the Supervisor Agent deciding which iteration to execute next.

## Current State
- Total iterations: {len(iterations)}
- Completed iterations: {completed}
- Pending iterations: {[it['id'] for it in pending]}

## Pending Iterations
"""
        for it in pending:
            deps = it.get("depends_on", [])
            deps_met = all(d in completed for d in deps)
            context += f"""
- Iteration {it['id']}: {it.get('name', '?')}
  Agent: {it.get('agent', 'backend_dev')}
  Dependencies: {deps}
  Dependencies Met: {deps_met}
  Description: {it.get('description', '')[:100]}
"""
        
        # Ask LLM to make the decision
        decision_prompt = f"""{context}

## Your Task
Analyze the current state and decide which iteration should be executed next.

Rules:
1. Only select iterations where ALL dependencies are met
2. Prioritize iterations that unblock the most dependent work
3. Consider logical progression (Phase 1 → Phase 2 → Phase 3)
4. If no iterations have dependencies met, report that we're waiting

Respond in JSON format:
```json
{{
  "next_agent": "agent_name",
  "iteration_id": 123,
  "reason": "Brief explanation of why this iteration should run next"
}}
```

If no iterations are ready:
```json
{{
  "next_agent": null,
  "iteration_id": null,
  "reason": "Explanation of what we're waiting for"
}}
```"""
        
        self._log("Consulting LLM for next iteration decision")
        try:
            result = self.run(
                message=decision_prompt,
                timeout=60,
                log_callback=self.log_callback,
            )
            
            # Extract JSON from response
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', result.get("output", ""), re.DOTALL)
            if json_match:
                decision = json.loads(json_match.group(1))
            else:
                # Try to parse the entire output as JSON
                decision = json.loads(result.get("output", "{}"))
            
            # Validate decision
            iteration_id = decision.get("iteration_id")
            if iteration_id:
                # Verify the iteration exists and dependencies are met
                iteration = next((it for it in iterations if it["id"] == iteration_id), None)
                if iteration:
                    deps = iteration.get("depends_on", [])
                    deps_met = all(d in completed for d in deps)
                    self._log(f"LLM selected iteration {iteration_id}: {iteration.get('name', '?')} → {decision.get('next_agent')}")
                    return {
                        "next_agent": decision.get("next_agent"),
                        "iteration_id": iteration_id,
                        "reason": decision.get("reason", ""),
                        "ready": deps_met
                    }
            
            # No valid iteration selected
            self._log(f"LLM decision: {decision.get('reason', 'No iteration ready')}")
            return {
                "next_agent": None,
                "iteration_id": None,
                "reason": decision.get("reason", "No iteration ready"),
                "ready": False
            }
            
        except Exception as e:
            self._log(f"LLM decision failed: {e}, falling back to rule-based")
            logger.warning("[supervisor] LLM decision failed, using fallback: %s", e)
            
            # Fallback: rule-based selection (emergency only)
            for iteration in pending:
                deps = iteration.get("depends_on", [])
                if all(dep_id in completed for dep_id in deps):
                    agent = iteration.get("agent", "backend_dev")
                    return {
                        "next_agent": agent,
                        "iteration_id": iteration["id"],
                        "reason": f"Rule-based fallback: dependencies met for iteration {iteration['id']}",
                        "ready": True
                    }
            
            return {
                "next_agent": None,
                "iteration_id": None,
                "reason": "Waiting for dependencies (rule-based fallback)",
                "ready": False
            }

    def decide_agent_collaboration(self, agent_state: dict, project_context: dict) -> list[str]:
        """
        Use LLM to decide which agents should collaborate via @mention based on current state.
        
        Returns: list of agent IDs to @mention (e.g., ["backend_dev", "test_dev"])
        """
        collaboration_prompt = f"""You are the Supervisor Agent coordinating agent collaboration.

## Current Agent State
Agent: {agent_state.get('role', 'unknown')}
Phase: {agent_state.get('phase', 'unknown')}
Task: {agent_state.get('task', 'unknown')}
Status: {agent_state.get('status', 'unknown')}

## Project Context
Architecture: {project_context.get('architecture', 'unknown')}
Completed Work: {len(project_context.get('completed', []))} iterations

## Your Task
Determine which agents should collaborate on the current task.

Available agents: architect, backend_dev, test_dev, reviewer, integration_test, cicd, planner, docs_agent

Consider:
1. What phase are we in? (1=architecture, 2=API, 3=infrastructure)
2. What type of work is being done?
3. Which specialists would add value?
4. Who should review the work?

Respond with a JSON list of agent IDs that should collaborate:
```json
["agent1", "agent2"]
```

Or empty list if no collaboration needed:
```json
[]
```"""
        
        self._log(f"Consulting LLM for collaboration decision: {agent_state.get('role', '?')}")
        try:
            result = self.run(
                message=collaboration_prompt,
                timeout=60,
                log_callback=self.log_callback,
            )
            
            # Extract JSON from response
            import re
            output = result.get("output", "")
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                collaboration = json.loads(json_match.group(1))
            else:
                collaboration = json.loads(output)
            
            if collaboration:
                self._log(f"LLM recommends collaboration: {collaboration}")
            else:
                self._log("LLM: No collaboration needed")
            
            return collaboration if isinstance(collaboration, list) else []
            
        except Exception as e:
            self._log(f"LLM collaboration decision failed: {e}")
            logger.warning("[supervisor] LLM collaboration decision failed: %s", e)
            
            # Fallback: rule-based by phase
            phase = agent_state.get("phase", 1)
            if phase == 1:
                return ["architect", "backend_dev"]
            elif phase == 2:
                return ["backend_dev", "test_dev", "reviewer"]
            elif phase == 3:
                return ["cicd", "integration_test", "reviewer"]
            return []

    def evaluate_agent_output(self, agent_id: str, iteration_id: int, result: dict) -> dict:
        """
        Evaluate the quality of an agent's output.
        
        Returns: {
            "approved": bool,
            "quality_score": float (0-100),
            "feedback": str,
            "rework_needed": bool
        }
        """
        success = result.get("success", False)
        exit_code = result.get("exit_code", -1)
        
        if not success or exit_code != 0:
            self._log(f"Agent {agent_id} iteration {iteration_id} FAILED (exit code {exit_code})")
            return {
                "approved": False,
                "quality_score": 0,
                "feedback": f"Agent {agent_id} failed with exit code {exit_code}",
                "rework_needed": True
            }
        
        # LLM-based quality evaluation
        output_preview = result.get("output", "")[:500]
        
        evaluation_prompt = f"""You are the Supervisor Agent evaluating agent output quality.

## Agent Execution
Agent: {agent_id}
Iteration: {iteration_id}
Exit Code: {exit_code}
Success: {success}

## Output Preview
{output_preview}

## Your Task
Evaluate the quality of this agent's output on a scale of 0-100.

Consider:
1. Did the agent complete the task successfully?
2. Is the output complete and well-structured?
3. Are there any obvious errors or issues?
4. Does the output meet professional standards?

Respond in JSON format:
```json
{{
  "quality_score": 85,
  "approved": true,
  "feedback": "Brief assessment of the output quality",
  "rework_needed": false
}}
```

Guidelines:
- 90-100: Excellent, no changes needed
- 70-89: Good, minor improvements possible
- 50-69: Acceptable but needs improvements
- Below 50: Needs significant rework"""
        
        self._log(f"Evaluating {agent_id} iteration {iteration_id} quality")
        try:
            eval_result = self.run(
                message=evaluation_prompt,
                timeout=60,
                log_callback=self.log_callback,
            )
            
            # Extract JSON from response
            import re
            output = eval_result.get("output", "")
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                evaluation = json.loads(json_match.group(1))
            else:
                evaluation = json.loads(output)
            
            quality_score = evaluation.get("quality_score", 50)
            approved = evaluation.get("approved", quality_score >= 70)
            feedback = evaluation.get("feedback", "No feedback provided")
            rework_needed = evaluation.get("rework_needed", quality_score < 70)
            
            self._log(f"Quality score: {quality_score}/100 - {'APPROVED' if approved else 'REJECTED'}")
            
            return {
                "approved": approved,
                "quality_score": quality_score,
                "feedback": feedback,
                "rework_needed": rework_needed
            }
            
        except Exception as e:
            self._log(f"LLM evaluation failed: {e}, defaulting to pass")
            logger.warning("[supervisor] LLM evaluation failed: %s", e)
            
            # Fallback: if execution succeeded, approve it
            return {
                "approved": True,
                "quality_score": 70,
                "feedback": "Execution successful (rule-based fallback)",
                "rework_needed": False
            }

    def decide_phase_transition(self, iterations: list[dict], phase: int) -> dict:
        """
        Decide whether to transition to the next phase.
        
        Returns: {
            "transition": bool,
            "reason": str,
            "next_phase": int | None
        }
        """
        current_phase_iterations = [it for it in iterations if it.get("phase") == phase]
        completed = [it for it in current_phase_iterations if it.get("approved", False)]
        
        if len(completed) == len(current_phase_iterations) and current_phase_iterations:
            return {
                "transition": True,
                "reason": f"All iterations in phase {phase} completed",
                "next_phase": phase + 1
            }
        
        return {
            "transition": False,
            "reason": f"Phase {phase} still has pending iterations ({len(completed)}/{len(current_phase_iterations)} complete)",
            "next_phase": None
        }

    def decide_phase_0(self, project_type: str, workspace: dict) -> dict:
        """
        Decide Phase 0 strategy based on project type (legacy vs greenfield) and architecture style.
        
        Returns: {
            "strategy": "legacy_scan" | "greenfield_clarify",
            "action": str,
            "agents_involved": list[str],
            "next_steps": list[str],
            "architecture_notes": list[str]
        }
        """
        architecture = workspace.get("project", {}).get("architecture", "monolith")
        
        if project_type == "legacy":
            strategy = {
                "strategy": "legacy_scan",
                "action": "Scan existing codebase and generate reference documentation",
                "agents_involved": ["docs_agent"],
                "next_steps": [
                    "Scan legacy source code with provided source paths",
                    "Index existing code in RAG system",
                    "Extract domain concepts and architecture from code",
                    "Generate reference docs (architecture.md, domain-model.md)",
                    "Create API spec from existing endpoints",
                    "Proceed to Phase 1 with code as context"
                ],
                "architecture_notes": []
            }
            
            # Add architecture-specific notes
            if architecture == "microservice":
                strategy["architecture_notes"] = [
                    "Identify existing service boundaries and API contracts",
                    "Document inter-service communication patterns",
                    "Note service-specific technologies and frameworks",
                    "Assess current deployment and orchestration setup"
                ]
            else:  # monolith
                strategy["architecture_notes"] = [
                    "Document monolithic application structure",
                    "Identify internal module boundaries and dependencies",
                    "Note shared components and utilities",
                    "Assess current deployment approach"
                ]
                
            return strategy
            
        else:  # greenfield
            strategy = {
                "strategy": "greenfield_clarify",
                "action": "Supervisor defines phase 0 plan and collaborates with architect for clarification",
                "agents_involved": ["supervisor", "architect"],
                "next_steps": [
                    "Supervisor creates phase 0 clarification plan",
                    "Architect asks user for project vision via comms UI",
                    "Generate blueprint.md from user input",
                    "Generate requirements.md with features",
                    "Generate architecture.md with design approach",
                    "User approves specs through comms collaboration",
                    "Proceed to Phase 1 execution"
                ],
                "architecture_notes": []
            }
            
            # Add architecture-specific guidance
            if architecture == "microservice":
                strategy["architecture_notes"] = [
                    "Clarify service boundaries and domain decomposition",
                    "Define API contracts between services",
                    "Specify technology stack per service",
                    "Plan for service discovery and communication",
                    "Consider deployment orchestration (Kubernetes, Docker Compose)",
                    "Address cross-cutting concerns (auth, logging, monitoring)"
                ]
            else:  # monolith
                strategy["architecture_notes"] = [
                    "Define high-level module structure",
                    "Specify technology stack for the application",
                    "Plan for internal API design",
                    "Consider deployment strategy (single container/app)",
                    "Address scalability and maintainability concerns"
                ]
                
            return strategy

    def execute_phase_0_plan(self, architect_agent, workspace: dict) -> bool:
        """
        Execute Phase 0 plan: define clarification questions and let architect ask user.
        Uses AgentBus for inter-agent communication.
        
        Args:
            architect_agent: ArchitectAgent instance to use for clarification
            workspace: Workspace configuration dict
            
        Returns:
            True if docs were generated, False otherwise
        """
        from pathlib import Path
        
        architecture = workspace.get("project", {}).get("architecture", "monolith")
        docs_dir = Path(workspace.get("docs_dir", "docs"))
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        self._log(f"Executing phase 0 plan for {architecture} architecture")
        logger.info("[supervisor] executing phase 0 plan for %s architecture", architecture)
        
        # Define clarification plan
        clarification_plan = {
            "primary_question": """
I'm the Architect agent working with the Supervisor to plan your project. The Supervisor has asked me to gather some information about what you'd like to build.

To create a proper development plan, I need to understand your project vision. Please tell me:

1. **What is your project about?** (e.g., "a task management web app", "an AI chatbot platform", "a data analytics dashboard")

2. **What are the main features/goals?** (e.g., "users can create and assign tasks", "integrate with external APIs")

3. **Any technical preferences?** (e.g., "React frontend", "Python backend", "microservices architecture")

Your answers will help me create comprehensive documentation and a detailed development plan.
""",
            "suggestions": [
                "I want to create a web application for task management",
                "Help me plan a microservice-based platform",
                "I need a simple monolithic application with REST APIs",
                "I already have documentation ready - please check docs/ directory"
            ]
        }
        
        # Share the clarification plan on the bus
        self.share_context("supervisor.phase0_plan", {
            "architecture": architecture,
            "clarification_plan": clarification_plan,
            "status": "initiated"
        })
        
        # Broadcast phase 0 initiation
        self.broadcast("phase0_started", {
            "strategy": "greenfield_clarify",
            "architecture": architecture,
            "agents_involved": ["supervisor", "architect"]
        })
        
        # Ask architect to gather user clarification via AgentBus
        self._log("Requesting architect to gather user clarification via AgentBus")
        logger.info("[supervisor] ===== about to call ask_agent on AgentBus =====")
        logger.info("[supervisor] asking architect to gather user clarification")
        clarification_request = f"""
Phase 0 Clarification Request from Supervisor
==============================================

Architecture: {architecture}

Please ask the user the following question and return their response:

{clarification_plan['primary_question']}

Suggested answers to offer:
{', '.join(clarification_plan['suggestions'])}

Return the user's exact response.
"""
        
        logger.info("[supervisor] calling self.ask_agent(target_role='architect', ...)")
        user_response = self.ask_agent(
            target_role="architect",
            question=clarification_request,
            context={
                "task_id": "phase-0-clarification",
                "iteration_id": 0,
                "clarification_plan": clarification_plan
            }
        )
        logger.info("[supervisor] ask_agent returned, response length: %d", len(user_response) if user_response else 0)
        
        if not user_response:
            self._log("No user response received")
            logger.warning("[supervisor] no user response received via architect")
            self.share_context("supervisor.phase0_plan", {
                "architecture": architecture,
                "status": "failed",
                "reason": "no user response"
            })
            return False
        
        self._log(f"Received user response: {user_response[:100]}")
        logger.info("[supervisor] received user response via architect: %s", user_response[:100])
        
        # Generate initial documentation from user response
        self._log("Generating phase 0 documentation")
        logger.info("[supervisor] generating phase 0 documentation from user response")
        
        # Create blueprint.md
        blueprint_path = docs_dir / "blueprint.md"
        blueprint_content = f"""# Project Blueprint

## User's Vision
{user_response}

## Project Structure
Based on your description, here's the planned structure:

### Development Phases
1. **Phase 1: Core Models** - Define data models and domain entities
2. **Phase 2: API Foundation** - Build base API endpoints and services  
3. **Phase 3: Integration** - Add features and integrations
4. **Phase 4: Polish** - Testing, documentation, deployment prep

## Architecture Style
{architecture.title()} architecture

## Next Steps
The agents will now analyze this vision and create detailed iteration plans.
Review and adjust these in your docs/ directory if needed.
"""
        blueprint_path.write_text(blueprint_content)
        self._log(f"Created {blueprint_path}")
        logger.info("[supervisor] created %s", blueprint_path)
        
        # Share on bus
        self.share_context("supervisor.phase0_blueprint", {
            "path": str(blueprint_path),
            "vision": user_response,
            "architecture": architecture,
            "summary": "Initial project blueprint generated from user guidance.",
        })
        
        self.share_context("supervisor.phase0_plan", {
            "architecture": architecture,
            "status": "completed",
            "blueprint_path": str(blueprint_path)
        })
        
        # Broadcast completion
        self.broadcast("phase0_completed", {
            "docs_generated": [str(blueprint_path)],
            "architecture": architecture,
            "next_step": "architect_planning"
        })
        
        self._log("Phase 0 documentation complete")
        logger.info("[supervisor] phase 0 documentation complete")
        return True

    def decide_agent_assignment(self, iteration: dict, architecture: str) -> str:
        """
        Decide which agent should handle an iteration based on architecture style.
        
        Args:
            iteration: Iteration dict with name, description, etc.
            architecture: "monolith" or "microservice"
            
        Returns: Agent name ("backend_dev", "config_agent", etc.)
        """
        iteration_name = iteration.get("name", "").lower()
        description = iteration.get("description", "").lower()
        
        # Architecture-specific agent assignments
        if architecture == "microservice":
            # For microservices, prefer specialized agents for service-related work
            if any(keyword in iteration_name + description for keyword in 
                  ["api", "gateway", "service", "microservice", "endpoint"]):
                return "backend_dev"  # Could be specialized service agent
                
            if any(keyword in iteration_name + description for keyword in
                  ["docker", "compose", "kubernetes", "deployment", "orchestration"]):
                return "config_agent"
                
            if any(keyword in iteration_name + description for keyword in
                  ["monitoring", "logging", "tracing", "observability"]):
                return "config_agent"
                
        else:  # monolith
            # For monoliths, standard agent assignments
            if any(keyword in iteration_name + description for keyword in
                  ["database", "model", "entity", "schema"]):
                return "backend_dev"
                
            if any(keyword in iteration_name + description for keyword in
                  ["config", "deployment", "infrastructure"]):
                return "config_agent"
        
        # Default assignment
        return iteration.get("agent", "backend_dev")

    def decide_service_architecture(self, services: list[dict], architecture: str) -> dict:
        """
        For microservice projects, decide on service architecture and communication patterns.
        
        Args:
            services: List of service definitions
            architecture: Should be "microservice"
            
        Returns: Architecture decisions dict
        """
        if architecture != "microservice":
            return {"pattern": "monolith", "services": [], "communication": "internal"}
            
        decisions = {
            "pattern": "microservice",
            "services": services,
            "communication": {
                "protocol": "REST",  # or "gRPC", "GraphQL"
                "discovery": "service-registry",
                "gateway": "api-gateway",
                "auth": "jwt-tokens"
            },
            "deployment": {
                "orchestration": "docker-compose",  # or "kubernetes"
                "scaling": "horizontal",
                "monitoring": "centralized"
            },
            "cross_cutting": [
                "authentication",
                "logging", 
                "monitoring",
                "configuration",
                "circuit-breakers"
            ]
        }
        
        return decisions
