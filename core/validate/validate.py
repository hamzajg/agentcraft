#!/usr/bin/env python3
"""
validate.py — enforces the human/agent ownership boundary.

Runs in two modes:
  python validate.py              — full repo scan (CI)
  python validate.py --staged     — staged files only (pre-commit hook)

Exit codes:
  0 — clean
  1 — violations found (blocks commit or fails CI)

Rules (from workspace.yaml enforcement section):
  - Files matching forbidden_in_human_paths patterns must not exist
    under human_paths directories
  - agent-owned dirs are written by agents to repo root

Also validates:
  - workspace.yaml is valid YAML and has required fields
  - docs/ contains at least one .md file
  - agents/prompts/ contains a prompt for every agent_configs/ entry
"""

import argparse
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent.parent
WORKSPACE = REPO_ROOT / "workspace.yaml"


def _find_workspace_root() -> Path:
    """Walk up from CWD looking for workspace.yaml."""
    cur = Path.cwd()
    for d in [cur] + list(cur.parents):
        if (d / "workspace.yaml").exists():
            return d
            
    # Try finding inside subdirectories depth 1
    sub_ws = list(cur.glob("*/workspace.yaml"))
    if len(sub_ws) == 1:
        return sub_ws[0].parent
        
    return REPO_ROOT  # fallback to installation dir


# ── Violation collector ────────────────────────────────────────────────────────


class Report:
    def __init__(self):
        self.violations: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str):
        self.violations.append(f"  ERROR  {msg}")

    def warn(self, msg: str):
        self.warnings.append(f"  WARN   {msg}")

    def ok(self):
        return len(self.violations) == 0

    def print_summary(self):
        if self.violations:
            print("\n── Violations (must fix) ────────────────────────────────────")
            for v in self.violations:
                print(v)
        if self.warnings:
            print("\n── Warnings (should fix) ────────────────────────────────────")
            for w in self.warnings:
                print(w)
        if self.ok():
            print("✓  All ownership checks passed")
        else:
            print(f"\n✗  {len(self.violations)} violation(s) found")


# ── Main checks ────────────────────────────────────────────────────────────────


def load_workspace(report: Report) -> Optional[dict]:
    if not WORKSPACE.exists():
        report.error(f"workspace.yaml not found at {WORKSPACE}")
        return None
    try:
        with WORKSPACE.open() as f:
            ws = yaml.safe_load(f)
    except yaml.YAMLError as e:
        report.error(f"workspace.yaml is invalid YAML: {e}")
        return None
    for field in ["project", "paths", "enforcement"]:
        if field not in ws:
            report.error(f"workspace.yaml missing required field: {field}")
    return ws


def check_human_paths_clean(
    ws: dict, report: Report, staged_files: Optional[list] = None
):
    """
    Ensure no agent-generated file patterns exist under human-authored paths.
    """
    enforcement = ws.get("enforcement", {})
    forbidden = enforcement.get("forbidden_in_human_paths", [])
    human_paths = [REPO_ROOT / p for p in enforcement.get("human_paths", [])]

    files_to_check = []
    if staged_files is not None:
        files_to_check = [Path(f) for f in staged_files]
    else:
        for hp in human_paths:
            if hp.exists():
                files_to_check += [f for f in hp.rglob("*") if f.is_file()]

    for f in files_to_check:
        # Only check files under human_paths
        is_human = any(str(f).startswith(str(hp)) for hp in human_paths)
        if not is_human:
            continue
        rel = f.relative_to(REPO_ROOT)

        # Check if this is in a 3rd party directory (should be warning, not error)
        is_third_party = any(
            part in str(rel).split("/")
            for part in ["node_modules", "vendor", "third_party", "deps", ".git"]
        )

        for pattern in forbidden:
            if fnmatch(str(rel), pattern) or fnmatch(f.name, pattern.lstrip("**/")):
                if is_third_party:
                    report.warn(
                        f"Agent-generated file in 3rd party directory: {rel}\n"
                        f"         Matches forbidden pattern: {pattern}\n"
                        f"         This is allowed in 3rd party libs but should be reviewed."
                    )
                else:
                    report.error(
                        f"Agent-generated file in human-authored path: {rel}\n"
                        f"         Matches forbidden pattern: {pattern}\n"
                        f"         Agents write this file — commit it or delete it."
                    )


def check_output_not_committed(report: Report):
    """
    Warn if agent-owned dirs have uncommitted tracked files.
    """
    # Agents write to repo root — check specific agent-owned dirs
    agent_dirs = ["api-gateway", "openspec", "cli"]
    if not any((REPO_ROOT / d).exists() for d in agent_dirs):
        return
    try:
        result = subprocess.run(
            ["git", "ls-files"] + agent_dirs,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        tracked = [line for line in result.stdout.splitlines() if line.strip()]
        if tracked:
            report.warn(
                f"Agent dirs have {len(tracked)} git-tracked file(s). "
                f"These should only be committed after human review.\n"
                f"         Files: {', '.join(tracked[:3])}"
                + (f" (and {len(tracked) - 3} more)" if len(tracked) > 3 else "")
            )
    except FileNotFoundError:
        pass  # git not available


def check_docs_present(ws: dict, report: Report):
    docs_dir = REPO_ROOT / ws.get("paths", {}).get("docs", "docs")
    if not docs_dir.exists():
        report.error(f"docs/ directory not found at {docs_dir}")
        return
    md_files = list(docs_dir.glob("*.md"))
    if not md_files:
        report.warn(f"docs/ is empty — add at least one .md file")
    else:
        required = ["blueprint.md", "topdown.md", "mvp.md"]
        for r in required:
            if not (docs_dir / r).exists():
                report.warn(f"docs/{r} not found — recommended for architect agent")


def check_agent_configs_have_prompts(report: Report):
    configs_dir = REPO_ROOT / "agents" / "agent_configs"
    prompts_dir = REPO_ROOT / "agents" / "prompts"
    if not configs_dir.exists():
        return
    for cfg in configs_dir.glob("*.yaml"):
        prompt = prompts_dir / f"{cfg.stem}.md"
        if not prompt.exists():
            report.warn(
                f"agent_configs/{cfg.name} has no matching prompt: "
                f"prompts/{cfg.stem}.md"
            )


def check_workspace_yaml_present(report: Report):
    if not WORKSPACE.exists():
        report.error(
            "workspace.yaml not found. This file configures the agent team "
            "for this project. See agents/validate/workspace.yaml.example"
        )


def get_staged_files() -> list[str]:
    try:
        git_root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
        )
        if git_root:
            return [str(Path(git_root) / f) for f in result.stdout.splitlines()]
        return result.stdout.splitlines()
    except Exception:
        return []


# ── Entry point ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Validate agent/human ownership boundary"
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check staged files only (pre-commit mode)",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    # Detect workspace root
    ws_root = _find_workspace_root()
    global REPO_ROOT, WORKSPACE
    REPO_ROOT = ws_root
    WORKSPACE = ws_root / "workspace.yaml"

    report = Report()
    staged = get_staged_files() if args.staged else None

    if not args.quiet:
        mode = "staged files" if args.staged else "full repo"
        print(f"Validating {mode} at {REPO_ROOT}")

    check_workspace_yaml_present(report)
    ws = load_workspace(report)
    if ws:
        check_human_paths_clean(ws, report, staged_files=staged)
        check_docs_present(ws, report)
        check_output_not_committed(report)
    check_agent_configs_have_prompts(report)

    report.print_summary()
    sys.exit(0 if report.ok() else 1)


if __name__ == "__main__":
    main()
