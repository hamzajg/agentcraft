"""
core/event_stream.py — Persistent event stream with file-backed storage.

The orchestrator emits typed events here. Events are:
  1. Appended to a JSONL file (persistent across restarts)
  2. Buffered in a ring buffer (for in-memory subscribers)
  3. Forwarded to comms server via HTTP (for WS clients)

Resume is based on replaying the event log — no separate run_log needed.

Usage (orchestrator / agents):
    from core.event_stream import ES
    ES.emit("task_started", {"agent": "backend_dev", "file": "Foo.java"})

Usage (comms server, to subscribe):
    ES.subscribe(async_callback)   # async fn(event_type, payload) -> None
"""

import asyncio
import collections
import json
import logging
import os
import threading
import time
import uuid
import httpx
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

RING_SIZE = 500


class FileEventStore:
    """
    Append-only JSONL event store.

    Each line is a JSON object: one event per line.
    The file grows but is never rewritten — safe for concurrent append.

    Storage: .ai/events.jsonl (configurable)
    """

    def __init__(self, path: Path):
        self.path = path
        self._mu = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict) -> None:
        """Append one event to the JSONL file. Thread-safe."""
        with self._mu:
            with open(self.path, "a") as f:
                f.write(json.dumps(event, separators=(",", ":")) + "\n")
                f.flush()

    def read_all(self) -> list[dict]:
        """Read all events from the file."""
        if not self.path.exists():
            return []
        events = []
        try:
            with open(self.path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("[event_store] read error on %s: %s", self.path, e)
        return events

    def tail(self, n: int = 200) -> list[dict]:
        """Read the last N events efficiently."""
        if not self.path.exists():
            return []
        # For small files, just read all
        size = self.path.stat().st_size
        if size < 1024 * 1024:  # < 1MB
            all_events = self.read_all()
            return all_events[-n:]

        # For large files, read from end
        events = []
        with open(self.path, "r") as f:
            # Seek near end and work backwards
            lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
                if len(events) >= n:
                    break
        return list(reversed(events))

    def clear(self) -> None:
        """Clear the event store. File store is append-only, so nothing to clear here."""
        pass

    def reset_file(self) -> None:
        """Delete the file store — use for a completely fresh start."""
        if self.path.exists():
            self.path.unlink()

    # ── State Reconstruction ────────────────────────────────────────────

    def reconstruct_state(self) -> dict:
        """
        Replay all events to reconstruct the current build state.

        Returns a dict with:
          build_status:  "idle" | "running" | "paused" | "stopped" | "done" | "error"
          current_phase: int | None
          current_iter:  int | None
          completed_iterations: list[int]    # IDs of approved iterations
          phases_completed: list[int]
          delivered_files: list[str]
          approved_count: int
          rejected_count: int
          last_event_ts: float
          resume_from_iteration: int   # next iteration to start from
        """
        events = self.read_all()

        state = {
            "build_status": "idle",
            "current_phase": None,
            "current_iter": None,
            "completed_iterations": [],
            "phases_completed": [],
            "delivered_files": [],
            "approved_count": 0,
            "rejected_count": 0,
            "last_event_ts": 0.0,
            "resume_from_iteration": 1,
        }

        for ev in events:
            etype = ev.get("type", "")
            data = ev.get("data", {})
            ts = ev.get("ts", 0)
            state["last_event_ts"] = max(state["last_event_ts"], ts)

            if etype == "build_started":
                state["build_status"] = "running"
                state["completed_iterations"] = []
                state["phases_completed"] = []
                state["delivered_files"] = []
                state["approved_count"] = 0
                state["rejected_count"] = 0

            elif etype == "build_done":
                state["build_status"] = "done"
                state["current_iter"] = None
                state["current_phase"] = None

            elif etype == "stopped":
                state["build_status"] = "stopped"
                state["current_iter"] = None

            elif etype == "error":
                state["build_status"] = "error"

            elif etype == "paused":
                state["build_status"] = "paused"

            elif etype == "resumed":
                state["build_status"] = "running"

            elif etype == "phase_started":
                state["current_phase"] = data.get("phase")

            elif etype == "phase_done":
                phase = data.get("phase")
                if phase is not None and phase not in state["phases_completed"]:
                    state["phases_completed"].append(phase)

            elif etype == "iter_started":
                state["current_iter"] = data.get("id")

            elif etype == "iter_done":
                iter_id = data.get("id")
                approved = data.get("approved", False)
                # Remove from in-progress tracking
                if iter_id is not None:
                    if approved:
                        if iter_id not in state["completed_iterations"]:
                            state["completed_iterations"].append(iter_id)
                        state["approved_count"] += 1
                    else:
                        state["rejected_count"] += 1
                    # Current iteration is now done
                    if state["current_iter"] == iter_id:
                        state["current_iter"] = None

            elif etype == "file_written":
                fpath = data.get("path")
                if fpath and fpath not in state["delivered_files"]:
                    state["delivered_files"].append(fpath)

        # Determine resume point
        if state["build_status"] in ("done",):
            state["resume_from_iteration"] = 1  # full restart
        elif state["completed_iterations"]:
            # Resume from after the last approved iteration
            last_completed = max(state["completed_iterations"])
            state["resume_from_iteration"] = last_completed + 1
        else:
            state["resume_from_iteration"] = 1

        return state


class _EventStream:
    """Singleton event stream. Access via ES module-level instance."""

    def __init__(self):
        self._mu          = threading.Lock()
        self._ring: collections.deque = collections.deque(maxlen=RING_SIZE)
        self._subscribers: list[Callable] = []   # async callbacks
        self._loop: asyncio.AbstractEventLoop | None = None
        self._remote_url: str | None = None
        self._file_store: FileEventStore | None = None

    def set_remote(self, url: str) -> None:
        """Configure ES to forward all emitted events to a remote server."""
        self._remote_url = url.rstrip("/")
        logger.info("[ES] remote forwarding enabled: %s", self._remote_url)

    def set_file_store(self, store: FileEventStore) -> None:
        """Configure the file-backed event store for persistence and resume."""
        self._file_store = store
        logger.info("[ES] file store configured: %s", store.path)

    def get_file_store(self) -> Optional[FileEventStore]:
        """Get the file store if configured."""
        return self._file_store

    # ── Emit ──────────────────────────────────────────────────────────────────

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        """Emit an event. Thread-safe. Called from orchestrator thread."""
        event = {
            "id":    str(uuid.uuid4())[:8],
            "ts":    time.time(),
            "type":  event_type,
            "data":  payload or {},
        }

        # Append to file store (persistent)
        if self._file_store:
            try:
                self._file_store.append(event)
            except Exception as e:
                logger.warning("[ES] file store append failed: %s", e)

        # Add to ring buffer (in-memory subscribers)
        with self._mu:
            self._ring.append(event)
            subs = list(self._subscribers)
            remote_url = self._remote_url

        logger.debug("[ES] %s %s", event_type, str(payload or {})[:80])

        # Push to async subscribers (server process)
        if subs and self._loop and self._loop.is_running():
            for cb in subs:
                asyncio.run_coroutine_threadsafe(cb(event), self._loop)

        # Forward to remote (orchestrator process)
        if remote_url:
            def _forward():
                try:
                    httpx.post(f"{remote_url}/api/live/emit", json=event, timeout=2)
                except Exception as e:
                    logger.debug("[ES] remote forward failed: %s", e)
            threading.Thread(target=_forward, daemon=True).start()

    def inject(self, event: dict) -> None:
        """Inject an externally-generated event into the ring buffer and subscribers."""
        # Also persist if file store is configured
        if self._file_store:
            try:
                self._file_store.append(event)
            except Exception:
                pass

        with self._mu:
            self._ring.append(event)
            subs = list(self._subscribers)

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
        """Last N events — tries file store first for persistence."""
        if self._file_store:
            return self._file_store.tail(limit)
        with self._mu:
            return list(self._ring)[-limit:]

    def since(self, ts: float) -> list[dict]:
        """Events since a timestamp."""
        if self._file_store:
            return [e for e in self._file_store.read_all() if e["ts"] > ts]
        with self._mu:
            return [e for e in self._ring if e["ts"] > ts]

    def clear(self) -> None:
        with self._mu:
            self._ring.clear()
        if self._file_store:
            self._file_store.clear()
        if self._remote_url:
            try:
                httpx.post(f"{self._remote_url}/api/live/reset", timeout=2)
            except Exception:
                pass


# Module-level singleton
ES = _EventStream()
