#!/usr/bin/env python3
"""
Resource monitor for the AGENT_665956_V10_15_3_RW EDR/AV agent.

Two subcommands:

  discover   Snapshot the running process list so you can diff a
             "before install" snapshot against an "after install" one
             and see exactly which process name(s) the agent installed
             (installer filenames rarely match the running service name).

  monitor    Poll one or more processes (matched by name substring) at a
             fixed interval and log CPU% / RAM usage to a JSON file.

Requires: psutil  (pip install psutil)
Target OS: Windows (run inside the Windows Sandbox where the agent is
installed). The script itself is plain Python + psutil, so it also runs
on Linux/macOS for testing, but process-name matching is meant for the
Windows process list.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    sys.exit(
        "psutil is required but not installed.\n"
        "Install it inside the sandbox with:  pip install psutil"
    )


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path, data):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------- discover

def cmd_discover(args):
    snapshot = {}
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            snapshot[str(p.pid)] = {
                "name": p.info["name"],
                "exe": p.info["exe"],
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if args.diff:
        with open(args.diff, "r", encoding="utf-8") as f:
            before = json.load(f)
        before_names = {v["name"] for v in before.values()}
        new_procs = [v for v in snapshot.values() if v["name"] not in before_names]

        print(f"Processes present now but not in {args.diff}:")
        if not new_procs:
            print("  (none found - agent processes may already have been running,"
                  " or share a name with something already in the baseline)")
        else:
            seen = set()
            for proc in new_procs:
                key = (proc["name"], proc["exe"])
                if key in seen:
                    continue
                seen.add(key)
                print(f"  name={proc['name']!r}  exe={proc['exe']}")

    atomic_write_json(args.output, snapshot)
    print(f"\nSnapshot of {len(snapshot)} processes written to {args.output}")


# ----------------------------------------------------------------- monitor

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


def sample(procs):
    """One sample across all currently-matching processes. Returns
    (per_process_list, aggregate_dict); drops processes that died."""
    per_proc = []
    total_cpu = 0.0
    total_rss = 0
    alive = []
    for p in procs:
        try:
            cpu = p.cpu_percent(interval=None)  # non-blocking, needs prior priming call
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


def cmd_monitor(args):
    patterns = args.name
    print(f"Watching for processes matching: {patterns}")
    print("(name or exe path contains any of the patterns, case-insensitive)")

    procs = find_matching_procs(patterns)
    if not procs:
        print("No matching process found yet - will keep looking every interval "
              "until one appears (start/install the agent now if you haven't).")

    # Prime cpu_percent() for anything already found; psutil needs one throwaway
    # call before the numbers returned by later calls are meaningful.
    for p in procs:
        try:
            p.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    samples = []
    start = time.monotonic()
    deadline = start + args.duration if args.duration else None
    logical_cpus = psutil.cpu_count(logical=True)

    print(f"Logging every {args.interval}s to {args.output}"
          f"{f' for {args.duration}s' if args.duration else ' until Ctrl+C'}.")

    try:
        while True:
            time.sleep(args.interval)

            # Pick up newly-spawned matching processes (e.g. installer forking
            # a service + tray helper) and drop ones that already exited.
            new_procs = find_matching_procs(patterns)
            known_pids = {p.pid for p in procs}
            for np in new_procs:
                if np.pid not in known_pids:
                    try:
                        np.cpu_percent(interval=None)  # prime
                        procs.append(np)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            per_proc, aggregate, procs = sample(procs)
            sys_cpu = psutil.cpu_percent(interval=None)
            sys_mem = psutil.virtual_memory()

            entry = {
                "timestamp": now_iso(),
                "elapsed_s": round(time.monotonic() - start, 1),
                "target": {
                    "processes": per_proc,
                    **aggregate,
                    "cpu_percent_of_all_cores": round(
                        aggregate["cpu_percent_sum"] / logical_cpus, 2
                    ) if logical_cpus else None,
                },
                "system": {
                    "cpu_percent": sys_cpu,
                    "ram_used_percent": sys_mem.percent,
                    "ram_used_mb": round((sys_mem.total - sys_mem.available) / (1024 * 1024), 2),
                    "ram_total_mb": round(sys_mem.total / (1024 * 1024), 2),
                },
            }
            samples.append(entry)

            atomic_write_json(args.output, {
                "target_name_patterns": patterns,
                "interval_s": args.interval,
                "logical_cpus": logical_cpus,
                "samples": samples,
            })

            found = aggregate["process_count"]
            print(f"[{entry['elapsed_s']:>7.1f}s] procs={found} "
                  f"cpu%={aggregate['cpu_percent_sum']:>6.1f} "
                  f"ram={aggregate['rss_mb_sum']:>8.1f}MB")

            if deadline and time.monotonic() >= deadline:
                break
    except KeyboardInterrupt:
        print("\nStopped by user.")

    write_summary(args.output, samples, patterns, args.interval, logical_cpus)


def write_summary(output_path, samples, patterns, interval, logical_cpus):
    if not samples:
        print("No samples collected - nothing to summarize.")
        return

    cpu_vals = [s["target"]["cpu_percent_sum"] for s in samples]
    ram_vals = [s["target"]["rss_mb_sum"] for s in samples]

    summary = {
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

    atomic_write_json(output_path, {
        "target_name_patterns": patterns,
        "interval_s": interval,
        "logical_cpus": logical_cpus,
        "summary": summary,
        "samples": samples,
    })

    print("\n--- Summary ---")
    print(f"Samples: {summary['sample_count']}  Duration: {summary['duration_s']}s")
    print(f"CPU% (sum of matched processes): min={summary['cpu_percent_sum']['min']} "
          f"avg={summary['cpu_percent_sum']['avg']} max={summary['cpu_percent_sum']['max']}")
    print(f"RAM MB (sum of matched processes): min={summary['ram_mb_sum']['min']} "
          f"avg={summary['ram_mb_sum']['avg']} max={summary['ram_mb_sum']['max']}")
    print(f"Full log written to {output_path}")


# --------------------------------------------------------------------- cli

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.strip(),
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_disc = sub.add_parser("discover", help="Snapshot running processes (before/after install diff)")
    p_disc.add_argument("-o", "--output", default="process_snapshot.json",
                         help="Where to write this snapshot (default: process_snapshot.json)")
    p_disc.add_argument("--diff", metavar="BEFORE_SNAPSHOT.json",
                         help="Compare against an earlier snapshot and print processes that are new")
    p_disc.set_defaults(func=cmd_discover)

    p_mon = sub.add_parser("monitor", help="Log CPU/RAM of matching process(es) to JSON")
    p_mon.add_argument("--name", action="append", required=True,
                        help="Substring to match against process name/exe path "
                             "(case-insensitive). Repeat --name for multiple patterns, "
                             "e.g. --name agent --name 665956")
    p_mon.add_argument("-i", "--interval", type=float, default=2.0,
                        help="Seconds between samples (default: 2)")
    p_mon.add_argument("-d", "--duration", type=float, default=0,
                        help="Total seconds to run; 0 = run until Ctrl+C (default: 0)")
    p_mon.add_argument("-o", "--output", default="av_resource_usage.json",
                        help="JSON file to write/update (default: av_resource_usage.json)")
    p_mon.set_defaults(func=cmd_monitor)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
