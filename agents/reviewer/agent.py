"""
reviewer.py — reads completed task output and decides APPROVED or REWORK.

The reviewer is the loop termination authority.
It reads the written file + task spec and emits a structured verdict.
"""

import logging
import re
from pathlib import Path
from dataclasses import dataclass

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the Reviewer Agent. Review code and provide approval or rework feedback."""


@dataclass
class ReviewVerdict:
    approved: bool
    reason: str
    suggestions: list[str]

    @property
    def label(self) -> str:
        return "APPROVED" if self.approved else "REWORK"


class ReviewerAgent(AiderAgent):
    _role = "reviewer"

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
            role="reviewer",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills,
            framework_id=framework_id,
            max_retries=1,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def handle_query(self, question: str, context: dict) -> str:
        """
        Handle queries from other agents.
        Any agent can ask the reviewer a quick opinion via:
            answer = self.ask_agent("reviewer", "Is this approach correct?", context)
        Uses local LLM with reviewer persona for fast answers.
        """
        code    = context.get("code", context.get("code_snippet", ""))
        file    = context.get("file", "")
        if self._llm:
            prompt = (
                "You are an expert code reviewer.\n"
                + (f"File: {file}\n" if file else "")
                + (f"Code:\n{code[:1000]}\n\n" if code else "")
                + f"Question from another agent:\n{question}\n\n"
                + "Give a concise technical answer. If something is wrong, "
                + "explain what and suggest the fix."
            )
            return self._llm.chat(prompt) or "No opinion available."
        return "Reviewer LLM not available."


    def review(self, task: dict, docs_dir: Path) -> ReviewVerdict:
        """
        Review a completed task's output file against its spec.

        The reviewer must output one of:
          APPROVED
          REWORK: <one-line reason>
          REWORK: <one-line reason>
          - suggestion 1
          - suggestion 2
        """
        target_file = self.workspace / task["file"]
        if not target_file.exists():
            logger.warning("[reviewer] file not found: %s", target_file)
            return ReviewVerdict(
                approved=False,
                reason=f"File was not created: {task['file']}",
                suggestions=["Agent must create the file before review"]
            )

        read_files = [target_file] + list(docs_dir.glob("*.md"))

        message = f"""
Review the file that was just written against its task specification.

Task specification:
{_task_summary(task)}

Read the file {task['file']} and check:
1. Does it fully implement the task description?
2. Does it meet every acceptance criterion?
3. Is the code/config/docs correct and consistent with the project architecture?
4. Are there any missing imports, broken references, or wrong field names?

Respond with EXACTLY one of these formats — no preamble:

APPROVED

or:

REWORK: <one-line reason>
- <specific fix needed>
- <specific fix needed>
"""
        output = self.run_readonly(
            message=message,
            read_files=read_files,
            timeout=90,
        )

        return self._parse_verdict(output, task["file"])

    def review_iteration(self, iteration: dict, tasks: list[dict], docs_dir: Path) -> ReviewVerdict:
        """
        Review the entire iteration output holistically.
        Called after all tasks in an iteration pass individual review.
        """
        written_files = [
            self.workspace / t["file"]
            for t in tasks
            if (self.workspace / t["file"]).exists()
        ]
        read_files = written_files + list(docs_dir.glob("*.md"))

        message = f"""
Review the entire iteration output for cohesion and completeness.

Iteration: {iteration['name']}
Goal: {iteration['goal']}

Check:
1. Do all files work together consistently (imports, interfaces, field names)?
2. Is the iteration goal fully achieved?
3. Are there missing files that were expected?

Expected files:
{chr(10).join('- ' + f for f in iteration.get('files_expected', []))}

Respond EXACTLY:
APPROVED
or:
REWORK: <reason>
- <fix>
"""
        output = self.run_readonly(
            message=message,
            read_files=read_files,
            timeout=90,
        )
        return self._parse_verdict(output, f"iteration {iteration['id']}")

    @staticmethod
    def _parse_verdict(text: str, context: str) -> ReviewVerdict:
        text = text.strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Find APPROVED or REWORK line
        for i, line in enumerate(lines):
            upper = line.upper()
            if upper.startswith("APPROVED"):
                return ReviewVerdict(approved=True, reason="", suggestions=[])
            if upper.startswith("REWORK"):
                reason = re.sub(r"(?i)^rework\s*:?\s*", "", line).strip()
                suggestions = [
                    l.lstrip("- ").strip()
                    for l in lines[i+1:]
                    if l.startswith("-")
                ]
                logger.info("[reviewer] REWORK %s: %s (%d suggestions)", context, reason, len(suggestions))
                return ReviewVerdict(approved=False, reason=reason, suggestions=suggestions)

        # No clear verdict — treat as rework
        logger.warning("[reviewer] no clear verdict for %s — defaulting to REWORK", context)
        return ReviewVerdict(
            approved=False,
            reason="Reviewer did not return a clear verdict",
            suggestions=[text[:300]]
        )


def _task_summary(task: dict) -> str:
    return (
        f"File: {task['file']}\n"
        f"Description: {task['description']}\n"
        f"Acceptance criteria:\n" +
        "\n".join(f"  - {c}" for c in task.get("acceptance_criteria", []))
    )
