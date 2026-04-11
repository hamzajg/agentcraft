"""
indexer.py — file indexing pipeline.

Takes a file path + collection name → chunks it → embeds each chunk
via Ollama nomic-embed-text → upserts into LanceDB.

Incremental: tracks file hashes so unchanged files are skipped.
Thread-safe: LanceDB writes are synchronous; call from any thread.
"""

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE      = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_EMBED_URL = f"{OLLAMA_BASE}/api/embeddings"
BATCH_SIZE       = 16   # chunks per embedding request


class Indexer:

    def __init__(self, store, embed_model: str = "nomic-embed-text"):
        """
        store: RagStore instance (provides .table and .get_hashes())
        """
        self._store = store
        self._embed_model = embed_model

    def index_file(self, path: Path, collection: str,
                   force: bool = False) -> int:
        """
        Index one file. Returns number of chunks upserted (0 if skipped).

        Skips files whose hash hasn't changed since last index,
        unless force=True.
        """
        if not path.exists() or not path.is_file():
            return 0

        file_hash = _md5(path)
        if not force and self._store.has_file(str(path), file_hash):
            logger.debug("[indexer] unchanged: %s", path)
            return 0

        from rag.chunker import chunk_file
        chunks = chunk_file(path)
        if not chunks:
            logger.debug("[indexer] no chunks: %s", path)
            return 0

        logger.info("[indexer] indexing %s (%d chunks)", path, len(chunks))

        # Delete stale records for this file
        self._store.delete_file(str(path))

        # Embed in batches
        texts   = [c.text for c in chunks]
        vectors = _embed_batch(texts, self._embed_model)

        if not vectors:
            logger.warning("[indexer] embedding failed for %s", path)
            return 0

        rows = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            rows.append({
                "vector":      vector,
                "text":        chunk.text,
                "source_path": str(path),
                "collection":  collection,
                "chunk_index": chunk.chunk_index,
                "language":    chunk.language,
                "file_hash":   file_hash,
            })

        self._store.upsert(rows)
        logger.debug("[indexer] upserted %d chunks for %s", len(rows), path)
        return len(rows)

    def index_directory(self, directory: Path, collection: str,
                        extensions: Optional[list[str]] = None,
                        force: bool = False) -> int:
        """Index all matching files in a directory tree."""
        if not directory.exists():
            logger.warning("[indexer] directory not found: %s", directory)
            return 0

        from rag.schema import LANGUAGE_MAP
        valid_exts = set(extensions or list(LANGUAGE_MAP.keys()) + [".md", ".txt"])

        total = 0
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in valid_exts:
                # Skip hidden dirs, build artifacts, and the RAG store itself
                parts = path.parts
                if any(p.startswith(".") for p in parts):
                    continue
                if any(p in ("target", "node_modules", "__pycache__", ".rag") for p in parts):
                    continue
                total += self.index_file(path, collection, force=force)
        logger.info("[indexer] indexed %d chunks from %s [%s]", total, directory, collection)
        return total


# ── Embedding via Ollama ──────────────────────────────────────────────────────

def _embed_batch(texts: list[str], embed_model: str) -> list[list[float]]:
    """Embed a list of texts using Ollama. Returns list of vectors."""
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        batch_vectors = _embed_texts(batch, embed_model)
        if batch_vectors is None:
            return []
        vectors.extend(batch_vectors)
    return vectors


def _embed_texts(texts: list[str], embed_model: str) -> Optional[list[list[float]]]:
    """Call Ollama embedding endpoint for a batch of texts."""
    results = []
    for text in texts:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(OLLAMA_EMBED_URL, json={
                    "model":  embed_model,
                    "prompt": text,
                })
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        except Exception as e:
            logger.error("[indexer] embed error: %s", e)
            return None
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()
