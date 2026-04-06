"""
chunker.py — language-aware text chunker.

Strategy per language:
  Markdown   — split on ## headings; fall back to paragraph splits
  Java       — split on class/method boundaries (top-level { blocks })
  Python     — split on def/class boundaries
  YAML/JSON  — split on top-level keys / array items
  Other      — fixed-size overlapping windows

Each chunk is bounded: MIN_TOKENS ≤ len ≤ MAX_TOKENS (approx, by character count).
Overlap ensures context isn't lost at boundaries.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Approximate character counts (nomic-embed-text context: 8192 tokens ≈ 32 000 chars)
# Keep chunks smaller so retrieval is precise, not broad
CHUNK_MAX_CHARS  = 1500
CHUNK_MIN_CHARS  = 80
CHUNK_OVERLAP    = 150   # chars repeated between adjacent chunks


@dataclass
class Chunk:
    text:        str
    chunk_index: int
    language:    str


def chunk_file(path: Path) -> list[Chunk]:
    """Chunk a file into semantically coherent pieces."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    if not text.strip():
        return []

    suffix = path.suffix.lower()
    if suffix == ".md":
        pieces = _chunk_markdown(text)
    elif suffix == ".java":
        pieces = _chunk_java(text)
    elif suffix == ".py":
        pieces = _chunk_python(text)
    elif suffix in (".yaml", ".yml"):
        pieces = _chunk_yaml(text)
    elif suffix == ".json":
        pieces = _chunk_fixed(text)   # JSON structure varies too much
    else:
        pieces = _chunk_fixed(text)

    from rag.schema import language_for
    lang = language_for(str(path))
    return [
        Chunk(text=p.strip(), chunk_index=i, language=lang)
        for i, p in enumerate(pieces)
        if len(p.strip()) >= CHUNK_MIN_CHARS
    ]


# ── Markdown ──────────────────────────────────────────────────────────────────

def _chunk_markdown(text: str) -> list[str]:
    """Split on ## headings, keeping heading with its content."""
    sections = re.split(r"(?m)^(#{1,3} .+)$", text)
    chunks: list[str] = []
    current = ""
    for part in sections:
        if re.match(r"^#{1,3} ", part):
            if current.strip():
                chunks.extend(_split_oversized(current))
            current = part + "\n"
        else:
            current += part
    if current.strip():
        chunks.extend(_split_oversized(current))
    return chunks or _chunk_fixed(text)


# ── Java ──────────────────────────────────────────────────────────────────────

def _chunk_java(text: str) -> list[str]:
    """Split on class/interface/enum/method declarations."""
    # Find top-level declarations
    pattern = re.compile(
        r"(?:^|\n)"
        r"(?:(?:public|private|protected|static|final|abstract|sealed)\s+)*"
        r"(?:class|interface|enum|record)\s+\w+",
        re.MULTILINE,
    )
    return _split_on_pattern(text, pattern) or _chunk_fixed(text)


# ── Python ────────────────────────────────────────────────────────────────────

def _chunk_python(text: str) -> list[str]:
    """Split on def/class at module level (not indented)."""
    pattern = re.compile(r"(?m)^(?:class |def |async def )\w+")
    return _split_on_pattern(text, pattern) or _chunk_fixed(text)


# ── YAML ──────────────────────────────────────────────────────────────────────

def _chunk_yaml(text: str) -> list[str]:
    """Split on top-level keys (no leading whitespace)."""
    pattern = re.compile(r"(?m)^\w[\w\-]*\s*:")
    return _split_on_pattern(text, pattern) or _chunk_fixed(text)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_on_pattern(text: str, pattern: re.Pattern) -> list[str]:
    """Split text at positions where pattern matches; respect size limits."""
    positions = [m.start() for m in pattern.finditer(text)]
    if not positions:
        return []
    positions.append(len(text))
    pieces: list[str] = []
    for i in range(len(positions) - 1):
        piece = text[positions[i]:positions[i + 1]]
        pieces.extend(_split_oversized(piece))
    return pieces


def _split_oversized(text: str) -> list[str]:
    """Break a chunk that exceeds CHUNK_MAX_CHARS using fixed windows."""
    if len(text) <= CHUNK_MAX_CHARS:
        return [text]
    return list(_fixed_windows(text))


def _chunk_fixed(text: str) -> list[str]:
    return list(_fixed_windows(text))


def _fixed_windows(text: str) -> Iterator[str]:
    """Overlapping fixed-size windows."""
    start = 0
    while start < len(text):
        end = min(start + CHUNK_MAX_CHARS, len(text))
        yield text[start:end]
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
