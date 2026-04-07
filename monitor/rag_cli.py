"""
rag_cli.py — RAG repository CLI tool.

Commands:
  status    — show index stats: chunks, files, lines per collection
  search    — semantic search against the index
  files     — list indexed files with chunk counts
  reindex   — re-run full indexing from workspace sources
  purge     — delete the entire store (with confirmation)

Usage:
  python ai-team/monitor/rag_cli.py status
  python ai-team/monitor/rag_cli.py search "message bus reactive"
  python ai-team/monitor/rag_cli.py search "agent supervisor" --collection codebase
  python ai-team/monitor/rag_cli.py files --sort size --limit 20
  python ai-team/monitor/rag_cli.py files --language java
  python ai-team/monitor/rag_cli.py reindex
  python ai-team/monitor/rag_cli.py purge
"""

import argparse
import sys
from pathlib import Path

# Resolve repo root and add ai-team to path
SCRIPT_DIR = Path(__file__).parent
AI_TEAM    = SCRIPT_DIR.parent
REPO_ROOT  = AI_TEAM.parent
sys.path.insert(0, str(AI_TEAM))

BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"
TEAL   = "\033[38;5;78m"
PURPLE = "\033[38;5;141m"
AMBER  = "\033[38;5;214m"
RED    = "\033[38;5;196m"
WHITE  = "\033[97m"
GRAY   = "\033[38;5;245m"

COLL_COLORS = {
    "docs":     TEAL,
    "codebase": PURPLE,
    "legacy":   AMBER,
}

LANG_COLORS = {
    "java":     "\033[38;5;214m",
    "python":   "\033[38;5;75m",
    "markdown": "\033[38;5;78m",
    "yaml":     "\033[38;5;141m",
    "json":     "\033[38;5;220m",
    "shell":    "\033[38;5;208m",
}


def _store_path() -> Path:
    try:
        import yaml
        ws = yaml.safe_load((REPO_ROOT / "workspace.yaml").read_text())
        base = ws.get("paths", {}).get("output", ".")
        sub  = ws.get("rag", {}).get("store_path", ".rag")
        return REPO_ROOT / base / sub
    except Exception:
        return REPO_ROOT / ".rag"


def _bar(pct: float, w: int = 16) -> str:
    filled = int(pct / 100 * w)
    color  = RED if pct > 85 else (AMBER if pct > 60 else TEAL)
    return f"{color}{'█' * filled}{'░' * (w - filled)}{RESET}"


def _coll_color(name: str) -> str:
    return COLL_COLORS.get(name, GRAY)


def _lang_color(lang: str) -> str:
    return LANG_COLORS.get(lang, GRAY)


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(args):
    from rag.stats import compute
    store = _store_path()
    print(f"\n{BOLD}RAG Repository{RESET}  {DIM}{store}{RESET}\n")

    stats = compute(store)
    if stats is None:
        print(f"  {AMBER}Store not found.{RESET}")
        print(f"  Enable RAG in workspace.yaml (rag.enabled: true) and run: make build\n")
        return

    # Summary row
    print(f"  {BOLD}{stats.total_chunks:,}{RESET} chunks  "
          f"{BOLD}{stats.total_files:,}{RESET} files  "
          f"{BOLD}{stats.total_lines:,}{RESET} lines  "
          f"{DIM}{stats.store_size_mb:.1f} MB{RESET}")
    print()

    # Collections table
    w = 52
    print(f"  {BOLD}{'Collection':<14}{'Chunks':>8}{'Files':>8}{'Lines':>8}  {'Distribution':<20}{RESET}")
    print(f"  {'─' * w}")
    for c in stats.collections:
        cc = _coll_color(c['name'])
        print(
            f"  {cc}{c['name']:<14}{RESET}"
            f"{c['chunk_count']:>8,}"
            f"{c['file_count']:>8,}"
            f"{c['line_estimate']:>8,}"
            f"  {_bar(c['pct_of_total'])} {c['pct_of_total']:.0f}%"
        )
    print()

    # Language distribution
    if stats.language_dist:
        total = sum(stats.language_dist.values())
        print(f"  {BOLD}Languages{RESET}")
        for lang, count in sorted(stats.language_dist.items(),
                                   key=lambda x: x[1], reverse=True)[:8]:
            pct = count / total * 100
            lc  = _lang_color(lang)
            print(f"  {lc}{lang:<14}{RESET} {count:>6,}  {_bar(pct, 12)} {pct:.0f}%")
        print()

    # Health
    if not stats.healthy:
        for issue in stats.issues:
            print(f"  {AMBER}⚠  {issue}{RESET}")
        print()
    else:
        print(f"  {TEAL}✓  Index healthy{RESET}\n")


# ── search ────────────────────────────────────────────────────────────────────

def cmd_search(args):
    from rag.stats import search
    store  = _store_path()
    query  = args.query
    top_k  = args.limit
    coll   = args.collection

    print(f"\n{BOLD}Searching:{RESET} {query}")
    if coll:
        print(f"{DIM}Collection: {coll}{RESET}")
    print()

    results = search(store, query, top_k=top_k, collection=coll)
    if not results:
        print(f"  {GRAY}No results — is Ollama running? Is the index populated?{RESET}\n")
        return

    for i, r in enumerate(results):
        score   = r["score"]
        sc_color = TEAL if score > 0.85 else (PURPLE if score > 0.7 else GRAY)
        cc       = _coll_color(r["collection"])
        lc       = _lang_color(r["language"])
        fname    = Path(r["source_path"]).name

        print(f"  {sc_color}{score:.3f}{RESET}  "
              f"{BOLD}{fname}{RESET}:{r['chunk_index']}  "
              f"{cc}[{r['collection']}]{RESET}  "
              f"{lc}{r['language']}{RESET}")

        if args.show_text and r.get("text"):
            preview = r["text"][:160].replace("\n", " ")
            print(f"        {DIM}{preview}…{RESET}")
    print()


# ── files ─────────────────────────────────────────────────────────────────────

def cmd_files(args):
    from rag.stats import compute
    store = _store_path()
    stats = compute(store)
    if not stats:
        print(f"  {AMBER}Store not found or empty.{RESET}\n")
        return

    files = stats.files
    if args.language:
        files = [f for f in files if f["language"] == args.language]
    if args.collection:
        files = [f for f in files if f["collection"] == args.collection]
    if args.sort == "name":
        files = sorted(files, key=lambda f: Path(f["source_path"]).name)
    # Default sort is already by chunk_count desc from stats.py

    files = files[:args.limit]

    print(f"\n{BOLD}Indexed Files{RESET}  "
          f"{DIM}({len(files)} shown  "
          f"{'lang='+args.language if args.language else ''}  "
          f"{'coll='+args.collection if args.collection else ''}){RESET}\n")

    print(f"  {BOLD}{'File':<40}{'Collection':<12}{'Lang':<10}{'Chunks':>7}{'Lines':>7}{RESET}")
    print(f"  {'─' * 78}")

    for f in files:
        fname = Path(f["source_path"]).name[:38]
        cc    = _coll_color(f["collection"])
        lc    = _lang_color(f["language"])
        print(
            f"  {fname:<40}"
            f"{cc}{f['collection']:<12}{RESET}"
            f"{lc}{f['language']:<10}{RESET}"
            f"{f['chunk_count']:>7,}"
            f"{f['line_estimate']:>7,}"
        )
    print()


# ── reindex ───────────────────────────────────────────────────────────────────

def cmd_reindex(args):
    try:
        import yaml
        ws = yaml.safe_load((REPO_ROOT / "workspace.yaml").read_text())
    except Exception:
        print(f"{AMBER}workspace.yaml not found{RESET}")
        return

    rag_cfg = ws.get("rag", {})
    if not rag_cfg.get("enabled"):
        print(f"{AMBER}RAG is disabled in workspace.yaml. Set rag.enabled: true first.{RESET}")
        return

    from rag import RagClient
    store  = _store_path()
    client = RagClient(store_path=store,
                       embed_model=rag_cfg.get("embed_model", "nomic-embed-text"))

    if not client.setup():
        print(f"{RED}Failed to open RAG store{RESET}")
        return

    docs_path = REPO_ROOT / ws.get("paths", {}).get("docs", "docs")
    out_path  = REPO_ROOT / ws.get("paths", {}).get("output", ".")

    print(f"\n{BOLD}Re-indexing…{RESET}\n")

    n = client.ingest_directory(docs_path, "docs", force=True)
    print(f"  {TEAL}docs{RESET}     {n:,} chunks")

    if out_path.exists():
        n = client.ingest_directory(out_path, "codebase", force=True)
        print(f"  {PURPLE}codebase{RESET} {n:,} chunks")

    legacy_dirs = rag_cfg.get("legacy_source_dirs", [])
    for d in legacy_dirs:
        p = REPO_ROOT / d
        if p.exists():
            n = client.ingest_directory(p, "legacy", force=True)
            print(f"  {AMBER}legacy{RESET}   {n:,} chunks  ({d})")

    client.close()
    print(f"\n{TEAL}✓ Reindex complete{RESET}\n")


# ── purge ─────────────────────────────────────────────────────────────────────

def cmd_purge(args):
    import shutil
    store = _store_path()
    if not store.exists():
        print("Store not found.")
        return
    answer = input(f"Delete entire RAG store at {store}? [y/N] ").strip().lower()
    if answer == "y":
        shutil.rmtree(store)
        print(f"{TEAL}Store deleted.{RESET}")
    else:
        print("Cancelled.")


# ── router ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAG repository CLI")
    sub    = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Show index stats")

    sp = sub.add_parser("search", help="Semantic search")
    sp.add_argument("query")
    sp.add_argument("--collection", "-c", default=None)
    sp.add_argument("--limit",      "-n", type=int, default=10)
    sp.add_argument("--show-text",  action="store_true")

    fp = sub.add_parser("files", help="List indexed files")
    fp.add_argument("--language",   "-l", default=None)
    fp.add_argument("--collection", "-c", default=None)
    fp.add_argument("--sort",       "-s", choices=["size", "name"], default="size")
    fp.add_argument("--limit",      "-n", type=int, default=50)

    sub.add_parser("reindex", help="Re-run full indexing")
    sub.add_parser("purge",   help="Delete the entire store")

    args = parser.parse_args()

    dispatch = {
        "status":  cmd_status,
        "search":  cmd_search,
        "files":   cmd_files,
        "reindex": cmd_reindex,
        "purge":   cmd_purge,
    }

    fn = dispatch.get(args.cmd)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
