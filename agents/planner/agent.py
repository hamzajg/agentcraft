"""
planner/agent.py — Planner agent.

ROLE: Task decomposition and planning.
Follows the same incremental step + user-controlled retry pattern as all agents.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Planner Agent.

Your role is to decompose iterations into concrete tasks and assign them to appropriate agents.
"""


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


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
        **kwargs,
    ):
        super().__init__(
            role="planner",
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
        self._step_results = []

    def get_step_results(self) -> list[dict]:
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path] = None,
                  output_path: Path = None, label: str = None, timeout: int = 180) -> dict:
        kwargs = {"message": message, "timeout": timeout, "log_callback": self.log_callback}
        if read_files:
            kwargs["read_files"] = read_files
        if output_path:
            kwargs["edit_files"] = [output_path]
        result = self.run(**kwargs)
        if label:
            success = result.get("success", False)
            if output_path:
                success = success and _file_has_content(output_path)
            self._step_results.append({"label": label, "success": success, "file": str(output_path) if output_path else ""})
            if not success:
                logger.warning("[planner] step FAILED: %s", label)
        return result

    def _ask_user_retry(self, step_label: str, error_detail: str) -> str:
        reply = self.ask(
            question=f"Step '{step_label}' failed: {error_detail}. What should I do?",
            suggestions=["Retry this step", "Skip this step", "Abort"],
            timeout=300,
        )
        return (reply or "").lower().strip()

    def _log(self, message: str):
        if self.log_callback:
            try:
                self.log_callback(self.role, message)
            except Exception:
                pass
        logger.info("[planner] %s", message)

    def gather_context(self) -> dict:
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
        return [
            {"role": "backend_dev", "capabilities": ["implement code", "create files", "write logic"]},
            {"role": "test_dev", "capabilities": ["write tests", "testing", "test-driven development"]},
            {"role": "docs_agent", "capabilities": ["write documentation", "documentation", "readme"]},
            {"role": "config_agent", "capabilities": ["create configuration", "settings", "config files"]},
            {"role": "reviewer", "capabilities": ["review code", "quality check", "verify correctness"]},
            {"role": "cicd", "capabilities": ["create infrastructure", "CI/CD", "deployment config"]},
        ]

    def decompose(
        self,
        iteration: dict,
        docs_dir: Path,
        prior_tasks_files: list[Path] = None,
    ) -> list[dict]:
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

        result = self._run_step(prompt, context_files, label="decompose iteration", timeout=180)
        tasks = self._parse_tasks(result.get("output", "[]"))

        tasks_file = ai_dir / f"tasks_iter_{iteration['id']}.json"
        tasks_file.write_text(json.dumps(tasks, indent=2))
        self.emit_file_written(tasks_file)

        self._log(f"Decomposed iteration {iteration.get('id')} into {len(tasks)} tasks")
        self.report_status("idle")
        return tasks

    def _parse_tasks(self, output: str) -> list[dict]:
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

        result = self._run_step(prompt, context_files, label="plan single file", timeout=120)
        if not result.get("success"):
            decision = self._ask_user_retry("plan single file", "aider could not plan task")
            if "abort" in decision:
                return {"id": "unknown", "iteration_id": 0, "agent": "backend_dev", "file": file_path, "description": "Planning aborted", "acceptance_criteria": []}
            if "skip" in decision:
                return {"id": "unknown", "iteration_id": iteration.get("id", 0), "agent": "backend_dev", "file": file_path, "description": "Auto-planned", "acceptance_criteria": []}
            result = self._run_step(
                f"CRITICAL: Plan the implementation task for {file_path}. Output valid JSON.",
                context_files, label="plan single file (retry)", timeout=120,
            )
        return self._parse_single_task(result.get("output", "{}"))

    def _parse_single_task(self, output: str) -> dict:
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
