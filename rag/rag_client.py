"""
rag_client.py — RAG client used by agents.

Two operations agents care about:
  retrieve(query, ...) → list[Path]   top-k relevant chunks as temp files
  ingest(path, ...)                   index a file immediately after writing

The client is instantiated once by the orchestrator and passed to each agent
via the base class. If RAG is not configured (no rag: section in workspace.yaml),
all methods are no-ops so existing code is unaffected.
"""

import logging
import time
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum chunks returned per retrieve call
DEFAULT_TOP_K  = 5
# Maximum characters of chunk text injected per retrieved chunk
MAX_CHUNK_CHARS = 1200


class RagClient:

    def __init__(self, store_path: Path, embed_model: str = "nomic-embed-text"):
        self._store_path  = store_path
        self._embed_model = embed_model
        self._store: Optional["RagStore"] = None
        self._indexer: Optional["Indexer"] = None
        self._enabled = False
        self._temp_files: list[Path] = []
        self._qlog = None
        self._agent_id = ''
        self._task_id  = ''

    def setup(self) -> bool:
        """
        Open or create the LanceDB store. Returns True if successful.
        Must be called before any retrieve/ingest calls.
        """
        try:
            self._store   = RagStore(self._store_path)
            self._indexer = Indexer(self._store)
            self._enabled = True
            logger.info("[rag] store opened at %s", self._store_path)
            return True
        except Exception as e:
            logger.warning("[rag] failed to open store — RAG disabled: %s", e)
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ── Indexing ──────────────────────────────────────────────────────────────

    def ingest_file(self, path: Path, collection: str = "codebase",
                    force: bool = False) -> int:
        """Index one file. Called by agents after writing output."""
        if not self._enabled:
            return 0
        return self._indexer.index_file(path, collection, force=force)

    def ingest_directory(self, directory: Path, collection: str,
                         extensions: Optional[list[str]] = None,
                         force: bool = False) -> int:
        """Index all matching files in a directory. Called on startup."""
        if not self._enabled:
            return 0
        return self._indexer.index_directory(directory, collection,
                                             extensions=extensions, force=force)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        collection: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[Path]:
        """
        Semantic search for query. Returns paths to temporary files containing
        the retrieved chunks — ready to pass as --read to Aider.

        Temporary files are cleaned up on close().
        """
        if not self._enabled or not query.strip():
            return []

        try:
            _t0    = time.time()
            vector  = self._embed(query)
            chunks  = self._store.search(vector, top_k=top_k,
                                         collection=collection,
                                         language=language)
            if not chunks:
                return []

            # Write chunks as temporary context files
            paths = []
            for chunk in chunks:
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".md", delete=False,
                    prefix=f"rag_{chunk['collection']}_"
                )
                # Include source attribution so agent knows where context came from
                tmp.write(
                    f"<!-- RAG context from: {chunk['source_path']} -->\n\n"
                    + chunk["text"][:MAX_CHUNK_CHARS]
                )
                tmp.close()
                p = Path(tmp.name)
                paths.append(p)
                self._temp_files.append(p)

            logger.debug("[rag] retrieved %d chunks for query: %s", len(paths), query[:60])

            # Log query activity
            if self._qlog:
                try:
                    self._qlog.log(
                        agent_id=self._agent_id,
                        task_id=self._task_id,
                        query=query,
                        collection=collection,
                        chunks=chunks,
                        duration_ms=(time.time() - _t0) * 1000,
                    )
                except Exception:
                    pass

            return paths

        except Exception as e:
            logger.warning("[rag] retrieve failed: %s", e)
            return []

    def retrieve_for_task(self, task: dict) -> list[Path]:
        """
        Convenience: build a composite query from a task dict and retrieve.
        Uses description + file path as the search query.
        """
        query_parts = [task.get("description", "")]
        if task.get("file"):
            query_parts.append(task["file"])
        query = " ".join(p for p in query_parts if p)
        return self.retrieve(query, top_k=DEFAULT_TOP_K)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def set_context(self, agent_id: str, task_id: str):
        """Called by orchestrator per task so queries are attributed correctly."""
        self._agent_id = agent_id
        self._task_id  = task_id

    def close(self):
        """Remove temporary files created during this session."""
        for p in self._temp_files:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        self._temp_files.clear()

    # ── Embedding ─────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        import httpx
        resp = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": self._embed_model, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


# ── RagStore — LanceDB wrapper ────────────────────────────────────────────────

class RagStore:

    TABLE_NAME = "chunks"

    def __init__(self, store_path: Path):
        import lancedb
        from rag.schema import CHUNK_SCHEMA
        store_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(store_path))
        if self.TABLE_NAME not in self._db.table_names():
            self._table = self._db.create_table(self.TABLE_NAME, schema=CHUNK_SCHEMA)
            logger.info("[rag] created new table '%s'", self.TABLE_NAME)
        else:
            self._table = self._db.open_table(self.TABLE_NAME)
            logger.info("[rag] opened table '%s' (%d rows)",
                        self.TABLE_NAME, self._table.count_rows())

    def has_file(self, source_path: str, file_hash: str) -> bool:
        try:
            result = (self._table
                      .search(query=None)
                      .where(f"source_path = '{source_path}' AND file_hash = '{file_hash}'")
                      .limit(1)
                      .to_list())
            return len(result) > 0
        except Exception:
            return False

    def delete_file(self, source_path: str):
        try:
            self._table.delete(f"source_path = '{source_path}'")
        except Exception:
            pass

    def upsert(self, rows: list[dict]):
        import pyarrow as pa
        from rag.schema import CHUNK_SCHEMA
        batch = pa.RecordBatch.from_pylist(rows, schema=CHUNK_SCHEMA)
        self._table.add(batch)

    def search(
        self,
        vector: list[float],
        top_k: int,
        collection: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[dict]:
        q = self._table.search(vector).limit(top_k)
        filters = []
        if collection:
            filters.append(f"collection = '{collection}'")
        if language:
            filters.append(f"language = '{language}'")
        if filters:
            q = q.where(" AND ".join(filters))
        try:
            return q.to_list()
        except Exception as e:
            logger.warning("[rag] search error: %s", e)
            return []

    def count(self) -> int:
        return self._table.count_rows()


# ── Indexer import (avoids circular) ─────────────────────────────────────────
from rag.indexer import Indexer
