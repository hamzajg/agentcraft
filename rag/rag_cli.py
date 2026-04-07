#!/usr/bin/env python3
"""
rag_cli.py — RAG repository inspector CLI.

Commands:
  stats              overall index health summary
  files              per-file breakdown table
  queries            recent query activity
  search <query>     test semantic search against the store
  collections        breakdown by collection (docs/codebase/legacy)
  languages          breakdown by language
  reset              clear query log
  reindex            re-index docs/ and repo root into the store

Usage:
  python rag/rag_cli.py stats
  python rag/rag_cli.py files --top 20
  python rag/rag_cli.py search "AgentMessage sealed class"
  python rag/rag_cli.py queries --limit 10
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Locate workspace.yaml
REPO_ROOT = Path(__file__).parent.parent


try:
    import yaml
    ws_file = REPO_ROOT / "workspace.yaml"
    ws      = yaml.safe_load(ws_file.read_text()) if ws_file.exists() else {}
except Exception:
    ws = {}

OUTPUT_DIR  = REPO_ROOT / ws.get("paths", {}).get("output", ".")
STORE_PATH  = OUTPUT_DIR / ".rag"
DOCS_DIR    = REPO_ROOT / ws.get("paths", {}).get("docs", "docs")

# ANSI
BOLD  = "\033[1m"
DIM   = "\033[2m"
RESET = "\033[0m"
TEAL  = "\033[38;5;78m"
AMBER = "\033[38;5;214m"
PURP  = "\033[38;5;141m"
RED   = "\033[38;5;196m"
GRAY  = "\033[38;5;245m"


def _bar(n: int, total: int, width: int = 24) -> str:
    pct    = n / total if total else 0
    filled = int(pct * width)
    return f"{TEAL}{'█' * filled}{'░' * (width - filled)}{RESET}"


def _pct(n: int, total: int) -> str:
    return f"{n / total * 100:.1f}%" if total else "0.0%"


def _stats(args):
    from rag.rag_stats import RagStats
    s   = RagStats(STORE_PATH)
    snap = s.snapshot()
    idx  = snap["index"]
    q    = snap.get("queries", {})

    w = 56
    print()
    print(f"{BOLD}  RAG Repository{RESET}   {DIM}{STORE_PATH}{RESET}")
    print(f"  {GRAY}{'─' * w}{RESET}")

    def row(label, value, note=""):
        print(f"  {label:<22}{BOLD}{value:<18}{RESET}{DIM}{note}{RESET}")

    row("Status",        idx.get("status", "unknown").upper())
    row("Store size",    f"{snap.get('store_size_mb', 0):.1f} MB")
    row("Total chunks",  f"{idx.get('total_chunks', 0):,}")
    row("Unique files",  f"{idx.get('total_files', 0):,}")
    row("Total lines",   f"{idx.get('total_lines', 0):,}")
    row("Total chars",   f"{idx.get('total_chars', 0):,}")

    print(f"  {GRAY}{'─' * w}{RESET}")

    # Collections
    cols = idx.get("collections", {})
    total = sum(cols.values())
    for col, cnt in sorted(cols.items(), key=lambda x: -x[1]):
        bar = _bar(cnt, total)
        print(f"  {col:<16}  {bar}  {cnt:>6,}  {_pct(cnt, total):>6}")

    print(f"  {GRAY}{'─' * w}{RESET}")

    # Query stats
    if q:
        row("Total queries",   f"{q.get('total_queries', 0):,}")
        row("Avg duration",    f"{q.get('avg_duration_ms', 0):.1f} ms")
        row("Avg chunks/query",f"{q.get('avg_chunks', 0):.2f}")
        row("Hit rate",        f"{q.get('hit_rate_pct', 0):.1f}%")
    print()


def _files(args):
    from rag.rag_stats import RagStats
    files = RagStats(STORE_PATH).files(limit=args.top)
    if not files:
        print("No files indexed.")
        return

    print()
    print(f"  {BOLD}{'File':<50} {'Coll':<10} {'Lang':<8} {'Chunks':>6} {'Lines':>7} {'Chars':>8}{RESET}")
    print(f"  {GRAY}{'─' * 96}{RESET}")
    for f in files:
        exists = "" if f["exists"] else f" {RED}✗{RESET}"
        name   = f["path"]
        if len(name) > 49:
            name = "…" + name[-48:]
        print(
            f"  {name:<50} {f['collection']:<10} {f['language']:<8} "
            f"{f['chunks']:>6,} {f['lines']:>7,} {f['chars']:>8,}{exists}"
        )
    print()


def _queries(args):
    from rag.rag_stats import RagStats
    data = RagStats(STORE_PATH).queries(limit=args.limit)
    recent = data.get("recent", [])
    if not recent:
        print("No queries logged yet.")
        return

    print()
    print(f"  {BOLD}Recent queries{RESET}  ({len(recent)} shown)")
    print(f"  {GRAY}{'─' * 80}{RESET}")
    for q in recent:
        ts    = time.strftime("%H:%M:%S", time.localtime(q["ts"]))
        agent = f"{TEAL}{q['agent_id']:<14}{RESET}" if q["agent_id"] else " " * 14
        hits  = q["chunks_returned"]
        color = TEAL if hits > 0 else RED
        src   = Path(q["top_source"]).name if q.get("top_source") else "—"
        print(
            f"  {GRAY}{ts}{RESET}  {agent}  "
            f"{color}{hits:>2} chunks{RESET}  "
            f"{q['query_text'][:40]:<40}  {DIM}→ {src}{RESET}"
        )

    print()
    by_agent = data.get("by_agent", [])
    if by_agent:
        print(f"  {BOLD}Queries per agent{RESET}")
        for a in by_agent:
            print(
                f"  {TEAL}{a['agent_id']:<16}{RESET}  "
                f"{a['queries']:>4} queries  "
                f"avg {a['avg_chunks']:.1f} chunks  "
                f"avg {a['avg_ms']:.0f} ms"
            )
    print()


def _collections(args):
    from rag.rag_stats import RagStats
    idx = RagStats(STORE_PATH).snapshot()["index"]
    cols = idx.get("collections", {})
    total = sum(cols.values())
    print()
    print(f"  {BOLD}Collections{RESET}  ({total:,} total chunks)")
    print(f"  {GRAY}{'─' * 50}{RESET}")
    for col, cnt in sorted(cols.items(), key=lambda x: -x[1]):
        print(f"  {col:<16}  {_bar(cnt, total)}  {cnt:>6,}  {_pct(cnt, total):>6}")
    print()


def _languages(args):
    from rag.rag_stats import RagStats
    idx   = RagStats(STORE_PATH).snapshot()["index"]
    langs = idx.get("languages", {})
    total = sum(langs.values())
    print()
    print(f"  {BOLD}Languages{RESET}  ({total:,} total chunks)")
    print(f"  {GRAY}{'─' * 50}{RESET}")
    for lang, cnt in sorted(langs.items(), key=lambda x: -x[1]):
        print(f"  {lang:<12}  {_bar(cnt, total)}  {cnt:>6,}  {_pct(cnt, total):>6}")
    print()


def _search(args):
    from rag.rag_client import RagClient
    print(f"\n  Searching: {BOLD}{args.query}{RESET}")
    client = RagClient(store_path=STORE_PATH)
    if not client.setup():
        print("  RAG store not available.")
        return
    t0    = time.time()
    paths = client.retrieve(args.query, top_k=args.top_k)
    ms    = (time.time() - t0) * 1000
    print(f"  {len(paths)} chunks in {ms:.0f} ms\n")
    for i, p in enumerate(paths, 1):
        content = p.read_text()[:200].strip()
        src_line = ""
        for line in content.splitlines():
            if "RAG context from:" in line:
                src_line = line.replace("<!-- RAG context from:", "").replace("-->", "").strip()
                break
        print(f"  {TEAL}[{i}]{RESET} {DIM}{src_line}{RESET}")
        print(f"      {content.replace(src_line, '').strip()[:120]}")
        print()
    client.close()


def _reset(args):
    from rag.rag_stats import RagStats
    RagStats(STORE_PATH).clear_queries()
    print("Query log cleared.")


def _reindex(args):
    from rag.rag_client import RagClient
    client = RagClient(store_path=STORE_PATH)
    if not client.setup():
        print("RAG store could not be opened.")
        return
    print(f"Re-indexing docs/  →  {DOCS_DIR}")
    n = client.ingest_directory(DOCS_DIR, "docs", force=args.force)
    print(f"  {n} chunks indexed from docs/")
    if OUTPUT_DIR.exists():
        print(f"Re-indexing repo root  →  {OUTPUT_DIR}")
        n = client.ingest_directory(OUTPUT_DIR, "codebase", force=args.force)
        print(f"  {n} chunks indexed from repo root")
    client.close()
    print("Done.")


def main():
    parser  = argparse.ArgumentParser(description="RAG repository inspector")
    subs    = parser.add_subparsers(dest="cmd")

    subs.add_parser("stats", help="Index health summary")

    p_files = subs.add_parser("files", help="Per-file breakdown")
    p_files.add_argument("--top", type=int, default=50)

    p_q = subs.add_parser("queries", help="Query activity log")
    p_q.add_argument("--limit", type=int, default=20)

    subs.add_parser("collections", help="Breakdown by collection")
    subs.add_parser("languages",   help="Breakdown by language")

    p_s = subs.add_parser("search", help="Test semantic search")
    p_s.add_argument("query")
    p_s.add_argument("--top-k", type=int, default=5)

    subs.add_parser("reset", help="Clear query log")

    p_ri = subs.add_parser("reindex", help="Re-index docs/ and repo root")
    p_ri.add_argument("--force", action="store_true", help="Re-index all files, skip hash check")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    dispatch = {
        "stats":       _stats,
        "files":       _files,
        "queries":     _queries,
        "collections": _collections,
        "languages":   _languages,
        "search":      _search,
        "reset":       _reset,
        "reindex":     _reindex,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
