"""
Tests for the shared failure taxonomy (core/failure.py).

These pin the contract every agent now inherits: what counts as a
hallucination, how a failed step is classified, and what the escalation
question looks like. The agents' own tests can't cover this — they need a
live LLM — so the taxonomy is tested here, once, for all of them.
"""
from pathlib import Path

import pytest

from core.failure import StepFailureMixin, looks_like_hallucination


REAL_CODE = """
import os

def compute_total(items):
    return sum(item.price * item.quantity for item in items)

class Invoice:
    def __init__(self, number, items):
        self.number = number
        self.items = items

    def total(self):
        return compute_total(self.items)
""" * 3  # comfortably over the 100-char floor

PLACEHOLDER_HEAVY = "\n".join(
    ["# TODO: implement this", "# placeholder — fill in later"] * 10
)


class TestLooksLikeHallucination:
    def test_empty_and_short_content_is_suspicious(self):
        assert looks_like_hallucination("")
        assert looks_like_hallucination("   ")
        assert looks_like_hallucination("ok")

    def test_placeholder_dense_content_is_suspicious(self):
        assert looks_like_hallucination(PLACEHOLDER_HEAVY)

    def test_comment_only_content_is_suspicious(self):
        comments = "\n".join(["# a note", "# another note", "// and one more"] * 5)
        assert looks_like_hallucination(comments)

    def test_real_code_passes(self):
        assert not looks_like_hallucination(REAL_CODE)


class _DummyAgent(StepFailureMixin):
    """Minimal host: only `ask` is required by the mixin."""

    def __init__(self, reply="retry"):
        self._reply = reply
        self.last_question = None

    def ask(self, question, suggestions=None, timeout=None):
        self.last_question = question
        return self._reply


class TestClassifyFailure:
    def _result(self, **kw):
        base = {"exit_code": 0, "stderr": "", "output": "done"}
        base.update(kw)
        return base

    def test_timeout_is_transient_and_auto_retries(self, tmp_path: Path):
        agent = _DummyAgent()
        out = tmp_path / "out.py"
        out.write_text(REAL_CODE)
        c = agent._classify_failure(self._result(exit_code=-1, stderr="timed out"), out, "step")
        assert c["severity"] == "transient"
        assert c["auto_retry"] is True
        assert c["needs_user_input"] is False

    def test_empty_output_on_success_is_a_refusal(self, tmp_path: Path):
        agent = _DummyAgent()
        out = tmp_path / "out.py"
        out.touch()  # exists but empty
        c = agent._classify_failure(self._result(exit_code=0), out, "step")
        assert c["severity"] == "refusal"
        assert c["auto_retry"] is True

    def test_hallucinated_content_needs_a_human(self, tmp_path: Path):
        agent = _DummyAgent()
        out = tmp_path / "out.py"
        out.write_text(PLACEHOLDER_HEAVY)
        c = agent._classify_failure(self._result(exit_code=0), out, "step")
        assert c["severity"] == "hallucination"
        assert c["auto_retry"] is False
        assert c["needs_user_input"] is True

    def test_unclassified_failure_is_critical(self, tmp_path: Path):
        agent = _DummyAgent()
        out = tmp_path / "out.py"
        out.write_text(REAL_CODE)
        c = agent._classify_failure(self._result(exit_code=1, stderr="boom"), out, "step")
        assert c["severity"] == "critical"
        assert c["needs_user_input"] is True


class TestAskUserRetry:
    def test_returns_lowercased_reply(self):
        agent = _DummyAgent(reply="  SKIP This Step ")
        assert agent._ask_user_retry("write file", "details", "critical") == "skip this step"

    def test_question_carries_label_and_severity(self):
        agent = _DummyAgent()
        agent._ask_user_retry("write file", "boom", "hallucination")
        assert "write file" in agent.last_question
        assert "HALLUCINATION" in agent.last_question

    def test_none_reply_becomes_empty_string(self):
        agent = _DummyAgent(reply=None)
        assert agent._ask_user_retry("x", "y", "critical") == ""
