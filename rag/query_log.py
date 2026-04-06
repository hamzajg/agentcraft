"""
query_log.py — logs every RAG retrieve() call to SQLite.

Schema:
  rag_queries(id, ts, agent_id, task_id, query_text, collection,
              chunks_returned, top_source, duration_ms)

This is the activity log that powers the "query feed" and
"most retrieved files" views in the React RAG page.
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QueryRecord:
    id:              int
    ts:              float
    agent_id:        str
    task_id:         str
    query_text:      str
    collection:      Optional[str]
    chunks_returned: int
    top_source:      Optional[str]
    duration_ms:     float


class QueryLog:

    TABLE = """
    CREATE TABLE IF NOT EXISTS rag_queries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ts              REAL    NOT NULL,
        agent_id        TEXT    NOT NULL DEFAULT '',
        task_id         TEXT    NOT NULL DEFAULT '',
        query_text      TEXT    NOT NULL,
        collection      TEXT,
        chunks_returned INTEGER NOT NULL DEFAULT 0,
        top_source      TEXT,
        duration_ms     REAL    NOT NULL DEFAULT 0
    )
    """
    IDX = "CREATE INDEX IF NOT EXISTS idx_ts ON rag_queries(ts)"

    def __init__(self, db_path: Path):
        self._db = str(db_path)
        with self._conn() as c:
            c.execute(self.TABLE)
            c.execute(self.IDX)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db)
        c.row_factory = sqlite3.Row
        return c

    def log(self, agent_id: str, task_id: str, query: str,
            collection: Optional[str], chunks: list, duration_ms: float):
        top_source = chunks[0].get("source_path") if chunks else None
        with self._conn() as c:
            c.execute(
                "INSERT INTO rag_queries"
                " (ts,agent_id,task_id,query_text,collection,chunks_returned,top_source,duration_ms)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (time.time(), agent_id, task_id, query[:500],
                 collection, len(chunks), top_source, round(duration_ms, 1))
            )

    def recent(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM rag_queries ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def top_sources(self, limit: int = 20) -> list[dict]:
        """Files most frequently returned by retrieval."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT top_source as source, COUNT(*) as hits
                FROM rag_queries
                WHERE top_source IS NOT NULL
                GROUP BY top_source
                ORDER BY hits DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def queries_per_agent(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT agent_id, COUNT(*) as queries,
                       AVG(chunks_returned) as avg_chunks,
                       AVG(duration_ms) as avg_ms
                FROM rag_queries
                GROUP BY agent_id
                ORDER BY queries DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def summary(self) -> dict:
        with self._conn() as c:
            total   = c.execute("SELECT COUNT(*) FROM rag_queries").fetchone()[0]
            avg_ms  = c.execute("SELECT AVG(duration_ms) FROM rag_queries").fetchone()[0] or 0
            avg_hit = c.execute("SELECT AVG(chunks_returned) FROM rag_queries").fetchone()[0] or 0
            zero    = c.execute(
                "SELECT COUNT(*) FROM rag_queries WHERE chunks_returned=0"
            ).fetchone()[0]
        return {
            "total_queries":    total,
            "avg_duration_ms":  round(avg_ms, 1),
            "avg_chunks":       round(avg_hit, 2),
            "zero_hit_queries": zero,
            "hit_rate_pct":     round((total - zero) / total * 100, 1) if total else 0,
        }

    def clear(self):
        with self._conn() as c:
            c.execute("DELETE FROM rag_queries")
