"""
planner/agent.py — Planner agent.

ROLE: Task decomposition and planning.

This agent:
- Decomposes iterations into concrete tasks
- Determines which agent should handle each task
- Creates task specifications with acceptance criteria
- Plans test-implementation pairs

ALL TASK ASSIGNMENT DECISIONS ARE MADE BY LLM.
No hardcoded file-type-to-agent mapping.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Planner Agent.

Your role is to decompose iterations into concrete tasks and assign them to appropriate agents.
"""


class PlannerAgent(AiderAgent):
    _role = "planner"

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
            role="planner",
            model=model,
            workspace=workspace,
            system_prompt=system_prompt or SYSTEM_PROMPT,
            skills=skills or [],
            framework_id=framework_id,
            max_retries=2,
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
        logger.info("[planner] %s", message)

    def gather_context(self) -> dict:
        """Gather context for task planning."""
        docs_dir = self.workspace / "docs"
        ai_dir = self.workspace / ".ai"
        
        context = {
            "iteration_goal": "",
            "architecture": {},
            "available_agents": self._get_available_agents(),
        }
        
        if (ai_dir / "spec.md").exists():
            context["spec"] = (ai_dir / "spec.md").read_text()[:1500]
        
        for md_file in docs_dir.glob("*.md"):
            context[f"doc_{md_file.stem}"] = md_file.read_text()[:1000]
        
        return context

    def _get_available_agents(self) -> list[dict]:
        """Get list of available agents with their capabilities."""
        return [
            {"role": "backend_dev", "capabilities": ["implement", "backend", "api", "service"]},
            {"role": "test_dev", "capabilities": ["test", "testing", "tdd", "unit", "integration"]},
            {"role": "docs_agent", "capabilities": ["docs", "documentation", "readme"]},
            {"role": "config_agent", "capabilities": ["config", "yaml", "json", "properties", "settings"]},
            {"role": "reviewer", "capabilities": ["review", "quality", "security"]},
            {"role": "cicd", "capabilities": ["ci", "cd", "pipeline", "docker", "deployment"]},
        ]

    def decompose(
        self,
        iteration: dict,
        docs_dir: Path,
        prior_tasks_files: list[Path] = None,
    ) -> list[dict]:
        """
        Decompose an iteration into concrete tasks using LLM.
        
        Args:
            iteration: The iteration to decompose
            docs_dir: Directory containing documentation
            prior_tasks_files: Previously created task files
            
        Returns:
            List of task dictionaries
        """
        self.report_status("running")
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir(parents=True, exist_ok=True)
        
        files_expected = iteration.get("files_expected", [])
        if not files_expected:
            logger.warning("[planner] iteration %d has no files_expected", iteration.get("id"))
            return []
        
        self._log(f"Decomposing iteration {iteration.get('id')} into tasks")
        
        context_files = list(docs_dir.glob("*.md"))
        if prior_tasks_files:
            context_files.extend(prior_tasks_files)
        
        spec_file = ai_dir / "spec.md"
        if spec_file.exists():
            context_files.append(spec_file)
        
        prompt = f"""Decompose this iteration into concrete tasks.

## Iteration
- ID: {iteration.get('id')}
- Phase: {iteration.get('phase')}
- Goal: {iteration.get('goal', 'No goal specified')}
- Files Expected: {json.dumps(files_expected)}

## Available Agents
{json.dumps(self._get_available_agents(), indent=2)}

## Context Files
{json.dumps([str(f) for f in context_files])}

## Task
For each file in files_expected:
1. Determine which agent should implement it
2. Decide if it needs a paired test
3. Create clear acceptance criteria

Decisions should be based on:
- File purpose and content type
- Dependencies between files
- Test coverage needs
- Agent capabilities

Output ONLY a valid JSON array of tasks:
```json
[
  {{
    "id": "iter1_task1",
    "iteration_id": {iteration.get('id')},
    "agent": "backend_dev|test_dev|docs_agent|...",
    "file": "path/to/file",
    "description": "What to implement",
    "context_files": ["related_file1", "related_file2"],
    "needs_test": true|false,
    "test_file": "path/to/test" (only if needs_test is true),
    "acceptance_criteria": ["criteria1", "criteria2"]
  }}
]
```

Consider TDD: if a file needs testing, include a paired test task before it.
"""

        result = self.run(
            message=prompt,
            read_files=context_files,
            timeout=180,
            log_callback=self.log_callback,
        )
        
        tasks = self._parse_tasks(result.get("output", "[]"))
        
        tasks_file = ai_dir / f"tasks_iter_{iteration['id']}.json"
        tasks_file.write_text(json.dumps(tasks, indent=2))
        self.emit_file_written(tasks_file)
        
        self._log(f"Decomposed iteration {iteration.get('id')} into {len(tasks)} tasks")
        self.complete(f"Decomposed iteration {iteration['id']} into {len(tasks)} tasks")
        self.report_status("idle")
        
        return tasks

    def _parse_tasks(self, output: str) -> list[dict]:
        """Parse tasks from LLM output."""
        import re
        json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []

    def plan_single_file(
        self,
        iteration: dict,
        file_path: str,
        context_files: list[Path],
    ) -> dict:
        """
        Plan task for a single file using LLM.
        
        Args:
            iteration: Parent iteration
            file_path: Path to the file to plan
            context_files: Files to read for context
            
        Returns:
            Task dictionary
        """
        prompt = f"""Plan the implementation task for this file.

## File
{file_path}

## Iteration Goal
{iteration.get('goal', 'No goal specified')}

## Iteration ID
{iteration.get('id')}

## Available Agents
{json.dumps(self._get_available_agents(), indent=2)}

## Task
Determine:
1. Which agent should implement this file
2. What dependencies it has
3. Clear acceptance criteria

Output ONLY a valid JSON object:
```json
{{
  "id": "unique_task_id",
  "iteration_id": {iteration.get('id')},
  "agent": "backend_dev|test_dev|docs_agent|...",
  "file": "{file_path}",
  "description": "precise description of what to implement",
  "context_files": ["file1", "file2"],
  "acceptance_criteria": ["criteria1", "criteria2"]
}}
```"""

        result = self.run(
            message=prompt,
            read_files=context_files,
            timeout=120,
        )
        
        return self._parse_single_task(result.get("output", "{}"))

    def _parse_single_task(self, output: str) -> dict:
        """Parse single task from LLM output."""
        import re
        json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {
                "id": "unknown",
                "iteration_id": 0,
                "agent": "backend_dev",
                "file": "unknown",
                "description": "Task parsing failed",
                "acceptance_criteria": ["compiles"],
            }
