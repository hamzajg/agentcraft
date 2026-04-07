"""
collector.py — system metrics collector.

Collects CPU, RAM, GPU, VRAM, and Ollama process stats.
Used by both the CLI monitor and the FastAPI /api/metrics SSE endpoint.

Designed to work without psutil installed (fallback to platform commands),
but psutil is preferred for accuracy and cross-platform support.
"""

import json
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict, field
from typing import Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class GpuMetrics:
    name:        str
    utilization: float   # 0–100 %
    vram_used_gb: float
    vram_total_gb: float
    vram_pct:    float
    temp_c:      Optional[float] = None


@dataclass
class SystemMetrics:
    ts:            float             # unix timestamp
    cpu_pct:       float
    cpu_cores:     int
    ram_used_gb:   float
    ram_total_gb:  float
    ram_pct:       float
    gpus:          list              # list of GpuMetrics dicts
    ollama_pid:    Optional[int]
    ollama_cpu:    float
    ollama_ram_gb: float

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def collect() -> SystemMetrics:
    """Collect a single snapshot of system metrics."""
    cpu_pct, cpu_cores, ram_used, ram_total, ram_pct = _cpu_ram()
    gpus                    = _gpus()
    ollama_pid, ocpu, oram  = _ollama_process()

    return SystemMetrics(
        ts=time.time(),
        cpu_pct=round(cpu_pct, 1),
        cpu_cores=cpu_cores,
        ram_used_gb=round(ram_used, 2),
        ram_total_gb=round(ram_total, 1),
        ram_pct=round(ram_pct, 1),
        gpus=[asdict(g) for g in gpus],
        ollama_pid=ollama_pid,
        ollama_cpu=round(ocpu, 1),
        ollama_ram_gb=round(oram, 2),
    )


# ── CPU / RAM ─────────────────────────────────────────────────────────────────

def _cpu_ram():
    import multiprocessing
    cores = multiprocessing.cpu_count()

    if _HAS_PSUTIL:
        cpu  = psutil.cpu_percent(interval=0.2)
        vm   = psutil.virtual_memory()
        used = vm.used  / (1024**3)
        total= vm.total / (1024**3)
        pct  = vm.percent
        return cpu, cores, used, total, pct

    # Fallback — Linux
    if platform.system() == "Linux":
        try:
            cpu = float(subprocess.check_output(
                "grep 'cpu ' /proc/stat | awk '{u=$2+$4; t=$2+$3+$4+$5; print u/t*100}'",
                shell=True, text=True).strip())
        except Exception:
            cpu = 0.0
        try:
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    k, v = line.split(":")
                    info[k.strip()] = int(v.strip().split()[0])
            total = info["MemTotal"]  / (1024**2)
            avail = info["MemAvailable"] / (1024**2)
            used  = total - avail
            pct   = used / total * 100
        except Exception:
            total, used, pct = 8.0, 4.0, 50.0
        return cpu, cores, used, total, pct

    return 0.0, cores, 0.0, 8.0, 0.0


# ── GPU ───────────────────────────────────────────────────────────────────────

def _gpus() -> list[GpuMetrics]:
    gpus = _nvidia_gpus()
    if gpus:
        return gpus
    gpus = _apple_silicon_gpu()
    if gpus:
        return gpus
    return []


def _nvidia_gpus() -> list[GpuMetrics]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            text=True, timeout=5
        )
        result = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            name       = parts[0]
            util       = float(parts[1]) if parts[1].isdigit() else 0.0
            vram_used  = float(parts[2]) / 1024
            vram_total = float(parts[3]) / 1024
            temp       = float(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
            result.append(GpuMetrics(
                name=name, utilization=util,
                vram_used_gb=round(vram_used, 2),
                vram_total_gb=round(vram_total, 1),
                vram_pct=round(vram_used / vram_total * 100 if vram_total else 0, 1),
                temp_c=temp,
            ))
        return result
    except Exception:
        return []


def _apple_silicon_gpu() -> list[GpuMetrics]:
    """Approximate Apple Silicon GPU usage via powermetrics (requires sudo) or fallback."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return []
    # Without sudo powermetrics, report unified memory as VRAM
    if _HAS_PSUTIL:
        vm         = psutil.virtual_memory()
        total_gb   = vm.total / (1024**3)
        used_gb    = vm.used  / (1024**3)
        return [GpuMetrics(
            name="Apple Silicon (Unified)",
            utilization=0.0,   # not available without powermetrics
            vram_used_gb=round(used_gb, 2),
            vram_total_gb=round(total_gb, 1),
            vram_pct=round(vm.percent, 1),
        )]
    return []


# ── Ollama process ────────────────────────────────────────────────────────────

def _ollama_process() -> tuple[Optional[int], float, float]:
    """Find the Ollama process and return (pid, cpu%, ram_gb)."""
    if _HAS_PSUTIL:
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                if "ollama" in proc.info["name"].lower():
                    cpu = proc.info["cpu_percent"] or 0.0
                    ram = (proc.info["memory_info"].rss or 0) / (1024**3)
                    return proc.info["pid"], cpu, ram
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    else:
        try:
            out = subprocess.check_output(
                ["pgrep", "-x", "ollama"], text=True).strip()
            if out:
                pid = int(out.splitlines()[0])
                return pid, 0.0, 0.0
        except Exception:
            pass
    return None, 0.0, 0.0
