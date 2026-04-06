"""
schema.py — LanceDB table schemas for RAG collections.

Three collections in one store (.rag/ at repo root):
  docs      — project documentation, specs, use cases
  codebase  — agent-generated output files (grows during a run)
  legacy    — existing source code for legacy/migration projects

Each chunk stores:
  vector      — 768-dim nomic-embed-text embedding
  text        — the chunk text (what gets injected into agent context)
  source_path — relative path of the source file
  collection  — "docs" | "codebase" | "legacy"
  chunk_index — position within the file (for reconstruction)
  language    — file type: "markdown" | "java" | "python" | "yaml" | "json" | "shell" | "other"
  file_hash   — md5 of the file at index time (for incremental updates)
"""

import pyarrow as pa

# nomic-embed-text produces 768-dim vectors
EMBEDDING_DIM = 768

CHUNK_SCHEMA = pa.schema([
    pa.field("vector",      pa.list_(pa.float32(), EMBEDDING_DIM)),
    pa.field("text",        pa.string()),
    pa.field("source_path", pa.string()),
    pa.field("collection",  pa.string()),
    pa.field("chunk_index", pa.int32()),
    pa.field("language",    pa.string()),
    pa.field("file_hash",   pa.string()),
])

COLLECTIONS = ["docs", "codebase", "legacy"]

# File extensions → language label
LANGUAGE_MAP = {
    ".java":       "java",
    ".py":         "python",
    ".md":         "markdown",
    ".yaml":       "yaml",
    ".yml":        "yaml",
    ".json":       "json",
    ".sh":         "shell",
    ".bash":       "shell",
    ".properties": "properties",
    ".xml":        "xml",
    ".toml":       "toml",
    ".ts":         "typescript",
    ".js":         "javascript",
    ".go":         "go",
    ".rs":         "rust",
}

def language_for(path: str) -> str:
    from pathlib import Path
    return LANGUAGE_MAP.get(Path(path).suffix.lower(), "other")
