"""
core/bus.py — AgentBus

The central nervous system for agent-to-agent communication.

Four primitives every agent inherits via base.py:

  ask_agent(target, question, context)  → str
    Blocking request/reply between agents. The target agent's
    registered handler is called synchronously. Falls back to
    local LLM if no handler is registered.

  share_context(key, value)
    Publish structured data to the shared context store.
    Any agent can read it. Persists for the lifetime of the build.
    e.g. architect shares "iteration_plan", spec shares "domain_model"

  read_context(key)  → dict | str | None
    Read a value from the shared context store by key.

  delegate(target_role, task_dict)  → dict
    Ask another agent to execute a task and return the result.
    Blocks until the delegated agent finishes. The orchestrator
    does not see delegated subtasks.

Bus also broadcasts all events over WebSocket so the comms UI
can display live agent-to-agent activity.

Thread safety: all operations are protected by threading.Lock.
"""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── Message types ──────────────────────────────────────────────────────────────

class MsgType(str, Enum):
    QUERY     = "query"      # blocking ask from one agent to another
    REPLY     = "reply"      # response to a QUERY
    CONTEXT   = "context"    # agent publishes shared context
    DELEGATE  = "delegate"   # agent assigns a subtask to another agent
    BROADCAST = "broadcast"  # agent announces state / completion


@dataclass
class BusMessage:
    id:          str
    type:        MsgType
    from_agent:  str
    to_agent:    Optional[str]   # None = broadcast to all
    content:     Any             # str for QUERY/REPLY, dict for CONTEXT/DELEGATE
    ref_id:      Optional[str]   # for REPLY: the QUERY id this answers
    ts:          float           = field(default_factory=time.time)
    task_id:     Optional[str]   = None
    iteration_id: Optional[int]  = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


# ── Handler registry ───────────────────────────────────────────────────────────

QueryHandler = Callable[[str, dict], str]
# fn(question: str, context: dict) -> answer: str


# ── AgentBus ───────────────────────────────────────────────────────────────────

class AgentBus:
    """
    Singleton in-process message broker.
    Get the instance with AgentBus.instance().
    """

    _inst: Optional["AgentBus"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "AgentBus":
        with cls._lock:
            if cls._inst is None:
                cls._inst = cls()
            return cls._inst

    @classmethod
    def reset(cls):
        """Reset for new build run."""
        with cls._lock:
            cls._inst = None

    def __init__(self):
        self._mu             = threading.Lock()
        self._messages:  list[BusMessage]          = []   # full audit log
        self._context:   dict[str, Any]            = {}   # shared key-value store
        self._handlers:  dict[str, QueryHandler]   = {}   # role → handler fn
        self._agents:    dict[str, Any]             = {}   # role → agent instance (for delegate)
        self._ws_push_fn: Optional[Callable]       = None # injected by comms server

    # ── Registration ──────────────────────────────────────────────────────────

    def register_agent(self, role: str, agent_instance: Any):
        """Called by orchestrator after building each agent."""
        with self._mu:
            self._agents[role] = agent_instance
        logger.debug("[bus] registered agent: %s", role)

    def register_handler(self, role: str, fn: QueryHandler):
        """Agent registers a function to handle queries directed at it."""
        with self._mu:
            self._handlers[role] = fn
        logger.debug("[bus] handler registered: %s", role)

    def set_ws_push(self, fn: Callable):
        """Injected by the comms server to push events to the UI."""
        self._ws_push_fn = fn

    # ── QUERY / REPLY ─────────────────────────────────────────────────────────

    def ask(
        self,
        from_role:   str,
        to_role:     str,
        question:    str,
        context:     dict      = None,
        task_id:     str       = None,
        iter_id:     int       = None,
        timeout:     float     = 30.0,
        fallback_llm: Any      = None,   # OllamaClient | None
    ) -> str:
        """
        Ask another agent a question. Blocks until answered.

        Resolution order:
          1. Registered handler for to_role
          2. Local LLM fallback (if fallback_llm provided)
          3. Empty string (silent, non-blocking fallback)
        """
        ctx = context or {}
        qmsg = self._record(BusMessage(
            id=str(uuid.uuid4()), type=MsgType.QUERY,
            from_agent=from_role, to_agent=to_role,
            content={"question": question, "context": ctx},
            ref_id=None, task_id=task_id, iteration_id=iter_id,
        ))

        logger.info("[bus] QUERY  %s → %s: %s", from_role, to_role, question[:80])
        self._push_ws("agent_query", qmsg.to_dict())

        # Try registered handler
        handler = self._handlers.get(to_role)
        if handler:
            try:
                answer = handler(question, ctx)
                self._record_reply(qmsg, from_role, to_role, answer, task_id, iter_id)
                return answer
            except Exception as e:
                logger.warning("[bus] handler for %s raised: %s", to_role, e)

        # Try local LLM fallback
        if fallback_llm:
            try:
                prompt = (
                    f"You are acting as the {to_role} agent. "
                    f"Another agent ({from_role}) is asking:\n\n{question}\n\n"
                    + (f"Context: {json.dumps(ctx)}\n\n" if ctx else "")
                    + "Give a concise, expert answer."
                )
                answer = fallback_llm.chat(prompt) or ""
                self._record_reply(qmsg, from_role, to_role, answer, task_id, iter_id)
                return answer
            except Exception as e:
                logger.warning("[bus] LLM fallback failed: %s", e)

        logger.warning("[bus] no handler or LLM for %s — returning empty", to_role)
        return ""

    def _record_reply(self, qmsg, from_role, to_role, answer, task_id, iter_id):
        rmsg = self._record(BusMessage(
            id=str(uuid.uuid4()), type=MsgType.REPLY,
            from_agent=to_role, to_agent=from_role,
            content=answer, ref_id=qmsg.id,
            task_id=task_id, iteration_id=iter_id,
        ))
        logger.info("[bus] REPLY  %s → %s: %s", to_role, from_role, str(answer)[:80])
        self._push_ws("agent_reply", rmsg.to_dict())

    # ── CONTEXT store ─────────────────────────────────────────────────────────

    def publish(
        self,
        from_role: str,
        key:       str,
        value:     Any,
        task_id:   str = None,
        iter_id:   int = None,
    ):
        """
        Publish a value to the shared context store.
        Key convention: "<role>.<topic>"  e.g. "architect.iteration_plan"
        """
        full_key = key if "." in key else f"{from_role}.{key}"
        with self._mu:
            self._context[full_key] = value

        msg = self._record(BusMessage(
            id=str(uuid.uuid4()), type=MsgType.CONTEXT,
            from_agent=from_role, to_agent=None,
            content={"key": full_key, "value": _truncate(value)},
            ref_id=None, task_id=task_id, iteration_id=iter_id,
        ))
        logger.info("[bus] CONTEXT %s published: %s", from_role, full_key)
        self._push_ws("agent_context", msg.to_dict())

    def read(self, key: str, requester: str = "") -> Any:
        """Read a value from the shared context store."""
        full_key = key if "." in key else key
        with self._mu:
            value = self._context.get(full_key)
        if value is not None:
            logger.debug("[bus] READ  %s read %s", requester, full_key)
        return value

    def context_snapshot(self) -> dict:
        """Full context store snapshot — used by UI and new agents onboarding."""
        with self._mu:
            return dict(self._context)

    # ── DELEGATE ──────────────────────────────────────────────────────────────

    def delegate(
        self,
        from_role:    str,
        to_role:      str,
        task:         dict,
        docs_dir:     Path   = None,
        task_id:      str    = None,
        iter_id:      int    = None,
    ) -> dict:
        """
        Ask an agent to execute a task and return the result dict.
        Blocks until the agent finishes.
        """
        msg = self._record(BusMessage(
            id=str(uuid.uuid4()), type=MsgType.DELEGATE,
            from_agent=from_role, to_agent=to_role,
            content={"task": task}, ref_id=None,
            task_id=task_id, iteration_id=iter_id,
        ))
        logger.info("[bus] DELEGATE %s → %s: %s", from_role, to_role, task.get("description","")[:60])
        self._push_ws("agent_delegate", msg.to_dict())

        agent = self._agents.get(to_role)
        if agent is None:
            logger.warning("[bus] delegate: no agent registered for %s", to_role)
            return {"success": False, "error": f"agent {to_role} not registered"}

        try:
            # Agents expose .implement() or .run_task()
            fn = getattr(agent, "implement", None) or getattr(agent, "run_task", None)
            if fn is None:
                return {"success": False, "error": f"{to_role} has no implement/run_task method"}
            result = fn(task, docs_dir or agent.workspace)
            reply_msg = self._record(BusMessage(
                id=str(uuid.uuid4()), type=MsgType.REPLY,
                from_agent=to_role, to_agent=from_role,
                content={"result": _truncate(result)}, ref_id=msg.id,
                task_id=task_id, iteration_id=iter_id,
            ))
            self._push_ws("agent_reply", reply_msg.to_dict())
            return result or {}
        except Exception as e:
            logger.error("[bus] delegate to %s failed: %s", to_role, e)
            return {"success": False, "error": str(e)}

    # ── BROADCAST ─────────────────────────────────────────────────────────────

    def broadcast(
        self,
        from_role:  str,
        event:      str,
        data:       dict   = None,
        task_id:    str    = None,
        iter_id:    int    = None,
    ):
        """Announce a state change or completion to all agents."""
        msg = self._record(BusMessage(
            id=str(uuid.uuid4()), type=MsgType.BROADCAST,
            from_agent=from_role, to_agent=None,
            content={"event": event, "data": data or {}},
            ref_id=None, task_id=task_id, iteration_id=iter_id,
        ))
        logger.info("[bus] BROADCAST %s: %s", from_role, event)
        self._push_ws("agent_broadcast", msg.to_dict())

    # ── Log access ────────────────────────────────────────────────────────────

    def messages(self, limit: int = 100) -> list[dict]:
        with self._mu:
            return [m.to_dict() for m in self._messages[-limit:]]

    def messages_between(self, agent_a: str, agent_b: str) -> list[dict]:
        with self._mu:
            return [
                m.to_dict() for m in self._messages
                if m.from_agent in (agent_a, agent_b)
                and (m.to_agent in (agent_a, agent_b) or m.to_agent is None)
            ]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _record(self, msg: BusMessage) -> BusMessage:
        with self._mu:
            self._messages.append(msg)
        return msg

    def _push_ws(self, event: str, payload: dict):
        if self._ws_push_fn:
            try:
                self._ws_push_fn(event, payload)
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _truncate(value: Any, max_len: int = 300) -> Any:
    """Truncate large values for logging/UI display."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "…"
    if isinstance(value, dict):
        return {k: _truncate(v, 100) for k, v in list(value.items())[:10]}
    if isinstance(value, list):
        return [_truncate(v, 100) for v in value[:5]]
    return value
