"""
supervisor/agent.py — Supervisor agent.

ROLE: Context gatherer and task orchestrator.

This agent:
- Gathers context from the workspace, docs, and other agents
- Prepares information for LLM decision-making
- Executes tasks by delegating to specialized agents
- Monitors progress and reports status

ALL DECISIONS ARE MADE BY LLM within this agent.
No hardcoded decision logic exists here.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Supervisor Agent.

Your role is to orchestrate the AI agent team by gathering context and delegating tasks.
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
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or [],
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

    def gather_project_context(self) -> dict:
        """
        Gather all relevant context for the project.
        
        Returns:
            Dictionary containing workspace, docs, and agent state.
        """
        context = {
            "workspace": self._gather_workspace_info(),
            "docs": self._gather_docs_info(),
            "agents": self._gather_agent_info(),
        }
        return context

    def _gather_workspace_info(self) -> dict:
        """Gather workspace information."""
        workspace_info = {"path": str(self.workspace)}
        
        workspace_yaml = self.workspace / "workspace.yaml"
        if workspace_yaml.exists():
            import yaml
            workspace_info["config"] = yaml.safe_load(workspace_yaml.read_text())
        
        return workspace_info

    def _gather_docs_info(self) -> dict:
        """Gather documentation information."""
        docs_dir = self.workspace / "docs"
        ai_dir = self.workspace / ".ai"
        
        docs_info = {
            "exists": docs_dir.exists(),
            "files": [],
        }
        
        if docs_dir.exists():
            docs_info["files"] = [
                {"name": f.name, "path": str(f)}
                for f in docs_dir.glob("*.md")
            ]
        
        ai_info = {
            "exists": ai_dir.exists(),
            "files": [],
        }
        
        if ai_dir.exists():
            ai_info["files"] = [
                {"name": f.name, "path": str(f)}
                for f in ai_dir.glob("*.md")
            ]
            ai_info["files"].extend([
                {"name": f.name, "path": str(f)}
                for f in ai_dir.glob("*.json")
            ])
        
        return {"docs": docs_info, "workflow": ai_info}

    def _gather_agent_info(self) -> dict:
        """Gather information about available agents."""
        from core.bus import AgentBus
        bus = AgentBus.instance()
        
        return {
            "available_agents": list(bus.list_agents()),
            "context_snapshot": bus.context_snapshot(),
        }

    def prepare_task_for_agent(
        self,
        agent_role: str,
        task_description: str,
        context: dict = None,
    ) -> str:
        """
        Prepare a clear task prompt for a specific agent.
        
        Args:
            agent_role: Which agent should execute the task
            task_description: What needs to be done
            context: Additional context to include
            
        Returns:
            Formatted prompt for the agent
        """
        context_str = json.dumps(context, indent=2) if context else "No additional context."
        
        prompt = f"""## Task for {agent_role}

### Task Description
{task_description}

### Context
{context_str}

### Instructions
1. Read any relevant files mentioned in the context
2. Execute the task as described
3. Report completion status
4. Write any files to the workspace

Be thorough and follow best practices for {agent_role} work.
"""
        return prompt

    def _query_llm(self, prompt: str) -> dict:
        """Query the LLM and return structured JSON response."""
        if self._llm:
            response = self._llm.generate(prompt, model=self.model)
        else:
            from core.llm import OllamaClient
            client = OllamaClient(model=self.model)
            response = client.generate(prompt)
        return self._parse_llm_response(response)

    def _parse_llm_response(self, response: str) -> dict:
        """Parse JSON from LLM response."""
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("[supervisor] Failed to parse JSON: %s", response[:200])
            return {"error": "Failed to parse response", "raw": response}

    def decide_next_action(
        self,
        available_actions: list[str],
        current_state: dict,
        history: list[dict] = None,
    ) -> dict:
        """Decide what action to take next using LLM."""
        history_text = ""
        if history:
            history_text = "\n".join([
                f"- {h.get('action')}: {h.get('reasoning', '')[:100]}"
                for h in history[-5:]
            ])
        state_text = json.dumps(current_state, indent=2)
        prompt = f"""You are a decision-making agent. Based on the current state and available actions, decide what to do next.

## Available Actions
{json.dumps(available_actions, indent=2)}

## Current State
{state_text}

## Recent History (last 5 decisions)
{history_text or "No history yet."}

## Task
Analyze the current state and decide which action to take next.

Respond ONLY with valid JSON:
```json
{{
  "action": "action_name",
  "reasoning": "Why this action makes sense",
  "confidence": 0.85,
  "priority": "high|medium|low"
}}
```"""
        return self._query_llm(prompt)

    def decide_approval(
        self,
        submission: dict,
        requirements: list[str],
        previous_feedback: list[str] = None,
    ) -> dict:
        """Decide whether to approve a submission using LLM."""
        req_text = "\n".join([f"- {r}" for r in requirements])
        fb_text = "\n".join([f"- {f}" for f in previous_feedback]) if previous_feedback else "No previous feedback."
        prompt = f"""You are a code review agent. Decide whether to approve this submission.

## Submission
{json.dumps(submission, indent=2)}

## Requirements (must be met for approval)
{req_text}

## Previous Feedback
{fb_text}

## Task
Review the submission against requirements.

Respond ONLY with valid JSON:
```json
{{
  "approved": true,
  "reasoning": "Why this was approved or rejected",
  "feedback": ["feedback point 1"],
  "must_fix": ["critical issue 1"] (only if not approved, empty array otherwise)
}}
```"""
        return self._query_llm(prompt)

    def decide_agent_team(
        self,
        task_description: str,
        available_agents: list[dict],
        current_team: list[str] = None,
    ) -> dict:
        """Decide which agents should work on a task using LLM."""
        agents_text = json.dumps(available_agents, indent=2)
        current_text = json.dumps(current_team) if current_team else "None"
        prompt = f"""You are an orchestration agent. Decide which AI agents should work on this task.

## Task Description
{task_description}

## Available Agents
{agents_text}

## Currently Assigned
{current_text}

## Task
Determine the optimal agent team for this task.

Respond ONLY with valid JSON:
```json
{{
  "agents": ["agent1", "agent2"],
  "reasoning": "Why these agents were selected",
  "coordination": "How should they collaborate?",
  "priority": "high|medium|low"
}}
```"""
        return self._query_llm(prompt)

    def decide_phase_transition(
        self,
        current_phase: int,
        phase_completion: dict,
        overall_progress: float,
    ) -> dict:
        """Decide whether to transition to the next phase using LLM."""
        prompt = f"""You are a project management agent. Decide if we should transition to the next phase.

## Current State
- Current Phase: {current_phase}
- Phase Completion: {json.dumps(phase_completion, indent=2)}
- Overall Progress: {overall_progress:.1%}

## Task
Analyze the completion status and decide if we should transition to the next phase.

Respond ONLY with valid JSON:
```json
{{
  "should_transition": true,
  "reasoning": "Why transitioning now makes sense",
  "next_phase": {current_phase + 1},
  "confidence": 0.9,
  "blockers": []
}}
```"""
        return self._query_llm(prompt)

    def request_decision(
        self,
        decision_type: str,
        context: dict,
    ) -> dict:
        """
        Request a decision from the LLM.
        
        Args:
            decision_type: Type of decision (next_action, approval, team, etc.)
            context: Context for the decision
            
        Returns:
            LLM's decision response
        """
        if decision_type == "next_action":
            return self.decide_next_action(
                available_actions=context.get("available_actions", []),
                current_state=context.get("current_state", {}),
                history=context.get("history", []),
            )
        elif decision_type == "approval":
            return self.decide_approval(
                submission=context.get("submission", {}),
                requirements=context.get("requirements", []),
                previous_feedback=context.get("previous_feedback", []),
            )
        elif decision_type == "team":
            return self.decide_agent_team(
                task_description=context.get("task_description", ""),
                available_agents=context.get("available_agents", []),
                current_team=context.get("current_team", []),
            )
        elif decision_type == "phase_transition":
            return self.decide_phase_transition(
                current_phase=context.get("current_phase", 1),
                phase_completion=context.get("phase_completion", {}),
                overall_progress=context.get("overall_progress", 0.0),
            )
        else:
            return {"error": f"Unknown decision type: {decision_type}"}

    def execute_phase_0_plan(self, workspace: dict) -> dict:
        """
        Execute Phase 0: Delegate to Architect for requirements gathering.
        
        Supervisor delegates requirement gathering to @architect who asks the user.
        
        Args:
            workspace: Workspace configuration
            
        Returns:
            {"status": "success", "docs_generated": {...}}
        """
        self.report_status("running")
        self._log("Executing Phase 0: Delegating to @architect for requirements")
        
        docs_dir = Path(workspace.get("docs_dir", "docs"))
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        self.share_context("supervisor.phase0_plan", {
            "status": "delegating_to_architect",
            "phase": 0,
        })
        
        self.broadcast("phase0_started", {
            "strategy": "architect_delegation",
            "delegating_to": "architect",
        })
        
        # Supervisor tells user it's delegating to @architect
        self.info("Phase 0: Starting requirements gathering. @architect will ask you a few questions about your project vision.", file=None)
        
        from agents.architect.agent import ArchitectAgent
        architect = ArchitectAgent(
            model=self.model,
            workspace=self.workspace,
            rag_client=self._rag,
            llm_client=self._llm,
        )
        architect.log_callback = self.log_callback
        
        user_input = architect.gather_requirements(docs_dir)
        
        if not user_input:
            self._log("No user response received from architect")
            self.share_context("supervisor.phase0_plan", {
                "status": "failed",
                "reason": "no user response"
            })
            self.report_status("idle")
            return {"status": "failed", "reason": "no user response"}
        
        self._log(f"Architect gathered requirements: {user_input[:100]}...")
        
        from agents.docs_agent.agent import DocsAgent
        docs_agent = DocsAgent(
            model=self.model,
            workspace=self.workspace,
            rag_client=self._rag,
            llm_client=self._llm,
        )
        
        generated_docs = docs_agent.generate_phase0_docs(
            user_input=user_input,
            docs_dir=docs_dir,
        )
        
        self.share_context("supervisor.phase0_plan", {
            "status": "completed",
            "docs_generated": {k: str(v) for k, v in generated_docs.items()},
        })
        
        self.broadcast("phase0_completed", {
            "docs_generated": [str(v) for v in generated_docs.values()],
        })
        
        self.report_status("idle")
        return {
            "status": "success",
            "docs_generated": generated_docs,
            "user_input": user_input,
        }
