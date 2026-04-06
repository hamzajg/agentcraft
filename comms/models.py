"""
models.py — shared data schemas for the comms server.

Clarification flow:
  Agent hits blocker
    → POST /clarify  { agentId, taskId, question, file, partialOutput }
    → server stores message, creates pending Future, pushes to UI via WS
    → agent blocks on Future.result(timeout=...)

  Human reads in UI, types reply
    → POST /reply    { messageId, reply }
    → server resolves Future
    → agent unblocks, injects reply into its prompt context, resumes
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class MessageStatus(str, Enum):
    PENDING  = "pending"   # agent waiting for human reply
    REPLIED  = "replied"   # human has replied, agent resumed
    EXPIRED  = "expired"   # timeout — agent used best-guess fallback


class AgentChannel(BaseModel):
    """One channel per agent — like a DM thread."""
    agent_id:    str
    agent_label: str                    # display name: "Backend Dev", "Reviewer"
    unread:      int = 0
    last_active: Optional[datetime] = None


class ClarificationRequest(BaseModel):
    """Agent → comms server: I need human input."""
    agent_id:       str = Field(..., description="e.g. 'backend_dev'")
    task_id:        str = Field(..., description="correlation ID from orchestrator")
    iteration_id:   Optional[int]   = None
    file:           Optional[str]   = None   # file being worked on
    question:       str = Field(..., description="the blocker / question")
    partial_output: Optional[str]   = None   # what the agent has produced so far
    suggestions:    list[str]       = Field(default_factory=list)  # agent's own guesses


class ClarificationMessage(BaseModel):
    """Stored message — shown in chat UI."""
    id:             str             = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id:       str
    agent_label:    str
    task_id:        str
    iteration_id:   Optional[int]   = None
    file:           Optional[str]   = None
    question:       str
    partial_output: Optional[str]   = None
    suggestions:    list[str]       = Field(default_factory=list)
    status:         MessageStatus   = MessageStatus.PENDING
    created_at:     datetime        = Field(default_factory=datetime.utcnow)
    replied_at:     Optional[datetime] = None
    reply:          Optional[str]   = None


class ReplyRequest(BaseModel):
    """Human → comms server: here is my answer."""
    message_id: str
    reply:      str


class ReplyMessage(BaseModel):
    """Sent back over WS to confirm reply received."""
    message_id: str
    reply:      str
    replied_at: datetime = Field(default_factory=datetime.utcnow)


class WsEvent(BaseModel):
    """All WebSocket messages share this envelope."""
    event:   str          # "clarification" | "reply_confirmed" | "agent_status" | "ping"
    payload: dict


class AgentStatus(BaseModel):
    """Agent publishes its current state — shown in sidebar."""
    agent_id:  str
    status:    str        # "running" | "blocked" | "idle" | "complete"
    task_id:   Optional[str] = None
    file:      Optional[str] = None


class LogMessage(BaseModel):
    """Log message from an agent."""
    agent_id:   str
    message:    str
    timestamp:  datetime = Field(default_factory=datetime.utcnow)


# ── display helpers ──────────────────────────────────────────────────────────

AGENT_LABELS = {
    "spec":             "Spec",
    "architect":        "Architect",
    "planner":          "Planner",
    "test_dev":         "Test Dev",
    "backend_dev":      "Backend Dev",
    "config_agent":     "Config",
    "docs_agent":       "Docs",
    "integration_test": "Integration Test",
    "reviewer":         "Reviewer",
    "cicd":             "CI/CD",
    "supervisor":       "Supervisor",
}


def agent_label(agent_id: str) -> str:
    return AGENT_LABELS.get(agent_id, agent_id.replace("_", " ").title())
