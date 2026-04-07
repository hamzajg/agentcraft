"""
clarification_client.py — agent-side client for the comms server.

Agents call ask() when they need human input.
ask() blocks the calling thread until the human replies or timeout expires.

Usage in any agent:
    from clarification_client import ClarificationClient

    clarifier = ClarificationClient(agent_id="backend_dev", task_id=task["id"])

    reply = clarifier.ask(
        question="Should I use ConcurrentHashMap or a synchronized List for stepResults?",
        file=task["file"],
        partial_output="public class SupervisorActor {\n  private final Map<...",
        suggestions=["ConcurrentHashMap keyed by stepIndex", "synchronized ArrayList"],
        timeout=3600,   # 1 hour — human might be away
    )
    # reply is the human's text, or the first suggestion on timeout
"""

import logging
import asyncio
import threading
import os
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

COMMS_URL = os.getenv("COMMS_SERVER_URL", "http://localhost:7000")


class ClarificationClient:

    def __init__(self, agent_id: str, task_id: str, iteration_id: Optional[int] = None):
        self.agent_id     = agent_id
        self.task_id      = task_id
        self.iteration_id = iteration_id
        self._message_id: Optional[str] = None

    def ask(
        self,
        question: str,
        file: Optional[str] = None,
        partial_output: Optional[str] = None,
        suggestions: Optional[list[str]] = None,
        timeout: int = 3600,
    ) -> str:
        """
        Post a clarification request and BLOCK until the human replies.

        Returns:
          - The human's reply text, or
          - The first suggestion (if timeout expires with no reply), or
          - Empty string (if no suggestions and timeout expires)
        """
        suggestions = suggestions or []
        fallback    = suggestions[0] if suggestions else ""

        logger.info(
            "[clarifier] %s asking: %s (timeout=%ds)", self.agent_id, question[:80], timeout
        )

        # POST to comms server — get message_id back
        import time
        max_retries = 10
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=10) as client:
                    resp = client.post(f"{COMMS_URL}/api/clarify", json={
                        "agent_id":       self.agent_id,
                        "task_id":        self.task_id,
                        "iteration_id":   self.iteration_id,
                        "file":           file,
                        "question":       question,
                        "partial_output": partial_output,
                        "suggestions":    suggestions,
                    })
                    resp.raise_for_status()
                    self._message_id = resp.json()["message_id"]
                    break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error("[clarifier] could not reach comms server after %d attempts: %s — using fallback", max_retries, e)
                    return fallback
                logger.warning("[clarifier] comms server not ready (attempt %d/%d): %s — retrying", attempt + 1, max_retries, e)
                time.sleep(1)

        # Block this thread using an event — resolved by polling
        reply_event = threading.Event()
        reply_holder: list[str] = []

        def _poll():
            """Poll the comms server until our message is replied to."""
            import time
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    with httpx.Client(timeout=5) as c:
                        r = c.get(f"{COMMS_URL}/api/messages/{self.agent_id}", params={"limit": 20})
                        msgs = r.json()
                        for m in msgs:
                            if m["id"] == self._message_id and m["status"] == "replied":
                                reply_holder.append(m["reply"] or "")
                                reply_event.set()
                                return
                except Exception:
                    pass
                time.sleep(2)
            # Timeout — use fallback
            reply_holder.append(fallback)
            reply_event.set()

        poll_thread = threading.Thread(target=_poll, daemon=True)
        poll_thread.start()
        reply_event.wait(timeout=timeout + 5)

        reply = reply_holder[0] if reply_holder else fallback
        logger.info("[clarifier] %s received reply: %s", self.agent_id, reply[:80])
        return reply

    def report_status(self, status: str, file: Optional[str] = None):
        """Non-blocking — update this agent's status in the UI sidebar."""
        try:
            with httpx.Client(timeout=3) as client:
                client.post(f"{COMMS_URL}/api/status", json={
                    "agent_id": self.agent_id,
                    "status":   status,
                    "task_id":  self.task_id,
                    "file":     file,
                })
        except Exception:
            pass  # Status updates are best-effort

    def info(self, message: str, file: Optional[str] = None):
        """Post an informational update to the agent's chat channel (non-blocking)."""
        try:
            with httpx.Client(timeout=3) as client:
                client.post(f"{COMMS_URL}/api/clarify", json={
                    "agent_id":     self.agent_id,
                    "task_id":      self.task_id,
                    "iteration_id": self.iteration_id,
                    "file":         file,
                    "question":     message,
                    "status":       "info",
                })
        except Exception:
            pass

    def complete(self, message: str, file: Optional[str] = None):
        """Post a final completion message to the agent's chat channel (non-blocking)."""
        try:
            with httpx.Client(timeout=3) as client:
                client.post(f"{COMMS_URL}/api/clarify", json={
                    "agent_id":     self.agent_id,
                    "task_id":      self.task_id,
                    "iteration_id": self.iteration_id,
                    "file":         file,
                    "question":     message,
                    "status":       "completed",
                })
        except Exception:
            pass
