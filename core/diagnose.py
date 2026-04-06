#!/usr/bin/env python3
"""
diagnose.py — hardware diagnostic and model selection.

Detects CPU, RAM, GPU, and VRAM, scores the machine,
selects appropriate Ollama models, and writes workspace.yaml + model-profile.yaml.

Run once before your first build:
    python ai-team/diagnose.py
    python ai-team/diagnose.py --dry-run       # show selection, don't write
    python ai-team/diagnose.py --pull           # also pull models from Ollama
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Installing pyyaml...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

REPO_ROOT  = Path(__file__).parent.parent
AI_TEAM    = Path(__file__).parent

# ── Hardware tiers ────────────────────────────────────────────────────────────
# Each tier defines:
#   coding_model    — primary model for backend_dev, test_dev, config_agent
#   planning_model  — used by architect, planner, spec (can be same as coding)
#   embed_model     — embedding model for RAG
#   llm_model       — local LLM for comms suggestions and planning fallback
#   rag_enabled     — whether to enable RAG by default at this tier

TIERS = {
    "minimal": {
        "label":          "Minimal  (CPU-only / <8 GB RAM)",
        "coding_model":   "qwen2.5-coder:1.5b",
        "planning_model": "phi3:mini",
        "embed_model":    "nomic-embed-text",
        "llm_model":      "qwen2.5:1.5b",
        "rag_enabled":    False,
        "note":           "RAG disabled — not enough RAM for concurrent embedding + inference",
    },
    "standard": {
        "label":          "Standard  (8–16 GB RAM / ≤6 GB VRAM)",
        "coding_model":   "qwen2.5-coder:7b",
        "planning_model": "qwen2.5-coder:7b",
        "embed_model":    "nomic-embed-text",
        "llm_model":      "qwen2.5-coder:7b",
        "rag_enabled":    True,
    },
    "performance": {
        "label":          "Performance  (16–32 GB RAM / 8–16 GB VRAM)",
        "coding_model":   "qwen2.5-coder:14b",
        "planning_model": "qwen2.5-coder:14b",
        "embed_model":    "mxbai-embed-large",
        "llm_model":      "qwen2.5-coder:14b",
        "rag_enabled":    True,
    },
    "high-end": {
        "label":          "High-end  (32 GB+ RAM / 24 GB+ VRAM)",
        "coding_model":   "qwen2.5-coder:32b",
        "planning_model": "llama3.1:8b",
        "embed_model":    "mxbai-embed-large",
        "llm_model":      "qwen2.5-coder:32b",
        "rag_enabled":    True,
    },
}


@dataclass
class HardwareProfile:
    cpu_cores:   int
    cpu_model:   str
    ram_gb:      float
    gpu_name:    str       # "" if none
    vram_gb:     float     # 0 if none
    platform:    str
    tier:        str
    tier_label:  str


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_hardware() -> HardwareProfile:
    import multiprocessing

    cpu_cores = multiprocessing.cpu_count()
    cpu_model = _cpu_model()
    ram_gb    = _ram_gb()
    gpu_name, vram_gb = _gpu()
    plat      = platform.system()
    tier      = _select_tier(ram_gb, vram_gb)

    return HardwareProfile(
        cpu_cores=cpu_cores,
        cpu_model=cpu_model,
        ram_gb=round(ram_gb, 1),
        gpu_name=gpu_name,
        vram_gb=round(vram_gb, 1),
        platform=plat,
        tier=tier,
        tier_label=TIERS[tier]["label"],
    )


def _cpu_model() -> str:
    sys_plat = platform.system()
    try:
        if sys_plat == "Darwin":
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
            return out
        if sys_plat == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":")[1].strip()
        if sys_plat == "Windows":
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "Name"], text=True)
            lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip() != "Name"]
            return lines[0] if lines else "Unknown"
    except Exception:
        pass
    return "Unknown CPU"


def _ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    sys_plat = platform.system()
    try:
        if sys_plat == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return int(out) / (1024 ** 3)
        if sys_plat == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024 ** 2)
        if sys_plat == "Windows":
            out = subprocess.check_output(
                ["wmic", "computersystem", "get", "TotalPhysicalMemory"], text=True)
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line) / (1024 ** 3)
    except Exception:
        pass
    return 8.0  # safe default


def _gpu() -> tuple[str, float]:
    """Return (gpu_name, vram_gb). Tries nvidia-smi, then macOS Metal, then AMD."""

    # NVIDIA
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=10
            ).strip()
            if out:
                parts = out.split(",")
                name  = parts[0].strip()
                vram  = float(parts[1].strip()) / 1024  # MiB → GiB
                return name, vram
        except Exception:
            pass

    # Apple Silicon — unified memory, GPU shares RAM
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType", "-json"], text=True, timeout=10)
            data = json.loads(out)
            displays = data.get("SPDisplaysDataType", [])
            for d in displays:
                name = d.get("sppci_model", "Apple Silicon GPU")
                # Apple Silicon: GPU can access full unified memory
                # Treat available RAM as effective VRAM
                vram = _ram_gb()
                return name, vram
        except Exception:
            pass
        return "Apple Silicon GPU", _ram_gb()

    # AMD (ROCm)
    if shutil.which("rocm-smi"):
        try:
            out = subprocess.check_output(
                ["rocm-smi", "--showmeminfo", "vram", "--json"],
                text=True, timeout=10)
            data = json.loads(out)
            for card, info in data.items():
                vram = int(info.get("VRAM Total Memory (B)", 0)) / (1024 ** 3)
                return f"AMD GPU ({card})", vram
        except Exception:
            pass

    return "", 0.0  # CPU-only


def _select_tier(ram_gb: float, vram_gb: float) -> str:
    effective = max(ram_gb * 0.6, vram_gb)   # GPU is faster but RAM matters too
    if effective >= 24:
        return "high-end"
    if effective >= 10:
        return "performance"
    if effective >= 5:
        return "standard"
    return "minimal"


# ── Output ────────────────────────────────────────────────────────────────────

def print_report(hw: HardwareProfile, tier_cfg: dict):
    w = 58
    print()
    print("┌" + "─" * w + "┐")
    print("│  Hardware Diagnostic".ljust(w) + "│")
    print("├" + "─" * w + "┤")
    print(f"│  CPU   {hw.cpu_model[:44]:<44}  │")
    print(f"│  Cores {hw.cpu_cores:<5}  RAM  {hw.ram_gb:.1f} GB".ljust(w + 1) + "│")
    if hw.gpu_name:
        print(f"│  GPU   {hw.gpu_name[:44]:<44}  │")
        print(f"│  VRAM  {hw.vram_gb:.1f} GB".ljust(w + 1) + "│")
    else:
        print(f"│  GPU   none (CPU inference only)".ljust(w + 1) + "│")
    print(f"│  OS    {hw.platform}".ljust(w + 1) + "│")
    print("├" + "─" * w + "┤")
    print(f"│  Tier  {hw.tier_label}".ljust(w + 1) + "│")
    print("├" + "─" * w + "┤")
    print(f"│  Coding model   {tier_cfg['coding_model']:<38} │")
    print(f"│  Planning model {tier_cfg['planning_model']:<38} │")
    print(f"│  Embed model    {tier_cfg['embed_model']:<38} │")
    print(f"│  LLM model      {tier_cfg['llm_model']:<38} │")
    print(f"│  RAG enabled    {str(tier_cfg['rag_enabled']):<38} │")
    if tier_cfg.get("note"):
        print(f"│  Note: {tier_cfg['note'][:50]:<50} │")
    print("└" + "─" * w + "┘")
    print()


def write_profile(hw: HardwareProfile, tier_cfg: dict, output_path: Path):
    profile = {
        "hardware": asdict(hw),
        "selected": {
            "coding_model":   tier_cfg["coding_model"],
            "planning_model": tier_cfg["planning_model"],
            "embed_model":    tier_cfg["embed_model"],
            "llm_model":      tier_cfg["llm_model"],
            "rag_enabled":    tier_cfg["rag_enabled"],
        },
    }
    output_path.write_text(yaml.dump(profile, default_flow_style=False))
    print(f"Profile written → {output_path}")


def patch_workspace(tier_cfg: dict, workspace_path: Path):
    """Update workspace.yaml with the selected models."""
    if not workspace_path.exists():
        print(f"workspace.yaml not found at {workspace_path} — skipping patch")
        return
    with workspace_path.open() as f:
        ws = yaml.safe_load(f) or {}

    ws.setdefault("agent_team", {})
    ws["agent_team"]["model"] = tier_cfg["coding_model"]

    ws.setdefault("rag", {})
    ws["rag"]["enabled"]     = tier_cfg["rag_enabled"]
    ws["rag"]["embed_model"] = tier_cfg["embed_model"]
    ws["rag"]["llm_model"]   = tier_cfg["llm_model"]

    with workspace_path.open("w") as f:
        yaml.dump(ws, f, default_flow_style=False)
    print(f"workspace.yaml updated → {workspace_path}")


def pull_models(tier_cfg: dict):
    models = {
        tier_cfg["coding_model"],
        tier_cfg["planning_model"],
        tier_cfg["embed_model"],
        tier_cfg["llm_model"],
    }
    print(f"\nPulling {len(models)} model(s)...")
    for model in sorted(models):
        print(f"  ollama pull {model}")
        subprocess.run(["ollama", "pull", model], check=False)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hardware diagnostic and model selection")
    parser.add_argument("--dry-run",    action="store_true", help="Show selection only")
    parser.add_argument("--pull",       action="store_true", help="Pull selected models")
    parser.add_argument("--force-tier", choices=list(TIERS),
                        help="Override auto-detected tier")
    parser.add_argument("--output",     type=Path,
                        default=Path(__file__).parent.parent / "model-profile.yaml",
                        help="Where to write the profile YAML")
    args = parser.parse_args()

    print("Detecting hardware...")
    hw = detect_hardware()

    if args.force_tier:
        hw.tier       = args.force_tier
        hw.tier_label = TIERS[args.force_tier]["label"]
        print(f"Tier overridden → {args.force_tier}")

    tier_cfg = TIERS[hw.tier]
    print_report(hw, tier_cfg)

    if args.dry_run:
        print("Dry run — no files written.")
        return

    write_profile(hw, tier_cfg, args.output)
    patch_workspace(tier_cfg, REPO_ROOT / "workspace.yaml")

    if args.pull:
        if not shutil.which("ollama"):
            print("Ollama not found — skipping pull")
        else:
            pull_models(tier_cfg)

    print("\nDone. Next steps:")
    print("  make hooks        # install pre-commit hook")
    print("  make build        # run the agent team")
    print("  make monitor      # watch system usage live")


if __name__ == "__main__":
    main()
