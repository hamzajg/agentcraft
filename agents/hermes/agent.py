import logging
import time
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else "# Hermes Agent"

class HermesAgent(AiderAgent):
    _role = "hermes"

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
            role="hermes",
            model=model,
            workspace=workspace,
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or [],
            framework_id=framework_id,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
            **kwargs,
        )

    def handle_query(self, question: str, context: dict = None) -> str:
        """Route questions to the right specialist agent."""
        prompt = f"""
        You are Hermes. You need to classify the following user request and delegate it to the best specialist agent.
        User request: "{question}"
        
        Available agents:
        - spec: product requirements, user stories, feature lists
        - architect: file structure, architecture specs, libraries to use
        - planner: list of tasks, build phases, acceptance criteria
        - backend_dev: implement APIs, server logic, database scripts, main code
        - test_dev: writing unit tests, test scripts
        - config_agent: environment files, dependencies (e.g. package.json, requirements.txt)
        - docs_agent: writing readme, markdown documents
        - reviewer: review codes/PRs
        - integration_test: run integrations tests, end to end suites
        - cicd: Dockerfiles, github actions, deployment scripts
        
        Respond with ONLY a JSON block like:
        {{
          "delegate": "agent_name",
          "reason": "why this agent is chosen",
          "action_message": "message to send to that agent"
        }}
        """
        try:
            res = self.ask_local(prompt)
            import json, re
            json_match = re.search(r'\{[\s\S]*\}', res)
            if json_match:
                data = json.loads(json_match.group(0))
                delegate = data.get("delegate")
                reason = data.get("reason", "")
                self.announce(f"Routing task to @{delegate}: {reason}")
                return f"Delegated to @{delegate}. Reason: {reason}"
        except Exception as e:
            logger.warning("[hermes] ask_local failed: %s", e)
            
        # Fallback rule-based
        q_lower = question.lower()
        if "spec" in q_lower or "requirement" in q_lower:
            delegate = "spec"
        elif "architect" in q_lower or "structure" in q_lower or "boundary" in q_lower:
            delegate = "architect"
        elif "test" in q_lower:
            delegate = "test_dev"
        elif "docker" in q_lower or "ci" in q_lower or "pipeline" in q_lower:
            delegate = "cicd"
        elif "docs" in q_lower or "readme" in q_lower or "markdown" in q_lower:
            delegate = "docs_agent"
        else:
            delegate = "backend_dev"
            
        self.announce(f"Routing task to @{delegate} (Rule fallback)")
        return f"Delegated to @{delegate}."

    def announce(self, message: str):
        """Broadcast a status announcement to the UI."""
        self.info(message)
        try:
            from core.event_stream import ES
            ES.emit("hermes_announcement", {"message": message, "ts": time.time()})
        except Exception as e:
            logger.warning("[hermes] Failed to announce event: %s", e)
