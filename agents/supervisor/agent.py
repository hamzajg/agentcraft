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

    def decide_next_agent(self, iterations: list[dict], completed: list[int]) -> dict:
        """
        Decide which agent should run next based on iteration dependencies.
        
        Returns: {
            "next_agent": "backend_dev" | "test_dev" | "reviewer" | "integration_test" | "cicd",
            "iteration_id": int,
            "reason": str,
            "ready": bool  # Are all dependencies met?
        }
        """
        pending = [it for it in iterations if it["id"] not in completed]
        if not pending:
            return {"next_agent": None, "iteration_id": None, "reason": "All iterations complete", "ready": False}
        
        # Find the next iteration with all dependencies met
        for iteration in pending:
            deps = iteration.get("depends_on", [])
            if all(dep_id in completed for dep_id in deps):
                agent = iteration.get("agent", "backend_dev")
                return {
                    "next_agent": agent,
                    "iteration_id": iteration["id"],
                    "reason": f"All dependencies met for iteration {iteration['id']}: {iteration.get('name', '?')}",
                    "ready": True
                }
        
        return {
            "next_agent": None,
            "iteration_id": None,
            "reason": "Waiting for dependencies",
            "ready": False
        }

    def decide_agent_collaboration(self, agent_state: dict, project_context: dict) -> list[str]:
        """
        Decide which agents should collaborate via @mention based on current state.
        
        Returns: list of agent IDs to @mention (e.g., ["backend_dev", "test_dev"])
        """
        collaboration = []
        
        # If architecture/design phase, involve architect + backend_dev
        if agent_state.get("phase") == 1:
            collaboration = ["architect", "backend_dev"]
        
        # API layer needs test_dev for test planning
        elif agent_state.get("phase") == 2:
            collaboration = ["backend_dev", "test_dev", "reviewer"]
        
        # Infrastructure phase needs test_dev and cicd
        elif agent_state.get("phase") == 3:
            collaboration = ["cicd", "integration_test", "reviewer"]
        
        return collaboration

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
            return {
                "approved": False,
                "quality_score": 0,
                "feedback": f"Agent {agent_id} failed with exit code {exit_code}",
                "rework_needed": True
            }
        
        # Basic quality check: success means approved for now
        return {
            "approved": True,
            "quality_score": 85,
            "feedback": f"Agent {agent_id} completed iteration {iteration_id} successfully",
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
                "action": "Request project clarification from user via collaborative dialogue",
                "agents_involved": ["architect"],
                "next_steps": [
                    "Ask user for project vision via comms UI",
                    "Architect guides through specification process",
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
