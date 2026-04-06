"""
pending.py — agent suspension and resumption via asyncio Futures.

When an agent POSTs /clarify:
  1. A Future is created and stored keyed by message_id
  2. The agent's thread blocks on Future.result(timeout=3600)
  3. When the human replies (POST /reply):
     - Future is resolved with the reply text
     - Agent unblocks and injects the reply into its prompt

Thread safety: agents call from sync threads (Aider subprocess threads).
The Future is created in the async event loop and resolved via
loop.call_soon_threadsafe() to cross the thread boundary safely.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# message_id → asyncio.Future[str]
_pending: dict[str, asyncio.Future] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None


def set_loop(loop: asyncio.AbstractEventLoop):
    """Called once on startup to register the event loop."""
    global _loop
    _loop = loop


def create_future(message_id: str) -> asyncio.Future:
    """Create a Future for a pending clarification. Called from async context."""
    assert _loop is not None, "Event loop not registered"
    fut = _loop.create_future()
    _pending[message_id] = fut
    logger.debug("[pending] created future for %s", message_id)
    return fut


def resolve(message_id: str, reply: str) -> bool:
    """
    Resolve a pending Future with the human's reply.
    Called from async context (HTTP handler).
    Returns True if a pending Future was found and resolved.
    """
    fut = _pending.pop(message_id, None)
    if fut is None:
        logger.warning("[pending] no pending future for %s", message_id)
        return False
    if not fut.done():
        fut.set_result(reply)
        logger.info("[pending] resolved future for %s", message_id)
        return True
    return False


def resolve_threadsafe(message_id: str, reply: str) -> bool:
    """
    Resolve from a non-async thread.
    Used when the reply comes in while agent thread is blocking.
    """
    assert _loop is not None
    fut = _pending.get(message_id)
    if fut is None:
        return False

    def _set():
        if not fut.done():
            fut.set_result(reply)
            _pending.pop(message_id, None)

    _loop.call_soon_threadsafe(_set)
    logger.info("[pending] resolved (threadsafe) future for %s", message_id)
    return True


def expire(message_id: str, fallback: str = "") -> bool:
    """Mark a pending future as expired (timeout). Agent uses fallback."""
    fut = _pending.pop(message_id, None)
    if fut and not fut.done():
        fut.set_result(fallback)
        logger.warning("[pending] expired future for %s — using fallback", message_id)
        return True
    return False


def pending_count() -> int:
    return len(_pending)


def list_pending_ids() -> list[str]:
    return list(_pending.keys())
