"""
store.py — SQLite-backed message store.

Persists all clarification messages and replies so chat history
survives server restarts. Agents are identified by agent_id (channel).
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ClarificationMessage, MessageStatus

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "comms.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id             TEXT PRIMARY KEY,
                agent_id       TEXT NOT NULL,
                agent_label    TEXT NOT NULL,
                task_id        TEXT NOT NULL,
                iteration_id   INTEGER,
                file           TEXT,
                question       TEXT NOT NULL,
                partial_output TEXT,
                suggestions    TEXT DEFAULT '[]',
                status         TEXT DEFAULT 'pending',
                created_at     TEXT NOT NULL,
                replied_at     TEXT,
                reply          TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_agent ON messages(agent_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_status ON messages(status)")
    logger.info("[store] database initialised: %s", DB_PATH)


def save(msg: ClarificationMessage):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO messages
              (id, agent_id, agent_label, task_id, iteration_id, file,
               question, partial_output, suggestions, status, created_at, replied_at, reply)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            msg.id, msg.agent_id, msg.agent_label, msg.task_id,
            msg.iteration_id, msg.file, msg.question, msg.partial_output,
            json.dumps(msg.suggestions), msg.status.value,
            msg.created_at.isoformat(),
            msg.replied_at.isoformat() if msg.replied_at else None,
            msg.reply,
        ))


def mark_replied(message_id: str, reply: str) -> Optional[ClarificationMessage]:
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("""
            UPDATE messages
            SET status='replied', reply=?, replied_at=?
            WHERE id=?
        """, (reply, now, message_id))
    return get(message_id)


def get(message_id: str) -> Optional[ClarificationMessage]:
    with _conn() as c:
        row = c.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    return _row_to_msg(row) if row else None


def list_by_agent(agent_id: str, limit: int = 50) -> list[ClarificationMessage]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE agent_id=? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit)
        ).fetchall()
    return [_row_to_msg(r) for r in rows]


def list_pending() -> list[ClarificationMessage]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE status='pending' ORDER BY created_at ASC"
        ).fetchall()
    return [_row_to_msg(r) for r in rows]


def list_agents_with_history() -> list[dict]:
    """Return all available agents, with message history if any."""
    from .models import agent_label
    
    # Get all available agents
    try:
        from agents import list_agents
        all_agent_ids = list_agents()
    except ImportError:
        all_agent_ids = []
    
    # Get message history for agents that have sent messages
    with _conn() as c:
        rows = c.execute("""
            SELECT agent_id, agent_label,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS unread,
                   MAX(created_at) AS last_active
            FROM messages
            GROUP BY agent_id
            ORDER BY last_active DESC
        """).fetchall()
    
    # Create a dict of agents with history
    agents_with_history = {r["agent_id"]: dict(r) for r in rows}
    
    # Build the full list
    result = []
    for agent_id in all_agent_ids:
        if agent_id in agents_with_history:
            # Agent has history
            result.append(agents_with_history[agent_id])
        else:
            # Agent has no history yet
            result.append({
                "agent_id": agent_id,
                "agent_label": agent_label(agent_id),
                "total": 0,
                "unread": 0,
                "last_active": None
            })
    
    # Sort by last_active desc, then by agent_id
    result.sort(key=lambda x: (x["last_active"] or "", x["agent_id"]), reverse=True)
    return result


def _row_to_msg(row: sqlite3.Row) -> ClarificationMessage:
    return ClarificationMessage(
        id=row["id"],
        agent_id=row["agent_id"],
        agent_label=row["agent_label"],
        task_id=row["task_id"],
        iteration_id=row["iteration_id"],
        file=row["file"],
        question=row["question"],
        partial_output=row["partial_output"],
        suggestions=json.loads(row["suggestions"] or "[]"),
        status=MessageStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        replied_at=datetime.fromisoformat(row["replied_at"]) if row["replied_at"] else None,
        reply=row["reply"],
    )
