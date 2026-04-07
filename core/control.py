"""
core/control.py — Build control channel.

The comms server writes control commands here.
The orchestrator reads them between every task and iteration.

Design: threading.Event flags + a queue for directives.
All methods are thread-safe.

Usage (comms server — REST handler):
    from core.control import CC
    CC.pause_after_task()
    CC.inject_directive("Use CompletableFuture not Reactor")
    CC.approve(iteration_id=2)
    CC.stop()

Usage (orchestrator — between steps):
    CC.check()                # raises Paused or Stopped
    d = CC.pop_directive()    # None or str
    CC.wait_approval(iter_id) # blocks until approved/rejected
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class BuildPaused(Exception):
    """Raised by CC.check() when the build is paused."""


class BuildStopped(Exception):
    """Raised by CC.check() when the build has been stopped."""


@dataclass
class ApprovalGate:
    iteration_id:   int
    approved:       Optional[bool] = None   # None = pending
    reject_reason:  str = ""
    event:          threading.Event = field(default_factory=threading.Event)


class _ControlChannel:
    """Singleton control channel. Access via CC module-level instance."""

    def __init__(self):
        self._mu                  = threading.Lock()
        self._pause_after_task    = threading.Event()
        self._pause_after_iter    = threading.Event()
        self._paused              = threading.Event()   # currently paused
        self._stopped             = threading.Event()
        self._directives: queue.Queue[str] = queue.Queue()
        self._approval_gates: dict[int, ApprovalGate] = {}
        self._approval_enabled    = True   # set False to skip gates

    # ── Commands (called by comms server) ─────────────────────────────────────

    def pause_after_task(self) -> None:
        logger.info("[CC] pause_after_task requested")
        self._pause_after_task.set()

    def pause_after_iter(self) -> None:
        logger.info("[CC] pause_after_iter requested")
        self._pause_after_iter.set()

    def resume(self) -> None:
        logger.info("[CC] resume requested")
        self._pause_after_task.clear()
        self._pause_after_iter.clear()
        self._paused.clear()

    def stop(self) -> None:
        logger.info("[CC] stop requested")
        self._stopped.set()
        self._paused.clear()      # unblock any wait so it can exit

    def inject_directive(self, text: str) -> None:
        """Queue a directive string for the next agent task."""
        logger.info("[CC] directive: %s", text[:80])
        self._directives.put(text.strip())

    def approve(self, iteration_id: int) -> None:
        with self._mu:
            gate = self._approval_gates.get(iteration_id)
        if gate:
            gate.approved = True
            gate.event.set()
            logger.info("[CC] iteration %d approved", iteration_id)

    def reject(self, iteration_id: int, reason: str = "") -> None:
        with self._mu:
            gate = self._approval_gates.get(iteration_id)
        if gate:
            gate.approved      = False
            gate.reject_reason = reason
            gate.event.set()
            logger.info("[CC] iteration %d rejected: %s", iteration_id, reason)

    def set_approval_gates(self, enabled: bool) -> None:
        self._approval_enabled = enabled

    # ── Orchestrator hooks (called from orchestrator thread) ──────────────────

    def check_after_task(self) -> None:
        """Call after every task. Blocks if paused. Raises BuildStopped."""
        if self._stopped.is_set():
            raise BuildStopped()
        if self._pause_after_task.is_set():
            self._pause_after_task.clear()
            self._do_pause("after_task")

    def check_after_iter(self) -> None:
        """Call after every iteration. Blocks if paused. Raises BuildStopped."""
        if self._stopped.is_set():
            raise BuildStopped()
        if self._pause_after_iter.is_set():
            self._pause_after_iter.clear()
            self._do_pause("after_iter")

    def check_stop(self) -> None:
        """Lightweight stop check — call frequently inside loops."""
        if self._stopped.is_set():
            raise BuildStopped()

    def pop_directive(self) -> Optional[str]:
        """Return and remove the next queued directive, or None."""
        try:
            return self._directives.get_nowait()
        except queue.Empty:
            return None

    def wait_approval(self, iteration_id: int, timeout: float = 3600.0) -> bool:
        """
        Block until the iteration is approved or rejected.
        Returns True (approved) or False (rejected / timed out).
        Raises BuildStopped if stop() is called while waiting.
        """
        if not self._approval_enabled:
            return True

        gate = ApprovalGate(iteration_id=iteration_id)
        with self._mu:
            self._approval_gates[iteration_id] = gate

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stopped.is_set():
                raise BuildStopped()
            if gate.event.wait(timeout=2.0):
                break

        with self._mu:
            self._approval_gates.pop(iteration_id, None)

        if gate.approved is None:
            logger.warning("[CC] approval gate timed out for iter %d — auto-approving", iteration_id)
            return True
        return bool(gate.approved)

    # ── State inspection (for /api/live/state) ────────────────────────────────

    def state(self) -> dict:
        pending_directives = list(self._directives.queue)
        with self._mu:
            pending_gates = [
                {"iteration_id": g.iteration_id, "approved": g.approved}
                for g in self._approval_gates.values()
            ]
        return {
            "paused":              self._paused.is_set(),
            "stopped":             self._stopped.is_set(),
            "pause_after_task":    self._pause_after_task.is_set(),
            "pause_after_iter":    self._pause_after_iter.is_set(),
            "approval_gates_enabled": self._approval_enabled,
            "pending_directives":  len(pending_directives),
            "pending_gates":       pending_gates,
        }

    def reset(self) -> None:
        """Clear all flags for a new build run."""
        self._pause_after_task.clear()
        self._pause_after_iter.clear()
        self._paused.clear()
        self._stopped.clear()
        while not self._directives.empty():
            try:
                self._directives.get_nowait()
            except queue.Empty:
                break
        with self._mu:
            self._approval_gates.clear()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _do_pause(self, reason: str) -> None:
        from core.event_stream import ES
        self._paused.set()
        ES.emit("paused", {"reason": reason})
        logger.info("[CC] build paused (%s) — waiting for resume()", reason)
        # Block until resumed or stopped
        while self._paused.is_set():
            if self._stopped.is_set():
                self._paused.clear()
                raise BuildStopped()
            time.sleep(0.5)
        ES.emit("resumed", {})
        logger.info("[CC] build resumed")


# Module-level singleton
CC = _ControlChannel()
