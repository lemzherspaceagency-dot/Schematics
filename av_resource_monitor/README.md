# AV/EDR resource monitor (AGENT_665956_V10_15_3_RW)

Small Python + `psutil` tool for measuring how much CPU and RAM the
`AGENT_665956_V10_15_3_RW.EXE` agent uses once installed in a Windows
Sandbox.

## Setup inside the Windows Sandbox

1. Install Python 3 in the sandbox (winget or the python.org installer).
2. `pip install psutil`
3. Copy `monitor_av_resources.py` into the sandbox (drag-and-drop works in
   Windows Sandbox, or share a folder via the sandbox config file).

## Step 1 — find out what the agent's real process name is

Installer filenames rarely match the process/service name that ends up
running, so snapshot before/after:

```powershell
# before running the installer
python monitor_av_resources.py discover -o before.json

# ...run AGENT_665956_V10_15_3_RW.EXE, let it finish installing...

# after install
python monitor_av_resources.py discover -o after.json --diff before.json
```

The `--diff` output lists every process that appeared after the install
(name + exe path) — that's how you find the real process name(s) to
monitor, e.g. `agentsvc.exe`, `edrtray.exe`, whatever it turns out to be.

## Step 2 — monitor CPU/RAM

```powershell
python monitor_av_resources.py monitor --name agentsvc --name edrtray -i 2 -d 3600 -o usage.json
```

- `--name` — substring matched against process name/exe path, case
  insensitive. Repeat the flag for multiple processes (agents often run a
  service + a tray helper + a scan engine as separate processes) — their
  CPU/RAM are summed for a total footprint, and also broken out
  per-process in the JSON.
- `-i / --interval` — seconds between samples (default 2).
- `-d / --duration` — total seconds to run; omit or `0` to run until
  Ctrl+C (e.g. while you do a manual full-system scan and want to see the
  peak).
- `-o / --output` — JSON file, rewritten after every sample so it's
  always valid even if you stop early.

The script keeps watching for new matching processes as it runs (so a
scan engine that only starts during an on-demand scan gets picked up),
and drops processes that exit.

## Output

`usage.json` contains, per sample: timestamp, per-process CPU%/RAM, the
summed total across all matched processes, and system-wide CPU%/RAM for
context (so you can tell the agent's load apart from background noise).
When the run ends (duration elapsed or Ctrl+C) a `summary` block with
min/avg/max CPU% and RAM is added to the same file.

```json
{
  "target_name_patterns": ["agentsvc", "edrtray"],
  "interval_s": 2,
  "logical_cpus": 4,
  "summary": {
    "cpu_percent_sum": { "min": 0.0, "avg": 3.2, "max": 41.5 },
    "ram_mb_sum": { "min": 120.4, "avg": 145.1, "max": 210.7 },
    "sample_count": 1800,
    "duration_s": 3600.0
  },
  "samples": [ ... ]
}
```

Note: `cpu_percent_sum` is the sum across all matched processes and can
exceed 100% on multi-core systems (psutil convention — 100% = one core
fully busy); the JSON also includes `cpu_percent_of_all_cores`, normalized
by logical CPU count, if you want a 0-100% figure relative to the whole
machine.
