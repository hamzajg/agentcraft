"""
cli.py — live terminal system monitor for the agent team.

Usage:
    python ai-team/monitor/cli.py
    python ai-team/monitor/cli.py --interval 2
    python ai-team/monitor/cli.py --once          # single snapshot, then exit

Shows: CPU · RAM · GPU · VRAM gauges + live agent statuses from comms server.
Updates in-place using ANSI escape codes — no curses dependency.
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from collector import collect, SystemMetrics

# ANSI codes
CLEAR_SCREEN  = "\033[2J\033[H"
CLEAR_LINE    = "\033[2K"
CURSOR_HOME   = "\033[H"
CURSOR_HIDE   = "\033[?25l"
CURSOR_SHOW   = "\033[?25h"
BOLD          = "\033[1m"
DIM           = "\033[2m"
RESET         = "\033[0m"

# Colors
C_TEAL   = "\033[38;5;78m"
C_AMBER  = "\033[38;5;214m"
C_PURPLE = "\033[38;5;141m"
C_RED    = "\033[38;5;196m"
C_GRAY   = "\033[38;5;245m"
C_WHITE  = "\033[97m"
C_GREEN  = "\033[38;5;82m"

_running = True


def _bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    color  = C_RED if pct > 85 else (C_AMBER if pct > 60 else C_TEAL)
    bar    = "█" * filled + "░" * (width - filled)
    return f"{color}{bar}{RESET}"


def _agent_color(status: str) -> str:
    return {
        "blocked": C_AMBER,
        "running": C_TEAL,
        "idle":    C_GRAY,
        "complete": C_GREEN,
    }.get(status, C_GRAY)


def _agent_dot(status: str) -> str:
    return {
        "blocked": f"{C_AMBER}●{RESET}",
        "running": f"{C_TEAL}●{RESET}",
        "idle":    f"{C_GRAY}○{RESET}",
        "complete": f"{C_GREEN}✓{RESET}",
    }.get(status, f"{C_GRAY}○{RESET}")


def _fetch_agents() -> dict:
    """Fetch agent statuses from comms server (non-blocking)."""
    try:
        import urllib.request, json
        with urllib.request.urlopen("http://localhost:7000/api/channels", timeout=1) as r:
            channels = json.loads(r.read())
        with urllib.request.urlopen("http://localhost:7000/api/stats", timeout=1) as r:
            stats = json.loads(r.read())
        statuses = {}
        for ch in channels:
            statuses[ch["agent_id"]] = {
                "label":  ch.get("agent_label", ch["agent_id"]),
                "status": "blocked" if ch["agent_id"] in stats.get("pending_agents", [])
                          else "idle",
                "unread": ch.get("unread", 0),
            }
        return statuses
    except Exception:
        return {}


def render(metrics: SystemMetrics, agents: dict, interval: float):
    lines = []

    w = 62
    lines.append(f"{BOLD}{C_WHITE}  Agent System Monitor{RESET}"
                 + f"  {DIM}{C_GRAY}↻ {interval}s  q quit{RESET}")
    lines.append(f"{C_GRAY}  {'─' * w}{RESET}")

    # CPU
    lines.append(
        f"  {C_WHITE}CPU{RESET}  {_bar(metrics.cpu_pct)}  "
        f"{metrics.cpu_pct:5.1f}%  {DIM}{metrics.cpu_cores} cores{RESET}"
    )

    # RAM
    lines.append(
        f"  {C_WHITE}RAM{RESET}  {_bar(metrics.ram_pct)}  "
        f"{metrics.ram_pct:5.1f}%  "
        f"{DIM}{metrics.ram_used_gb:.1f}/{metrics.ram_total_gb:.0f} GB{RESET}"
    )

    # GPU rows
    if metrics.gpus:
        for g in metrics.gpus:
            name = g["name"][:24]
            lines.append(
                f"  {C_PURPLE}GPU{RESET}  {_bar(g['utilization'])}  "
                f"{g['utilization']:5.1f}%  {DIM}{name}{RESET}"
            )
            lines.append(
                f"  {C_PURPLE}VRM{RESET}  {_bar(g['vram_pct'])}  "
                f"{g['vram_pct']:5.1f}%  "
                f"{DIM}{g['vram_used_gb']:.1f}/{g['vram_total_gb']:.0f} GB{RESET}"
            )
    else:
        lines.append(f"  {C_GRAY}GPU  — no GPU detected{RESET}")

    # Ollama
    if metrics.ollama_pid:
        lines.append(
            f"  {C_GRAY}OLL  pid {metrics.ollama_pid}  "
            f"cpu {metrics.ollama_cpu:.1f}%  "
            f"ram {metrics.ollama_ram_gb:.1f} GB{RESET}"
        )

    lines.append(f"{C_GRAY}  {'─' * w}{RESET}")

    # Agent statuses
    if agents:
        lines.append(f"  {BOLD}Agents{RESET}")
        for aid, info in agents.items():
            dot    = _agent_dot(info["status"])
            label  = info["label"][:18].ljust(18)
            status = info["status"].ljust(8)
            color  = _agent_color(info["status"])
            unread = f"  {C_AMBER}[{info['unread']} waiting]{RESET}" if info["unread"] else ""
            lines.append(f"  {dot} {color}{label}{RESET}  {DIM}{status}{RESET}{unread}")
    else:
        lines.append(f"  {DIM}No agents — start comms server on :7000{RESET}")

    lines.append("")
    return "\n".join(lines)


def run(interval: float = 2.0, once: bool = False):
    global _running

    def _exit(*_):
        global _running
        _running = False

    signal.signal(signal.SIGINT,  _exit)
    signal.signal(signal.SIGTERM, _exit)

    print(CURSOR_HIDE, end="", flush=True)
    print(CLEAR_SCREEN, end="", flush=True)

    try:
        while _running:
            m      = collect()
            agents = _fetch_agents()
            frame  = render(m, agents, interval)

            print(CURSOR_HOME, end="")
            print(frame, end="", flush=True)

            if once:
                break
            time.sleep(interval)
    finally:
        print(CURSOR_SHOW, end="", flush=True)
        print()


def main():
    parser = argparse.ArgumentParser(description="Live system monitor for agent team")
    parser.add_argument("--interval", type=float, default=2.0, help="Refresh interval (s)")
    parser.add_argument("--once",     action="store_true",     help="Single snapshot and exit")
    args = parser.parse_args()
    run(interval=args.interval, once=args.once)


if __name__ == "__main__":
    main()
