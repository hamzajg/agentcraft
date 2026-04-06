"""
llm_suggest.py — local LLM reply suggestions for the comms UI.

When an agent sends a clarification, the comms server can optionally
generate suggested replies using the local Ollama model.
These appear as suggestion chips in the chat UI — the human clicks one
or types their own reply.

Fully local. No cloud. Gracefully disabled if Ollama is unreachable.
"""

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("COMMS_LLM_MODEL", "qwen2.5-coder:7b")
ENABLED      = os.getenv("COMMS_LLM_SUGGEST", "true").lower() == "true"

_llm = None


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    try:
        # Import from ai-team/llm/
        ai_team = os.path.join(os.path.dirname(__file__), "..", "ai-team")
        sys.path.insert(0, ai_team)
        from llm import OllamaClient
        client = OllamaClient(model=OLLAMA_MODEL, temperature=0.3, timeout=30)
        if client.is_available():
            _llm = client
            logger.info("[llm_suggest] local LLM ready: %s", OLLAMA_MODEL)
        else:
            logger.info("[llm_suggest] Ollama not available — suggestions disabled")
    except Exception as e:
        logger.debug("[llm_suggest] LLM init failed: %s", e)
    return _llm


async def generate_suggestions(
    agent_id: str,
    agent_label: str,
    question: str,
    file: Optional[str],
    partial_output: Optional[str],
    n: int = 3,
) -> list[str]:
    """
    Generate n suggested replies for a clarification message.
    Returns [] if LLM is unavailable or disabled.
    """
    if not ENABLED:
        return []

    llm = _get_llm()
    if llm is None:
        return []

    context = f"File: {file}\n" if file else ""
    partial = f"\nPartial output:\n{partial_output[:400]}\n" if partial_output else ""

    prompt = f"""An AI agent ({agent_label}) is asking a clarification question while building software.
{context}Question: {question}{partial}

Generate {n} short, concrete suggested answers a developer might give.
Each suggestion should be 1-2 sentences maximum and directly actionable.

Respond with ONLY a JSON array of strings, no explanation:
["suggestion 1", "suggestion 2", "suggestion 3"]"""

    try:
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm.extract_json(prompt)
        )
        if isinstance(result, list):
            suggestions = [str(s) for s in result[:n] if s]
            logger.debug("[llm_suggest] generated %d suggestions for %s",
                         len(suggestions), agent_id)
            return suggestions
    except Exception as e:
        logger.debug("[llm_suggest] suggestion generation failed: %s", e)

    return []
