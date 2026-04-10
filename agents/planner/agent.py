"""
planner/agent.py — Planner agent.

ROLE: Task decomposition and planning.
Uses chunked approach: one LLM call per task for reliability.
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
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def _file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
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
        self._retry_count = {}

    def get_step_results(self) -> list[dict]:
        """Return per-step results for reporting to orchestrator."""
        return list(self._step_results)

    def _run_step(self, message: str, read_files: list[Path] = None,
                  output_path: Path = None, label: str = None, timeout: int = 180) -> dict:
        """
        Run a single aider step with auto-retry for non-critical failures.
        """
        MAX_AUTO_RETRIES = 2

        attempt = self._retry_count.get(label, 0) + 1 if label else 1
        if label:
            self._retry_count[label] = attempt

        logger.info("[planner] step %d: %s", attempt, label or "unknown")

        kwargs = {"message": message, "timeout": timeout, "log_callback": self.log_callback}
        if read_files:
            kwargs["read_files"] = read_files
        if output_path:
            kwargs["edit_files"] = [output_path]
        result = self.run(**kwargs)

        success = result.get("success", False)
        if output_path:
            success = success and _file_has_content(output_path)

        if not success and label:
            classification = self._classify_failure(result, output_path or Path(""), label)
            result["severity"] = classification["severity"]
            result["auto_retry"] = classification["auto_retry"]
            result["needs_user_input"] = classification["needs_user_input"]
            result["retry_count"] = attempt
            result["escalated_message"] = classification.get("escalated_message", "")
            result["read_files"] = read_files
            result["timeout"] = timeout

            if classification["auto_retry"] and attempt <= MAX_AUTO_RETRIES:
                logger.info("[planner] auto-retrying '%s' (attempt %d/%d, severity=%s)",
                            label, attempt + 1, MAX_AUTO_RETRIES + 1, classification["severity"])
                retry_msg = classification.get("escalated_message") or message
                return self._run_step(retry_msg, read_files, output_path, label, timeout)

            if classification["needs_user_input"]:
                result["needs_user_input"] = True
        elif label:
            result["severity"] = "success"
            result["auto_retry"] = False
            result["needs_user_input"] = False
            result["retry_count"] = attempt

        if label:
            self._step_results.append({
                "label": label, "success": success, "file": str(output_path) if output_path else "",
                "exit_code": result.get("exit_code", -1), "severity": result.get("severity", "?"),
                "attempt": attempt,
            })
            if success:
                logger.info("[planner] step OK: %s", label)
            else:
                logger.warning("[planner] step FAILED [%s]: %s (attempt %d)",
                               result.get("severity", "?"), label, attempt)
        return result

    def _classify_failure(self, result: dict, output_path: Path, label: str) -> dict:
        import re
        exit_code = result.get("exit_code", -1)
        stderr = result.get("stderr", "")
        content = output_path.read_text() if output_path.exists() else ""
        if exit_code != 0 and (exit_code == -1 or "timeout" in stderr.lower() or exit_code >= 128):
            return {"severity": "transient", "auto_retry": True, "needs_user_input": False, "escalated_message": ""}
        if _file_has_content(output_path) and self._looks_like_hallucination(content):
            return {"severity": "hallucination", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}
        if exit_code == 0 and not _file_has_content(output_path):
            return {"severity": "refusal", "auto_retry": True, "needs_user_input": False,
                    "escalated_message": "CRITICAL: You MUST write the complete file content. No placeholders or stubs."}
        return {"severity": "critical", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}

    def _looks_like_hallucination(self, content: str) -> bool:
        import re
        if not content or len(content.strip()) < 20:
            return True
        lines = content.splitlines()
        placeholder_patterns = [r"TODO", r"placeholder", r"stub", r"fill.*in", r"coming soon",
                                r"auto-generat", r"skipped", r"incomplete", r"not (yet|currently) (implemented|available|generated)", r"_.*_"]
        placeholder_lines = sum(1 for line in lines for p in placeholder_patterns if re.search(p, line, re.IGNORECASE))
        if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
            return True
        if len(content.strip()) < 100:
            return True
        if all(line.startswith("#") or line.startswith("//") or line.strip() == "" for line in lines):
            return True
        return False

    def _ask_user_retry(self, step_label: str, error_detail: str, severity: str) -> str:
        """Ask user what to do after a critical or hallucination failure."""
        severity_label = severity.upper()
        reply = self.ask(
            question=f"Step '{step_label}' failed [{severity_label}]: {error_detail}. What should I do?",
            suggestions=[
                "Retry with more explicit instructions",
                "Skip this step and continue",
                "Abort — I'll fix this manually",
            ],
            timeout=600,
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
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._decompose_impl(iteration, docs_dir, prior_tasks_files)
        except Exception:
            logger.exception("[planner] unhandled error in decompose")
            result = []
        self.report_status("idle")
        return result

    def _decompose_impl(self, iteration: dict, docs_dir: Path, prior_tasks_files: list[Path] = None) -> list[dict]:
        """Decompose iteration into tasks using chunked approach for reliability."""
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir(parents=True, exist_ok=True)

        files_expected = iteration.get("files_expected", [])
        if not files_expected:
            logger.warning("[planner] iteration %d has no files_expected — creating minimal task", iteration.get("id"))
            return [{
                "id": f"iter{iteration.get('id')}_task1",
                "iteration_id": iteration.get("id"),
                "agent": "backend_dev",
                "file": "main.py",
                "description": iteration.get("goal", "Implement iteration"),
                "context_files": [],
                "needs_test": False,
                "acceptance_criteria": iteration.get("acceptance_criteria", ["runs without errors"])
            }]

        self._log(f"Decomposing iteration {iteration.get('id')} into {len(files_expected)} tasks")

        # Build context files list
        context_files = list(docs_dir.glob("*.md"))
        if prior_tasks_files:
            context_files.extend(prior_tasks_files)
        spec_file = ai_dir / "spec.md"
        if spec_file.exists():
            context_files.append(spec_file)

        # Create one task per file (chunked - one LLM call per file)
        tasks = []
        for i, file_path in enumerate(files_expected, 1):
            task_prompt = f"""Create a task for this file.

## File: {file_path}
## Iteration {iteration.get('id')} (Phase {iteration.get('phase', 1)})
## Goal: {iteration.get('goal', 'No goal specified')}

## Available Agents
- backend_dev: implements application code
- test_dev: writes tests
- config_agent: creates config files
- docs_agent: writes documentation
- cicd: creates CI/CD files

Respond with ONLY this JSON:
{{
  "agent": "agent_name",
  "description": "what to implement",
  "needs_test": false,
  "acceptance_criteria": ["criterion 1", "criterion 2"]
}}"""

            task_result = self._run_step(task_prompt, context_files[:3], label=f"task {i} for {Path(file_path).name}", timeout=90)
            task_info = self._parse_task_info(task_result.get("output", "{}"))

            # Determine agent
            agent = task_info.get("agent", self._infer_agent_from_file(file_path))

            task = {
                "id": f"iter{iteration.get('id')}_task{i}",
                "iteration_id": iteration.get("id"),
                "agent": agent,
                "file": file_path,
                "description": task_info.get("description", f"Create {file_path}"),
                "context_files": [f.name for f in context_files[:3]],
                "needs_test": task_info.get("needs_test", False),
                "acceptance_criteria": task_info.get("acceptance_criteria", ["file created", "works correctly"])
            }
            tasks.append(task)
            self._log(f"  ✓ Task {i}: {agent} -> {file_path}")

        # Save tasks
        tasks_file = ai_dir / f"tasks_iter_{iteration['id']}.json"
        tasks_file.write_text(json.dumps(tasks, indent=2))
        self.emit_file_written(tasks_file)

        self._log(f"Decomposed iteration {iteration.get('id')} into {len(tasks)} tasks")
        return tasks

    def _parse_task_info(self, output: str) -> dict:
        """Parse task info JSON object."""
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        return {}

    def _infer_agent_from_file(self, file_path: str) -> str:
        """Infer which agent should handle a file based on extension."""
        if file_path.endswith(('.py', '.js', '.ts', '.java', '.go', '.rb', '.rs')):
            return "backend_dev"
        elif file_path.endswith(('.md', '.txt', '.rst')):
            return "docs_agent"
        elif file_path.endswith(('.yaml', '.yml', '.json', '.toml', '.cfg', '.ini', '.env')):
            return "config_agent"
        elif 'test' in file_path.lower() or 'spec' in file_path.lower():
            return "test_dev"
        else:
            return "backend_dev"

    def _parse_tasks(self, output: str) -> list[dict]:
        """Parse task JSON from LLM output with robust error handling."""
        if not output or not output.strip():
            logger.warning("[planner] _parse_tasks: empty output received")
            return []

        output_stripped = output.strip()
        logger.info("[planner] _parse_tasks: output length=%d, first 100 chars=%s",
                    len(output), output_stripped[:100])

        # Try to extract JSON from markdown code blocks first
        json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
        if json_match:
            try:
                tasks = json.loads(json_match.group(1))
                logger.info("[planner] _parse_tasks: successfully parsed from markdown code block, %d tasks", len(tasks))
                return tasks
            except json.JSONDecodeError as e:
                logger.warning("[planner] _parse_tasks: failed to parse markdown code block JSON: %s", e)

        # Try to find any JSON array in the output
        array_match = re.search(r'\[[\s\S]*\]', output_stripped)
        if array_match:
            try:
                tasks = json.loads(array_match.group(0))
                logger.info("[planner] _parse_tasks: successfully parsed JSON array, %d tasks", len(tasks))
                return tasks
            except json.JSONDecodeError as e:
                logger.warning("[planner] _parse_tasks: failed to parse JSON array: %s", e)

        # Try parsing the entire output as JSON
        try:
            tasks = json.loads(output_stripped)
            logger.info("[planner] _parse_tasks: successfully parsed entire output as JSON, %d tasks", len(tasks))
            return tasks
        except json.JSONDecodeError as e:
            logger.error("[planner] _parse_tasks: all parsing attempts failed. Error: %s. Output was: %s",
                        e, output_stripped[:500])
            return []

    def plan_single_file(
        self,
        iteration: dict,
        file_path: str,
        context_files: list[Path],
    ) -> dict:
        self.report_status("running")
        self._step_results = []
        self._retry_count = {}
        try:
            result = self._plan_single_file_impl(iteration, file_path, context_files)
        except Exception:
            logger.exception("[planner] unhandled error in plan_single_file")
            result = {"id": "unknown", "iteration_id": 0, "agent": "backend_dev", "file": file_path, "description": "Planning error", "acceptance_criteria": []}
        self.report_status("idle")
        return result

    def _plan_single_file_impl(self, iteration: dict, file_path: str, context_files: list[Path]) -> dict:
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
            if result.get("needs_user_input"):
                decision = self._ask_user_retry("plan single file",
                                                result.get("stderr", "no output"),
                                                result.get("severity", "critical"))
                if "abort" in decision:
                    return {"id": "unknown", "iteration_id": 0, "agent": "backend_dev", "file": file_path, "description": "Planning aborted", "acceptance_criteria": []}
                if "skip" in decision:
                    return {"id": "unknown", "iteration_id": iteration.get("id", 0), "agent": "backend_dev", "file": file_path, "description": "Auto-planned", "acceptance_criteria": []}
                escalated = result.get("escalated_message", "") or f"CRITICAL: Plan the implementation task for {file_path}. Output valid JSON."
                result = self._run_step(escalated, context_files, label="plan single file (user-retry)", timeout=120)
            elif result.get("auto_retry"):
                pass  # Already auto-retried

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
