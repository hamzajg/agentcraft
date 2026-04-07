"""
planner/agent.py — Planner agent.

Baby-step approach:
  One call per FILE in files_expected.
  Each call asks: "produce the task dict for this one file."
  Merges into tasks array. TDD pairs inserted automatically.
"""

import json
import logging
from pathlib import Path
from core.base import AiderAgent

logger = logging.getLogger(__name__)
SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


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
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills,
            framework_id=framework_id,
            max_retries=2,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def decompose(self, iteration: dict, docs_dir: Path,
                  prior_tasks_files: list[Path]) -> list[dict]:
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir(exist_ok=True)
        tasks_file = ai_dir / f"tasks_iter_{iteration['id']}.json"

        files_expected = iteration.get("files_expected", [])
        if not files_expected:
            logger.warning("[planner] iter %d has no files_expected", iteration["id"])
            return []

        base_ctx = list(docs_dir.glob("*.md")) + prior_tasks_files
        spec_file = ai_dir / "spec.md"
        if spec_file.exists():
            base_ctx.append(spec_file)

        all_tasks: list[dict] = []
        task_counter = 1

        for file_path in files_expected:
            is_test  = "Test" in Path(file_path).stem or "/test/" in file_path
            is_java  = file_path.endswith(".java") and not is_test
            is_yaml  = file_path.endswith((".yaml", ".yml", ".json", ".properties"))
            is_md    = file_path.endswith(".md")

            if is_java:
                # TDD pair: test first, then impl
                test_path = _test_path_for(file_path)

                t_id = f"iter{iteration['id']}_task{task_counter}"
                task_counter += 1

                logger.info("[planner] planning test for %s", Path(file_path).name)
                test_task = self._plan_one_file(
                    iteration=iteration,
                    task_id=t_id,
                    file_path=test_path,
                    agent="test_dev",
                    context_files=[],
                    base_ctx=base_ctx,
                )
                if test_task:
                    all_tasks.append(test_task)

                # impl task
                i_id = f"iter{iteration['id']}_task{task_counter}"
                task_counter += 1

                logger.info("[planner] planning impl for %s", Path(file_path).name)
                impl_task = self._plan_one_file(
                    iteration=iteration,
                    task_id=i_id,
                    file_path=file_path,
                    agent="backend_dev",
                    context_files=[test_path],
                    base_ctx=base_ctx,
                )
                if impl_task:
                    all_tasks.append(impl_task)

            elif is_test:
                t_id = f"iter{iteration['id']}_task{task_counter}"
                task_counter += 1
                task = self._plan_one_file(
                    iteration=iteration, task_id=t_id,
                    file_path=file_path, agent="test_dev",
                    context_files=[], base_ctx=base_ctx,
                )
                if task:
                    all_tasks.append(task)

            elif is_yaml:
                t_id = f"iter{iteration['id']}_task{task_counter}"
                task_counter += 1
                task = self._plan_one_file(
                    iteration=iteration, task_id=t_id,
                    file_path=file_path, agent="config_agent",
                    context_files=[], base_ctx=base_ctx,
                )
                if task:
                    all_tasks.append(task)

            elif is_md:
                t_id = f"iter{iteration['id']}_task{task_counter}"
                task_counter += 1
                task = self._plan_one_file(
                    iteration=iteration, task_id=t_id,
                    file_path=file_path, agent="docs_agent",
                    context_files=[], base_ctx=base_ctx,
                )
                if task:
                    all_tasks.append(task)

        tasks_file.write_text(json.dumps(all_tasks, indent=2))
        logger.info("[planner] iter %d → %d tasks", iteration["id"], len(all_tasks))
        self.complete(f"Decomposed iteration {iteration['id']} into {len(all_tasks)} tasks", file=str(tasks_file))
        return all_tasks

    def _plan_one_file(
        self,
        iteration: dict,
        task_id:   str,
        file_path: str,
        agent:     str,
        context_files: list[str],
        base_ctx:  list[Path],
    ) -> dict | None:
        """Ask the model to describe exactly one task for one file."""
        out_file = self.workspace / ".ai" / f"task_{task_id}.json"
        fname    = Path(file_path).name

        msg = (
            f"Write the task description for ONE file: {file_path}\n\n"
            f"Iteration goal: {iteration.get('goal', '')}\n"
            f"Assigned agent: {agent}\n\n"
            "Output ONLY a single valid JSON object:\n"
            "{\n"
            f'  "id": "{task_id}",\n'
            f'  "iteration_id": {iteration["id"]},\n'
            f'  "agent": "{agent}",\n'
            f'  "file": "{file_path}",\n'
            '  "description": "precise description of what to implement",\n'
            f'  "context_files": {json.dumps(context_files)},\n'
            '  "acceptance_criteria": ["compiles", "implements X"]\n'
            "}"
        )

        result = self.run(
            message=msg,
            read_files=base_ctx,
            edit_files=[out_file],
            timeout=90,
            log_callback=self.log_callback,
        )

        if out_file.exists():
            result_data = self.read_json(out_file)
            if result_data is not None:
                return result_data

        # Fallback: minimal task dict
        logger.warning("[planner] could not parse task JSON for %s — using fallback", fname)
        return {
            "id":           task_id,
            "iteration_id": iteration["id"],
            "agent":        agent,
            "file":         file_path,
            "description":  f"Implement {fname} as described in the iteration goal: {iteration.get('goal', '')}",
            "context_files": context_files,
            "acceptance_criteria": ["compiles", "no TODOs"],
        }


def _test_path_for(impl_path: str) -> str:
    """Derive test file path from implementation path."""
    p = Path(impl_path)
    # src/main/java/.../Foo.java → src/test/java/.../FooTest.java
    parts = list(p.parts)
    try:
        idx = parts.index("main")
        parts[idx] = "test"
    except ValueError:
        pass
    stem = p.stem + "Test"
    return str(Path(*parts).parent / (stem + p.suffix))
