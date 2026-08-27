# AV/EDR resource monitor (AGENT_665956_V10_15_3_RW)

Small Python + `psutil` tool for measuring how much CPU and RAM the
`AGENT_665956_V10_15_3_RW.EXE` agent uses once installed in a Windows
Sandbox. Comes in two flavours:

- **`av_monitor_gui.py`** — point-and-click app, no terminal needed once
  it's running. Recommended for everyday use.
- **`monitor_av_resources.py`** — command-line version with the same
  underlying logic, for scripting/automation.

## Setup inside the Windows Sandbox

1. Install Python 3 in the sandbox (winget or the python.org installer —
   tick "Add to PATH"; tkinter, needed for the GUI, is included by
   default in the standard python.org installer).
2. `pip install psutil`
3. Copy the whole `av_resource_monitor` folder into the sandbox
   (drag-and-drop works in Windows Sandbox, or share a folder via the
   sandbox config file). Keep all three `.py` files together — the GUI
   and CLI both import `av_monitor_core.py`.

## Easiest way: the GUI

```powershell
python av_monitor_gui.py
```

(Double-clicking works too if `.py` files are associated with `python.exe`;
rename to `av_monitor_gui.pyw` first if you don't want a console window
behind it.)

1. Open it **before** running the installer.
2. Run `AGENT_665956_V10_15_3_RW.EXE` and let it finish installing.
3. Back in the app, click **Refresh** — any process that appeared since
   the app was opened is tagged **NAUJAS** and highlighted yellow, so you
   don't have to guess the process name (installer filenames rarely match
   the real service name).
4. Click the checkbox next to the process(es) that belong to the agent
   (tick all of them if it runs a service + tray icon + scan engine as
   separate processes — their usage gets summed and also shown per
   process).
5. Set the interval/duration/output file if you want something other
   than the defaults, click **Start**.
6. Watch the live table and the CPU/RAM graph. Click **Stop** whenever —
   the JSON file has been kept up to date the whole time and gets a
   summary (min/avg/max) block added when you stop.

## Building a standalone .exe (no Python needed to run it)

Windows executables have to be built on Windows - there's no reliable way
to cross-compile a real `.exe` from Linux, so this has to run inside your
Windows Sandbox (or any Windows machine) once. After that one-time build,
the resulting `.exe` is fully standalone.

1. Make sure Python is installed in the sandbox (see Setup above).
2. Double-click `build_exe.bat` in this folder (or run it from a
   terminal). It installs `pyinstaller`+`psutil` and packages
   `av_monitor_gui.py` into `AV_Resource_Monitor.exe`.
3. Once it finishes, `AV_Resource_Monitor.exe` sits in this folder as a
   single file. Copy just that file anywhere - it bundles its own Python
   and Tk runtime, so it runs with no Python installed. That's the file
   you can drop straight into future fresh Sandbox sessions.

## Command-line alternative

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
