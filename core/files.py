"""
Tiny filesystem helpers shared by the agents.

Every agent used to carry its own copy of these two functions — identical
byte for byte in nine of them — which is exactly the kind of duplication
that drifts: one agent "fixes" a helper and the other eight keep the old
behaviour. They live here once now.
"""
from pathlib import Path


def ensure_file(path: Path) -> Path:
    """Ensure file exists with parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def file_has_content(path: Path) -> bool:
    """Check if file exists and has meaningful content."""
    return path.exists() and path.stat().st_size > 0
