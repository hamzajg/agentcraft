"""
Shared failure taxonomy for agent steps.

Ten agents each carried their own copy of "did this step fail, how badly,
and what do we do about it" — the same classify → maybe-auto-retry →
maybe-ask-the-human pipeline, copy-pasted with the role name changed. That
is where hallucination handling rots: fix the placeholder detector in one
agent and the other nine keep flagging (or missing) the same output.

`StepFailureMixin` is the single implementation. Agents inherit it and keep
only what is genuinely theirs — their `_run_step` (readonly vs. edit-files
vs. output-path semantics really do differ per role) and, where a role needs
a stricter detector, an override of `_looks_like_hallucination`.

The detector itself is deliberately conservative in the *safe* direction:
short outputs, comment-only files, and placeholder-dense text all count as
hallucination candidates, because the cost of a false positive is one
retry while the cost of a false negative is shipping a stub.
"""
import logging
import re
from pathlib import Path

from core.files import file_has_content

logger = logging.getLogger(__name__)

#: Patterns that mark generated text as a placeholder rather than content.
#: Matched case-insensitively, per line; a file where >40% of lines hit one
#: of these is treated as hallucinated.
PLACEHOLDER_PATTERNS = [
    r"TODO", r"placeholder", r"stub", r"fill.*in", r"coming soon",
    r"auto-generat", r"skipped\b", r"incomplete\b",
    r"not (yet|currently) (implemented|available|generated)",
]


def looks_like_hallucination(content: str) -> bool:
    """The standard detector: empty/short, placeholder-dense, or
    comment-only output is treated as a hallucination candidate."""
    if not content or len(content.strip()) < 20:
        return True
    lines = content.splitlines()
    placeholder_lines = sum(
        1 for line in lines for p in PLACEHOLDER_PATTERNS
        if re.search(p, line, re.IGNORECASE)
    )
    if len(lines) > 3 and placeholder_lines / len(lines) > 0.4:
        return True
    if len(content.strip()) < 100:
        return True
    if all(
        line.lstrip().startswith(("#", "//", "/*", "*", "*/")) or line.strip() == ""
        for line in lines if line.strip()
    ):
        return True
    return False


class StepFailureMixin:
    """
    Failure classification + retry escalation shared by all agents.

    Expects the host class to provide `ask(...)` (from `AiderAgent`) and to
    keep `_looks_like_hallucination` overridable per role.
    """

    def _looks_like_hallucination(self, content: str) -> bool:
        return looks_like_hallucination(content)

    def _classify_failure(self, result: dict, output_path: Path, label: str) -> dict:
        exit_code = result.get("exit_code", -1)
        stderr = result.get("stderr", "")
        # Skip reading if path is a directory or doesn't exist
        content = ""
        if output_path.exists() and output_path.is_file():
            content = output_path.read_text()
        if exit_code != 0 and (exit_code == -1 or "timeout" in stderr.lower() or exit_code >= 128):
            return {"severity": "transient", "auto_retry": True, "needs_user_input": False, "escalated_message": ""}
        if file_has_content(output_path) and self._looks_like_hallucination(content):
            return {"severity": "hallucination", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}
        if exit_code == 0 and not file_has_content(output_path):
            return {"severity": "refusal", "auto_retry": True, "needs_user_input": False,
                    "escalated_message": "CRITICAL: You MUST write the complete file content. No placeholders or stubs."}
        return {"severity": "critical", "auto_retry": False, "needs_user_input": True, "escalated_message": ""}

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
