"""Shared process-sampling helpers used by both the CLI and GUI monitors."""

import json
import os
from datetime import datetime, timezone

import psutil


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path, data):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def matches(proc_name, proc_exe, patterns):
    proc_name = (proc_name or "").lower()
    proc_exe = (proc_exe or "").lower()
    return any(pat.lower() in proc_name or pat.lower() in proc_exe for pat in patterns)


def find_matching_procs(patterns):
    found = []
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if matches(p.info["name"], p.info["exe"], patterns):
                found.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def prime(procs):
    """psutil needs one throwaway cpu_percent() call before later calls
    return meaningful (non-zero-since-process-start) numbers."""
    for p in procs:
        try:
            p.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def sample(procs):
    """One sample across the given psutil.Process list. Returns
    (per_process_list, aggregate_dict, still_alive_procs)."""
    per_proc = []
    total_cpu = 0.0
    total_rss = 0
    alive = []
    for p in procs:
        try:
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_info()
            per_proc.append({
                "pid": p.pid,
                "name": p.name(),
                "cpu_percent": cpu,
                "rss_mb": round(mem.rss / (1024 * 1024), 2),
                "vms_mb": round(mem.vms / (1024 * 1024), 2),
                "num_threads": p.num_threads(),
            })
            total_cpu += cpu
            total_rss += mem.rss
            alive.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    aggregate = {
        "process_count": len(per_proc),
        "cpu_percent_sum": round(total_cpu, 2),
        "rss_mb_sum": round(total_rss / (1024 * 1024), 2),
    }
    return per_proc, aggregate, alive


def build_summary(samples):
    cpu_vals = [s["target"]["cpu_percent_sum"] for s in samples]
    ram_vals = [s["target"]["rss_mb_sum"] for s in samples]
    return {
        "cpu_percent_sum": {
            "min": round(min(cpu_vals), 2),
            "max": round(max(cpu_vals), 2),
            "avg": round(sum(cpu_vals) / len(cpu_vals), 2),
        },
        "ram_mb_sum": {
            "min": round(min(ram_vals), 2),
            "max": round(max(ram_vals), 2),
            "avg": round(sum(ram_vals) / len(ram_vals), 2),
        },
        "sample_count": len(samples),
        "duration_s": samples[-1]["elapsed_s"],
    }
