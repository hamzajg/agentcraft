"""
openspec_archive.py — archive a completed OpenSpec change.

What archiving does:
  1. Verifies the change is complete (all task checkboxes checked)
  2. Merges delta specs into openspec/specs/<domain>/spec.md
  3. Moves the change folder to openspec/changes/archive/YYYY-MM-DD-<name>/

Usage:
  python ai-team/rag/openspec_archive.py add-dark-mode
  python ai-team/rag/openspec_archive.py add-dark-mode --dry-run
  python ai-team/rag/openspec_archive.py --list      # show archivable changes
"""

import argparse
import re
import shutil
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
    REPO_ROOT = Path(__file__).parent.parent
    ws_file   = REPO_ROOT / "workspace.yaml"
    ws        = yaml.safe_load(ws_file.read_text()) if ws_file.exists() else {}
except Exception:
    ws = {}

OUTPUT_DIR    = REPO_ROOT / ws.get("paths", {}).get("output", ".")
OPENSPEC_ROOT = OUTPUT_DIR / "openspec"
SPECS_DIR     = OPENSPEC_ROOT / "specs"
CHANGES_DIR   = OPENSPEC_ROOT / "changes"
ARCHIVE_DIR   = CHANGES_DIR  / "archive"


# ── Completeness check ────────────────────────────────────────────────────────

def check_complete(change_dir: Path) -> tuple[bool, list[str]]:
    issues = []
    for required in ("proposal.md", "design.md", "tasks.md"):
        if not (change_dir / required).exists():
            issues.append(f"Missing {required}")

    tasks_file = change_dir / "tasks.md"
    if tasks_file.exists():
        text  = tasks_file.read_text()
        open_ = re.findall(r"^- \[ \]", text, re.MULTILINE)
        if open_:
            issues.append(f"{len(open_)} unchecked task(s) in tasks.md")

    return (len(issues) == 0), issues


# ── Delta spec merge ──────────────────────────────────────────────────────────

def merge_delta(delta_spec: Path, target_spec: Path):
    """
    Merge a delta spec into the domain's source-of-truth spec.

    Markers: ## ADDED Requirements, ## MODIFIED Requirements, ## REMOVED Requirements
    - ADDED sections are appended
    - MODIFIED sections replace the matching requirement text
    - REMOVED sections delete the matching requirement
    """
    delta = delta_spec.read_text()
    target_text = target_spec.read_text() if target_spec.exists() else ""

    added   = _extract_section(delta, "ADDED")
    modified = _extract_section(delta, "MODIFIED")
    removed  = _extract_section(delta, "REMOVED")

    # Apply REMOVED — delete requirement blocks from target
    for req_name in _requirement_names(removed):
        target_text = _remove_requirement(target_text, req_name)

    # Apply MODIFIED — replace requirement blocks
    for req_block in _requirement_blocks(modified):
        req_name = _first_requirement_name(req_block)
        if req_name:
            target_text = _remove_requirement(target_text, req_name)
            target_text = target_text.rstrip() + "\n\n" + req_block.strip() + "\n"

    # Apply ADDED — append
    if added.strip():
        target_text = target_text.rstrip() + "\n\n" + added.strip() + "\n"

    target_spec.parent.mkdir(parents=True, exist_ok=True)
    target_spec.write_text(target_text)


def _extract_section(text: str, marker: str) -> str:
    pattern = rf"## {marker} Requirements(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _requirement_names(text: str) -> list[str]:
    return re.findall(r"### Requirement: (.+)", text)


def _requirement_blocks(text: str) -> list[str]:
    parts = re.split(r"(?=### Requirement:)", text)
    return [p.strip() for p in parts if p.strip().startswith("### Requirement:")]


def _first_requirement_name(block: str) -> str:
    m = re.search(r"### Requirement: (.+)", block)
    return m.group(1).strip() if m else ""


def _remove_requirement(text: str, req_name: str) -> str:
    pattern = rf"### Requirement: {re.escape(req_name)}.*?(?=\n### Requirement:|\n## |\Z)"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip() + "\n"


# ── Archive ───────────────────────────────────────────────────────────────────

def archive_change(change_name: str, dry_run: bool = False) -> bool:
    change_dir = CHANGES_DIR / change_name
    if not change_dir.exists():
        print(f"Change not found: {change_dir}")
        return False

    ok, issues = check_complete(change_dir)
    if not ok:
        print(f"Change '{change_name}' is not ready to archive:")
        for issue in issues:
            print(f"  ✗ {issue}")
        return False

    # Find delta specs
    delta_specs_root = change_dir / "specs"
    delta_specs = list(delta_specs_root.rglob("spec.md")) if delta_specs_root.exists() else []

    print(f"Archiving: {change_name}")

    # Merge each delta spec
    for delta in delta_specs:
        domain = delta.parent.name
        target = SPECS_DIR / domain / "spec.md"
        print(f"  Merging delta specs/{domain}/spec.md → specs/{domain}/spec.md")
        if not dry_run:
            merge_delta(delta, target)

    # Move change folder to archive
    today      = date.today().strftime("%Y-%m-%d")
    archive_to = ARCHIVE_DIR / f"{today}-{change_name}"
    print(f"  Moving → changes/archive/{today}-{change_name}/")
    if not dry_run:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(change_dir), str(archive_to))

    if dry_run:
        print("  [dry-run] no files changed")
    else:
        print(f"✓ Archived. Specs updated. Change moved to archive.")
    return True


def list_changes():
    if not CHANGES_DIR.exists():
        print("No openspec/changes/ directory found.")
        return
    changes = [d for d in CHANGES_DIR.iterdir()
               if d.is_dir() and d.name != "archive"]
    if not changes:
        print("No active changes.")
        return
    print("Active changes:")
    for ch in sorted(changes):
        ok, issues = check_complete(ch)
        status = "✓ ready" if ok else f"✗ {issues[0]}"
        print(f"  {ch.name:<40} {status}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Archive an OpenSpec change")
    parser.add_argument("change", nargs="?", help="Change name to archive")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list",    action="store_true", help="List archivable changes")
    args = parser.parse_args()

    if args.list or not args.change:
        list_changes()
        return

    success = archive_change(args.change, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
