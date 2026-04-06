"""
rag_stats.py — RAG observatory stats engine.

Reads LanceDB and the query log to produce a unified snapshot
used by both the CLI and the React page.

RagStats.snapshot() → dict   full stats
RagStats.files()    → list   per-file breakdown
RagStats.queries()  → dict   query activity summary
"""

import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RagStats:

    def __init__(self, store_path: Path, query_log_path: Optional[Path] = None):
        self._store_path     = store_path
        self._query_log_path = query_log_path or store_path / "rag_queries.db"
        self._table          = None
        self._qlog           = None
        self._load()

    def _load(self):
        try:
            import lancedb
            if (self._store_path / "chunks.lance").exists() or \
               any(self._store_path.glob("*.lance")):
                db           = lancedb.connect(str(self._store_path))
                if "chunks" in db.table_names():
                    self._table = db.open_table("chunks")
        except Exception as e:
            logger.debug("[rag_stats] LanceDB not available: %s", e)

        try:
            from rag.query_log import QueryLog
            self._qlog = QueryLog(self._query_log_path)
        except Exception as e:
            logger.debug("[rag_stats] query log not available: %s", e)

    # ── Public API ────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Full stats snapshot — used by /api/rag/stats."""
        index    = self._index_stats()
        queries  = self._qlog.summary() if self._qlog else {}
        top_src  = self._qlog.top_sources(10) if self._qlog else []
        by_agent = self._qlog.queries_per_agent() if self._qlog else []

        return {
            "ts":            time.time(),
            "store_path":    str(self._store_path),
            "index":         index,
            "queries":       queries,
            "top_sources":   top_src,
            "by_agent":      by_agent,
            "store_size_mb": _dir_size_mb(self._store_path),
        }

    def files(self, limit: int = 200) -> list[dict]:
        """Per-file breakdown — used by /api/rag/files."""
        if self._table is None:
            return []
        try:
            rows = (self._table
                    .search(query=None)
                    .select(["source_path", "collection", "language",
                             "chunk_index", "text"])
                    .to_list())
        except Exception:
            return []

        # Aggregate by source_path
        files: dict[str, dict] = {}
        for r in rows:
            path = r.get("source_path", "unknown")
            if path not in files:
                p = Path(path)
                files[path] = {
                    "path":        path,
                    "name":        p.name,
                    "collection":  r.get("collection", ""),
                    "language":    r.get("language", ""),
                    "chunks":      0,
                    "chars":       0,
                    "exists":      p.exists(),
                }
            files[path]["chunks"] += 1
            files[path]["chars"]  += len(r.get("text", ""))

        # Add line count for existing files
        result = list(files.values())
        for f in result:
            if f["exists"]:
                try:
                    f["lines"] = Path(f["path"]).read_text(
                        errors="replace").count("\n") + 1
                except Exception:
                    f["lines"] = 0
            else:
                f["lines"] = 0

        result.sort(key=lambda x: x["chunks"], reverse=True)
        return result[:limit]

    def queries(self, limit: int = 50) -> dict:
        """Query activity — used by /api/rag/queries."""
        if self._qlog is None:
            return {"recent": [], "top_sources": [], "by_agent": []}
        return {
            "recent":      self._qlog.recent(limit),
            "top_sources": self._qlog.top_sources(20),
            "by_agent":    self._qlog.queries_per_agent(),
            "summary":     self._qlog.summary(),
        }

    def clear_queries(self):
        if self._qlog:
            self._qlog.clear()

    # ── Index stats ───────────────────────────────────────────────────────────

    def _index_stats(self) -> dict:
        if self._table is None:
            return {
                "total_chunks": 0, "total_files": 0,
                "total_chars": 0,  "total_lines": 0,
                "collections": {}, "languages": {},
                "status": "empty",
            }
        try:
            rows = (self._table
                    .search(query=None)
                    .select(["source_path", "collection", "language", "text"])
                    .to_list())
        except Exception:
            return {"status": "error", "total_chunks": 0}

        collections: dict[str, int] = {}
        languages:   dict[str, int] = {}
        files:       set[str]       = set()
        total_chars  = 0
        total_lines  = 0

        for r in rows:
            col  = r.get("collection", "unknown")
            lang = r.get("language", "other")
            src  = r.get("source_path", "")
            text = r.get("text", "")

            collections[col]  = collections.get(col, 0)  + 1
            languages[lang]   = languages.get(lang, 0)   + 1
            files.add(src)
            total_chars += len(text)
            total_lines += text.count("\n") + 1

        return {
            "total_chunks": len(rows),
            "total_files":  len(files),
            "total_chars":  total_chars,
            "total_lines":  total_lines,
            "collections":  collections,
            "languages":    languages,
            "status":       "ok" if rows else "empty",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dir_size_mb(path: Path) -> float:
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return round(total / (1024 * 1024), 2)
    except Exception:
        return 0.0
