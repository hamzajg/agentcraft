"""
core/event_stream.py — Real-time event stream.

The orchestrator emits typed events here.
The comms server subscribes and forwards every event to WS clients.
A ring buffer (last 500) lets a refreshed browser catch up instantly.

Usage (orchestrator / agents):
    from core.event_stream import ES
    ES.emit("task_started", {"agent": "backend_dev", "file": "Foo.java"})

Usage (comms server, to subscribe):
    ES.subscribe(async_callback)   # async fn(event_type, payload) -> None

Event types emitted:
  build_started      phase, model, framework, iterations_total
  build_done         duration_s, iterations_total, approved
  phase_started      phase (1/2/3)
  phase_done         phase, duration_s
  iter_started       id, name, phase, task_count
  iter_done          id, approved, attempts, duration_s
  task_started       id, agent, file, description, iteration_id, attempt
  task_done          id, agent, file, verdict, attempts, duration_s
  aider_token        agent, text, file, call_id     ← streaming output
  aider_done         agent, file, success, call_id
  file_written       path, size_bytes, agent
  reviewer_verdict   agent, file, verdict, reason
  approval_gate      iteration_id, iteration_name, summary, files_written
  directive_injected text, task_id
  paused             reason (after_task | after_iter | user)
  resumed
  stopped
  error              agent, message, task_id
"""

import asyncio
import collections
import logging
import threading
import time
import uuid
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

RING_SIZE = 500


class _EventStream:
    """Singleton event stream. Access via ES module-level instance."""

    def __init__(self):
        self._mu          = threading.Lock()
        self._ring: collections.deque = collections.deque(maxlen=RING_SIZE)
        self._subscribers: list[Callable] = []   # async callbacks
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Emit ──────────────────────────────────────────────────────────────────

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        """Emit an event. Thread-safe. Called from orchestrator thread."""
        event = {
            "id":    str(uuid.uuid4())[:8],
            "ts":    time.time(),
            "type":  event_type,
            "data":  payload or {},
        }
        with self._mu:
            self._ring.append(event)
            subs = list(self._subscribers)

        logger.debug("[ES] %s %s", event_type, str(payload or {})[:80])

        # Push to async subscribers from the orchestrator thread
        if subs and self._loop and self._loop.is_running():
            for cb in subs:
                asyncio.run_coroutine_threadsafe(cb(event), self._loop)

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, callback: Callable[[dict], Coroutine]) -> None:
        """Register an async callback. Called from comms server on startup."""
        with self._mu:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        with self._mu:
            self._subscribers = [s for s in self._subscribers if s is not callback]

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Inject the running asyncio event loop (called from FastAPI startup)."""
        self._loop = loop

    # ── History ───────────────────────────────────────────────────────────────

    def recent(self, limit: int = 200) -> list[dict]:
        """Last N events from ring buffer — for browser catch-up on connect."""
        with self._mu:
            events = list(self._ring)
        return events[-limit:]

    def since(self, ts: float) -> list[dict]:
        """Events since a timestamp — for polling fallback."""
        with self._mu:
            return [e for e in self._ring if e["ts"] > ts]

    def clear(self) -> None:
        with self._mu:
            self._ring.clear()


# Module-level singleton
ES = _EventStream()
