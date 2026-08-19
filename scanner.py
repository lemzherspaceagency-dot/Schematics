#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IT Kitaip - Windows Health & Security Scanner
=============================================

A self-contained Windows endpoint scanner for MSP use.

What it does
------------
1. Collects a system inventory, Windows Event Log signals, Defender status,
   security posture, accounts, services, network listeners and disk health.
2. Runs local rule-based heuristics to flag problems immediately (works with
   NO internet and NO API key).
3. Optionally sends the (optionally sanitized) findings to the Claude API for
   incident-responder-style analysis with CVE / Microsoft-doc lookup.
4. Optionally REPAIRS what it finds. Repairs are DRY-RUN by default. Nothing is
   changed unless you pass --apply, and risky changes still require per-fix
   confirmation. Every applied change records a rollback hint and is logged.
5. Writes a self-contained HTML report (opens in any browser, no extra apps)
   plus a JSON export.

Design goals
------------
* Standard library only  -> trivial to compile to a single .exe with PyInstaller.
* Degrades gracefully     -> every collector is wrapped; a missing capability
                             produces a note, never a crash.
* Safe by default         -> read-only unless explicitly told to repair.
* Universal               -> no assumptions about domain membership, edition,
                             or installed roles.

Author: built for IT Kitaip. Reuse freely.
"""

import argparse
import ctypes
import datetime
import getpass
import html
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import traceback
import urllib.request
import urllib.error

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

APP_NAME = "IT Kitaip Windows Scanner"
APP_VERSION = "1.0.0"

# ---- AI backend ----------------------------------------------------------- #
# "ollama"     = local, free, offline, no billing (DEFAULT). No live web search.
# "anthropic"  = Claude API, pay-as-you-go, supports live CVE/web verification.
# "claude_cli" = the `claude` CLI (Claude Code) in headless mode. Can run off a
#                Claude Pro/Max subscription (no per-token bill). Needs Node.js +
#                the CLI installed & logged in on THIS machine — use on a central
#                admin box, not on every endpoint.
DEFAULT_BACKEND = os.environ.get("SCANNER_BACKEND", "ollama")

# Ollama (local). Endpoint is the machine running `ollama serve` (default local).
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

# Claude CLI (headless). Path to the executable, and an optional model override.
CLAUDE_CLI_BIN = os.environ.get("CLAUDE_CLI_BIN", "claude")
CLAUDE_CLI_MODEL = os.environ.get("CLAUDE_CLI_MODEL", "")  # "" = CLI's default

# Anthropic (optional). VERIFY the model string at https://docs.claude.com.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# How far back to pull event logs, in days.
DEFAULT_LOOKBACK_DAYS = 3

# The system prompt handed to Claude. This is your "Log Analyst" persona.
LOG_ANALYST_SYSTEM_PROMPT = """\
You are a senior Windows systems engineer and diagnostician working for an MSP
(IT Kitaip). Each session you receive a JSON snapshot of a single Windows endpoint
or server, produced by an automated scanner. Your job every session:
analyze -> correlate -> prioritize -> prescribe fixes.

THE SNAPSHOT CONTAINS
- system: inventory, LastBoot / UptimeHours, elevation state.
- event_logs, grouped into AREAS you must read together:
  * security: logons 4624/4625, lockouts 4740, account creation 4720, group
    changes 4728/4732.
  * system: service installs 7045, unexpected shutdown 6008, kernel-power /
    critical 41 / 1001.
  * application: application & runtime errors 1000 / 1002.
  * hardware: disk, Ntfs, WHEA-Logger, storage-controller (storahci/stornvme),
    volmgr and Kernel-PnP events - this is the Hardware area.
- defender: status, signature age, recent threats, preferences.
- security_posture: firewall, SMBv1, UAC, RDP exposure, BitLocker, pending
  reboot, recent hotfixes.
- accounts, services, network listeners, disk_health.
- teams: a full Microsoft Teams picture for this machine. It is DISCOVERED, not
  assumed - read teams.summary first (new_teams_installed, version, package
  Status, classic_teams_present, both_installed, running, install_locations_found).
  Then: new_teams_package (MSIX identity), new_teams_provisioned (machine-wide),
  running_processes (real exe paths + memory), discovered_locations (install dirs
  and Start-menu shortcuts actually found on disk), data_paths (cache/profile
  folders with size in MB and file counts), log_files (recent Teams client logs
  and where they are), crash_events (Application 1000/1001/1002 filtered to
  Teams), appx_errors (AppXDeploymentServer failures - why install/update
  breaks), webview2 (runtime version; a hard prerequisite - blank means missing),
  policy (Office\\Teams key, AllowAllTrustedApps, autostart entries),
  outlook_addin (LoadBehavior; 3 = active), connectivity (TCP 443 reachability of
  teams.microsoft.com, login.microsoftonline.com, config.teams.microsoft.com).
  If teams.summary shows nothing installed, say so plainly and skip the section -
  do not invent Teams findings.
- whatsapp: a diagnostics-only picture of WhatsApp Desktop on this machine
  (NO message content, NO chat/contact data, NO media - process/version/crash/log
  health only). Read whatsapp.summary first (installed, version, status, running,
  install_locations_found). Then: package (MSIX identity), running_processes (real
  exe path + memory), discovered_locations (install dirs and Start-menu shortcuts
  found on disk), data_paths (LocalState/LocalCache folder SIZE IN MB and file
  COUNT only - never individual file names or content), log_files (paths and sizes
  of recent client logs, not their content), crash_events (Application
  1000/1001/1002 filtered to WhatsApp), appx_errors (AppXDeploymentServer failures
  - why install/update breaks). If whatsapp.summary shows nothing installed, say
  so plainly and skip the section - do not invent WhatsApp findings. Never ask for
  or speculate about message/chat contents; this data was never collected.

TEAMS ANALYSIS RULES
- Treat Teams as its own area and correlate it with the others: Teams crashes
  <-> Application 1000 <-> disk/Ntfs errors (failing storage corrupts the cache);
  Teams sign-in failures <-> connectivity results <-> proxy/firewall posture;
  Teams update failures <-> appx_errors <-> AllowAllTrustedApps policy <-> low
  disk space; high cache size <-> slow start complaints.
- Classic + new Teams both installed is a real finding (duplicate notifications,
  meeting add-in conflicts); classic Teams is retired.
- Prefer least-invasive Teams fixes in this order: restart client -> clear the
  MS-recommended cache path (%LOCALAPPDATA%\\Packages\\MSTeams_8wekyb3d8bbwe\\
  LocalCache\\Microsoft\\MSTeams) -> Reset via Settings > Apps > Advanced options
  -> re-provision with teamsbootstrapper.exe -p -> full reinstall. State that
  clearing cache or resetting wipes local personalization and signs the user out
  of some settings.
- The WindowsApps install folder name contains the version and changes on every
  update - never tell the user to hardcode it; resolve it via
  Get-AppxPackage -Name '*MSTeams*' or the discovered path in the snapshot.

WHATSAPP ANALYSIS RULES
- Treat WhatsApp as its own area, correlated the same way as Teams: crashes
  <-> Application 1000/1001/1002 <-> disk/Ntfs errors; install/update failures
  <-> appx_errors; oversized LocalCache <-> slow start / disk space complaints.
- This is diagnostics-only. Never infer, ask about, or comment on conversation
  content, contacts, or message volume - none of that was collected and it is
  out of scope for this report.
- Prefer least-invasive fixes: restart client -> clear LocalCache (note this
  clears local media cache but does not delete the account or message history,
  which is stored server-side/in LocalState) -> repair/reset via Settings > Apps
  > Advanced options -> reinstall from Microsoft Store.
- The WindowsApps/Packages folder names include an identity suffix that can vary
  by build - resolve via Get-AppxPackage -Name '*WhatsAppDesktop*' or the
  discovered path in the snapshot, never hardcode it.

ANALYSIS RULES
- Read every area before concluding. Never analyze one log in isolation; the same
  root cause often surfaces across areas with different symptoms (a failing disk
  shows as hardware 'disk' Event 7, Ntfs warnings in system, and crashes in
  application).
- Cross-log correlation is MANDATORY. For each significant finding, check: do
  events share a time window (+/- 2 min)? do they reference the same
  component / driver / service / PID / volume? is there a causal chain
  (unexpected shutdown -> dirty volume -> service-start failures)? State each as:
  [Area A EventID X] <-> [Area B EventID Y] - relationship.
- Distinguish noise from signal. Classify and set aside known-benign chatter
  (DCOM 10016, Perflib 1008 / 2003, ESENT informational, Time-Service drift < 5s,
  expected TPM / Defender informational events). Say what you ignored and why -
  never silently drop anything.
- Frequency and recency matter. Note repetition counts, first / last occurrence,
  and whether events cluster around boot, wake, or a timestamp. Compare against
  LastBoot and UptimeHours.
- Session-over-session: if a previous snapshot or report is provided, diff it -
  new issues, resolved issues, worsening trends, and whether prior fixes worked.
- Never invent event details. If a message is truncated or ambiguous, say so and
  give the exact Get-WinEvent filter that would disambiguate it.
- Treat the non-event data as first-class findings too: Defender off / stale,
  firewall off, SMBv1 / UAC / RDP posture, low disk, disk HealthStatus, and
  unexpected accounts or Administrators members are findings in their own right.

SEVERITY TRIAGE - assign each finding exactly one:
- P1 - Act now: data-loss risk, imminent hardware failure (WHEA uncorrectable,
  disk bad blocks, NTFS corruption), boot instability, active security failures
  (Defender disabled, brute-force success, unexpected admin / account creation).
- P2 - Fix this week: recurring service / driver failures, application crash
  loops, degraded-but-functioning components, stale signatures, missing hardening.
- P3 - Monitor: intermittent warnings, first-occurrence events, cosmetic errors.
- INFO - Noise: benign chatter (list it, then exclude it).

REQUIRED REPORT FORMAT (Markdown, use these exact section headers):
# LOG ANALYSIS - <Hostname> - <scanned_at>

## 1. Executive summary
2-4 sentences: overall verdict (Healthy / Degraded / At Risk / Critical), the
single most important issue, and whether immediate action is needed. If there are
active-compromise / ransomware / exfiltration indicators, say so FIRST here.

## 2. Findings (ordered by severity)
For each finding:
### [P1|P2|P3] <short title>
- **Evidence**: EventID(s) / provider / area(s) or posture item, count, time span
- **Correlation**: cross-log links found (or "none - isolated")
- **Root cause assessment**: most likely cause + confidence (High / Medium / Low)
- **Fix**: numbered steps, least-invasive first, with exact idempotent
  PowerShell / CMD commands
- **Verification**: how to confirm the fix worked (event to watch / command output)
- **If unresolved**: escalation path (vendor KB, firmware, RMA, deeper capture)

## 3. Cross-log correlation map
Every correlation chain identified this session.

## 4. Noise excluded
Table: EventID | Provider | Why benign

## 5. Trend vs previous session
Diff if prior data is given, else state "N/A - no prior data provided".

## 6. Watch list for next session
Specific EventIDs / providers to re-check, plus the Get-WinEvent one-liner to pull
them directly.

FIX QUALITY
- Built-in tooling first: sfc /scannow, DISM /Online /Cleanup-Image /RestoreHealth,
  chkdsk, Repair-Volume, service recovery settings, driver rollback - before
  registry edits or reinstalls.
- Every registry or destructive change must include a backup / rollback step.
- Flag anything requiring a reboot or maintenance window explicitly.
- If a fix depends on hardware replacement, say so directly; do not offer software
  workarounds for dying hardware without stating they are temporary.
- When an EventID + Provider maps to a known Microsoft KB or CVE, name it. If a web
  search tool is available, use it to confirm the reference is current; if you
  cannot verify, say the ID should be verified rather than asserting it. Never
  present unverified references as fact.

TONE
Direct, technical, no filler - the reader is an experienced sysadmin. Output in
Lithuanian or English, matching the language of the snapshot / user; default to
English.
"""

# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #

def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def is_windows():
    return os.name == "nt"


def is_admin():
    """Return True if running elevated (Windows) — best effort."""
    if not is_windows():
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


class C:
    """Minimal ANSI colours; auto-disabled if not a TTY or not supported."""
    _on = sys.stdout.isatty()
    G = "\033[92m" if _on else ""
    Y = "\033[93m" if _on else ""
    R = "\033[91m" if _on else ""
    B = "\033[94m" if _on else ""
    DIM = "\033[2m" if _on else ""
    X = "\033[0m" if _on else ""


def log(msg, level="info"):
    tag = {
        "info": f"{C.B}[*]{C.X}",
        "ok": f"{C.G}[+]{C.X}",
        "warn": f"{C.Y}[!]{C.X}",
        "err": f"{C.R}[x]{C.X}",
        "step": f"{C.DIM}  ->{C.X}",
    }.get(level, "[*]")
    print(f"{tag} {msg}", flush=True)


def run_powershell(script, timeout=60):
    """
    Run a PowerShell snippet and return stdout as text.
    Returns "" on any failure. Never raises.
    """
    if not is_windows():
        return ""
    for exe in ("powershell.exe", "pwsh.exe"):
        try:
            proc = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-Command", script],
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
            if proc.returncode == 0 or proc.stdout:
                return proc.stdout.strip()
        except FileNotFoundError:
            continue
        except Exception:
            return ""
    return ""


def ps_json(script, timeout=60):
    """Run PowerShell that ends in ConvertTo-Json and parse it."""
    raw = run_powershell(script, timeout=timeout)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def as_list(x):
    """PowerShell ConvertTo-Json returns a bare object for single items."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# --------------------------------------------------------------------------- #
# Collectors  (all read-only, all wrapped)
# --------------------------------------------------------------------------- #

def safe(fn):
    """Wrap a collector so it can never crash the run."""
    try:
        return fn()
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def collect_system_info():
    info = {
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "os_release": platform.release(),
        "scanned_at": now_iso(),
        "elevated": is_admin(),
    }
    data = ps_json(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption,Version,BuildNumber,OSArchitecture,"
        "@{n='InstallDate';e={$_.InstallDate.ToString('o')}},"
        "@{n='LastBoot';e={$_.LastBootUpTime.ToString('o')}},"
        "@{n='FreePhysicalMemoryMB';e={[math]::Round($_.FreePhysicalMemory/1024)}},"
        "@{n='TotalVisibleMemoryMB';e={[math]::Round($_.TotalVisibleMemorySize/1024)}} "
        "| ConvertTo-Json -Compress"
    )
    if data:
        info.update(data)
    cs = ps_json(
        "Get-CimInstance Win32_ComputerSystem | "
        "Select-Object Manufacturer,Model,Domain,PartOfDomain,"
        "NumberOfLogicalProcessors | ConvertTo-Json -Compress"
    )
    if cs:
        info.update(cs)
    return info


def collect_event_logs(lookback_days):
    """
    Pull the security-relevant event IDs. Returns dict keyed by category with
    lists of {TimeCreated, Id, Message} and simple aggregates.
    """
    start = (datetime.datetime.now() -
             datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%S")

    def pull(logname, ids, maxev=400):
        id_arr = ",".join(str(i) for i in ids)
        script = (
            f"$s=[datetime]'{start}';"
            f"try{{Get-WinEvent -FilterHashtable @{{LogName='{logname}';"
            f"Id={id_arr};StartTime=$s}} -MaxEvents {maxev} -ErrorAction Stop | "
            f"Select-Object @{{n='TimeCreated';e={{$_.TimeCreated.ToString('o')}}}},"
            f"Id,@{{n='Message';e={{($_.Message -split \"`n\")[0]}}}} | "
            f"ConvertTo-Json -Compress}}catch{{'[]'}}"
        )
        return as_list(ps_json(script) or [])

    def pull_providers(logname, providers, levels, maxev=250):
        """Pull Critical/Error/Warning events from specific providers (Hardware)."""
        prov = ",".join(f"'{p}'" for p in providers)
        lvl = ",".join(str(l) for l in levels)
        script = (
            f"$s=[datetime]'{start}';"
            f"try{{Get-WinEvent -FilterHashtable @{{LogName='{logname}';"
            f"ProviderName=@({prov});Level=@({lvl});StartTime=$s}} "
            f"-MaxEvents {maxev} -ErrorAction Stop | "
            f"Select-Object @{{n='TimeCreated';e={{$_.TimeCreated.ToString('o')}}}},"
            f"Id,@{{n='Provider';e={{$_.ProviderName}}}},"
            f"@{{n='Message';e={{($_.Message -split \"`n\")[0]}}}} | "
            f"ConvertTo-Json -Compress}}catch{{'[]'}}"
        )
        return as_list(ps_json(script) or [])

    security = {
        "failed_logons_4625": pull("Security", [4625]),
        "successful_logons_4624": pull("Security", [4624], maxev=200),
        "account_lockouts_4740": pull("Security", [4740]),
        "account_created_4720": pull("Security", [4720]),
        "added_to_group_4728_4732": pull("Security", [4728, 4732]),
    }
    system = {
        "service_installed_7045": pull("System", [7045]),
        "unexpected_shutdown_6008": pull("System", [6008]),
        "critical_errors": pull("System", [41, 1001]),
        "service_control_errors_7000_7001_7031_7034": pull(
            "System", [7000, 7001, 7031, 7034]),
    }
    application = {
        "app_errors_1000_1002": pull("Application", [1000, 1002]),
    }
    # Hardware area: disk / filesystem / WHEA / storage-controller / PnP.
    # Levels: 1=Critical, 2=Error, 3=Warning.
    hardware = {
        "storage_and_disk": pull_providers(
            "System",
            ["disk", "Ntfs", "volmgr", "storahci", "stornvme", "iaStorA",
             "Microsoft-Windows-Ntfs", "Microsoft-Windows-DiskDiagnosticDataCollector"],
            [1, 2, 3]),
        "whea_hardware_errors": pull_providers(
            "System", ["Microsoft-Windows-WHEA-Logger"], [1, 2, 3]),
        "pnp_device_events": pull_providers(
            "System", ["Microsoft-Windows-Kernel-PnP"], [1, 2]),
    }

    # Aggregate failed-logon sources for quick brute-force spotting.
    failed = security["failed_logons_4625"]
    hw_count = sum(len(v) for v in hardware.values())
    agg = {
        "total_failed_logons": len(failed),
        "total_hardware_events": hw_count,
    }
    return {
        "lookback_days": lookback_days,
        "window_start": start,
        "security": security,
        "system": system,
        "application": application,
        "hardware": hardware,
        "aggregate": agg,
    }


def collect_defender():
    status = ps_json(
        "Get-MpComputerStatus | Select-Object "
        "AMServiceEnabled,AntispywareEnabled,AntivirusEnabled,"
        "RealTimeProtectionEnabled,IoavProtectionEnabled,"
        "BehaviorMonitorEnabled,OnAccessProtectionEnabled,"
        "AntivirusSignatureAge,QuickScanAge,"
        "@{n='AntivirusSignatureLastUpdated';e={$_.AntivirusSignatureLastUpdated.ToString('o')}} "
        "| ConvertTo-Json -Compress"
    )
    threats = as_list(ps_json(
        "Get-MpThreatDetection -ErrorAction SilentlyContinue | "
        "Select-Object -First 50 @{n='InitialDetectionTime';"
        "e={$_.InitialDetectionTime.ToString('o')}},ThreatID,"
        "@{n='Resources';e={$_.Resources -join ';'}} | ConvertTo-Json -Compress"
    ) or [])
    prefs = ps_json(
        "Get-MpPreference | Select-Object DisableRealtimeMonitoring,"
        "MAPSReporting,SubmitSamplesConsent,PUAProtection | ConvertTo-Json -Compress"
    )
    return {"status": status, "recent_threats": threats, "preferences": prefs}


def collect_security_posture():
    posture = {}

    fw = as_list(ps_json(
        "Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json -Compress"
    ) or [])
    posture["firewall_profiles"] = fw

    posture["smb1_enabled"] = ps_json(
        "(Get-SmbServerConfiguration).EnableSMB1Protocol | ConvertTo-Json -Compress"
    )

    posture["rdp_deny_connections"] = run_powershell(
        "(Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' "
        "-Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections"
    )

    posture["uac_enabled"] = run_powershell(
        "(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
        "-Name EnableLUA -ErrorAction SilentlyContinue).EnableLUA"
    )

    posture["bitlocker"] = as_list(ps_json(
        "Get-BitLockerVolume -ErrorAction SilentlyContinue | "
        "Select-Object MountPoint,VolumeStatus,ProtectionStatus,EncryptionPercentage "
        "| ConvertTo-Json -Compress"
    ) or [])

    # Pending reboot (best-effort registry check)
    posture["pending_reboot"] = run_powershell(
        "$p=$false;"
        "if(Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending'){$p=$true};"
        "if(Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'){$p=$true};"
        "$p"
    )

    # Last installed hotfix
    posture["last_hotfixes"] = as_list(ps_json(
        "Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | "
        "Select-Object -First 5 HotFixID,"
        "@{n='InstalledOn';e={if($_.InstalledOn){$_.InstalledOn.ToString('o')}else{''}}} "
        "| ConvertTo-Json -Compress"
    ) or [])

    return posture


def collect_accounts():
    users = as_list(ps_json(
        "Get-LocalUser -ErrorAction SilentlyContinue | Select-Object Name,Enabled,"
        "PasswordRequired,PasswordExpires,"
        "@{n='LastLogon';e={if($_.LastLogon){$_.LastLogon.ToString('o')}else{''}}} "
        "| ConvertTo-Json -Compress"
    ) or [])
    admins = as_list(ps_json(
        "Get-LocalGroupMember -Group 'Administrators' -ErrorAction SilentlyContinue | "
        "Select-Object Name,ObjectClass | ConvertTo-Json -Compress"
    ) or [])
    return {"local_users": users, "administrators": admins}


def collect_services_and_startup():
    svcs = as_list(ps_json(
        "Get-Service | Where-Object Status -eq 'Running' | "
        "Select-Object Name,DisplayName | ConvertTo-Json -Compress"
    ) or [])
    autoruns = as_list(ps_json(
        "$k='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run';"
        "if(Test-Path $k){(Get-ItemProperty $k).PSObject.Properties | "
        "Where-Object {$_.Name -notlike 'PS*'} | "
        "Select-Object Name,Value | ConvertTo-Json -Compress}"
    ) or [])
    return {"running_service_count": len(svcs), "running_services": svcs[:100],
            "hklm_run_autoruns": autoruns}


def collect_network():
    listeners = as_list(ps_json(
        "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object LocalAddress,LocalPort,OwningProcess -Unique | "
        "Sort-Object LocalPort | ConvertTo-Json -Compress"
    ) or [])
    return {"listening_tcp": listeners}


def collect_disk_health():
    vols = as_list(ps_json(
        "Get-Volume -ErrorAction SilentlyContinue | Where-Object DriveLetter | "
        "Select-Object DriveLetter,FileSystemLabel,"
        "@{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},"
        "@{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB,1)}},"
        "HealthStatus | ConvertTo-Json -Compress"
    ) or [])
    return {"volumes": vols}


# --------------------------------------------------------------------------- #
# Microsoft Teams  (discovery-first: finds Teams rather than assuming paths)
# --------------------------------------------------------------------------- #
#
# Path/name facts verified against Microsoft docs:
#   new Teams  : MSIX package "MSTeams_8wekyb3d8bbwe";
#                executables ms-teams.exe + ms-teamsupdate.exe under
#                %ProgramFiles%\WindowsApps\MSTeams_<ver>_<arch>__8wekyb3d8bbwe
#                user data/cache: %LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe
#                MS-recommended cache reset path: ...\LocalCache\Microsoft\MSTeams
#                shared config: %LOCALAPPDATA%\Publishers\8wekyb3d8bbwe\TeamsSharedConfig
#   classic    : %APPDATA%\Microsoft\Teams (cache),
#                %LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe
# The WindowsApps folder name changes every update, so we DISCOVER it instead of
# hardcoding a version.
# --------------------------------------------------------------------------- #

def collect_teams():
    teams = {"_notes": []}

    # ---- 1. New Teams: MSIX package (the authoritative check) -------------- #
    teams["new_teams_package"] = ps_json(
        "Get-AppxPackage -Name '*MSTeams*' -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 Name,PackageFullName,Version,Architecture,"
        "InstallLocation,Status,IsFramework | ConvertTo-Json -Compress"
    )
    # Provisioned for all users (shows machine-wide deployment even if this
    # user's profile hasn't materialized it yet). Needs elevation.
    teams["new_teams_provisioned"] = ps_json(
        "try{Get-AppxProvisionedPackage -Online -ErrorAction Stop | "
        "Where-Object {$_.DisplayName -like '*MSTeams*'} | Select-Object -First 1 "
        "DisplayName,Version,PackageName | ConvertTo-Json -Compress}catch{''}"
    )

    # ---- 2. Running processes: find the REAL exe path on this machine ------ #
    teams["running_processes"] = as_list(ps_json(
        "Get-Process -Name 'ms-teams','ms-teamsupdate','Teams' "
        "-ErrorAction SilentlyContinue | Select-Object Name,Id,"
        "@{n='Path';e={$_.Path}},"
        "@{n='WorkingSetMB';e={[math]::Round($_.WorkingSet64/1MB,1)}},"
        "@{n='StartTime';e={if($_.StartTime){$_.StartTime.ToString('o')}else{''}}} "
        "| ConvertTo-Json -Compress"
    ) or [])

    # ---- 3. Filesystem discovery (bounded, never a full-disk scan) --------- #
    discovery = ps_json(r"""
$found = @()
# New Teams install dir (name changes per version - resolve by wildcard)
try {
  Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -Filter 'MSTeams_*' `
    -ErrorAction SilentlyContinue | ForEach-Object {
      $exe = Join-Path $_.FullName 'ms-teams.exe'
      $found += [pscustomobject]@{
        Kind='new-teams-install'; Path=$_.FullName;
        ExeExists=(Test-Path $exe); Modified=$_.LastWriteTime.ToString('o') }
    }
} catch {}
# Classic Teams executable
$classic = Join-Path $env:LOCALAPPDATA 'Microsoft\Teams\current\Teams.exe'
if (Test-Path $classic) {
  $v = (Get-Item $classic).VersionInfo.FileVersion
  $found += [pscustomobject]@{ Kind='classic-teams-exe'; Path=$classic;
    ExeExists=$true; Modified=$v }
}
# Start-menu shortcuts (what the user actually clicks)
foreach ($root in @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs",
                    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")) {
  if (Test-Path $root) {
    Get-ChildItem $root -Recurse -Filter '*Teams*.lnk' -ErrorAction SilentlyContinue |
      ForEach-Object {
        $found += [pscustomobject]@{ Kind='shortcut'; Path=$_.FullName;
          ExeExists=$true; Modified=$_.LastWriteTime.ToString('o') }
      }
  }
}
$found | ConvertTo-Json -Compress
""")
    teams["discovered_locations"] = as_list(discovery or [])

    # ---- 4. Cache / profile data + sizes ----------------------------------- #
    teams["data_paths"] = as_list(ps_json(r"""
$paths = @(
 @{N='new-teams-userdata'; P=(Join-Path $env:LOCALAPPDATA 'Packages\MSTeams_8wekyb3d8bbwe')},
 @{N='new-teams-localcache'; P=(Join-Path $env:LOCALAPPDATA 'Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams')},
 @{N='teams-shared-config'; P=(Join-Path $env:LOCALAPPDATA 'Publishers\8wekyb3d8bbwe\TeamsSharedConfig')},
 @{N='classic-teams-appdata'; P=(Join-Path $env:APPDATA 'Microsoft\Teams')},
 @{N='teams-meeting-addin'; P=(Join-Path $env:LOCALAPPDATA 'Microsoft\TeamsMeetingAddin')}
)
$out=@()
foreach($p in $paths){
  if(Test-Path $p.P){
    $sz = 0; $n = 0
    try {
      $items = Get-ChildItem $p.P -Recurse -File -Force -ErrorAction SilentlyContinue
      $sz = ($items | Measure-Object Length -Sum).Sum
      $n  = ($items | Measure-Object).Count
    } catch {}
    $out += [pscustomobject]@{ Name=$p.N; Path=$p.P; Exists=$true;
      SizeMB=[math]::Round(($sz/1MB),1); FileCount=$n;
      LastWrite=(Get-Item $p.P).LastWriteTime.ToString('o') }
  } else {
    $out += [pscustomobject]@{ Name=$p.N; Path=$p.P; Exists=$false;
      SizeMB=0; FileCount=0; LastWrite='' }
  }
}
$out | ConvertTo-Json -Compress
""") or [])

    # ---- 5. Teams log files (diagnostics the analyst can point at) --------- #
    teams["log_files"] = as_list(ps_json(r"""
$roots = @(
 (Join-Path $env:LOCALAPPDATA 'Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Logs'),
 (Join-Path $env:APPDATA 'Microsoft\Teams\logs.txt'),
 (Join-Path $env:USERPROFILE 'AppData\Local\Microsoft\Teams\current\Logs')
)
$out=@()
foreach($r in $roots){
  if(Test-Path $r){
    Get-ChildItem $r -File -Recurse -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 8 |
      ForEach-Object { $out += [pscustomobject]@{ Path=$_.FullName;
        SizeKB=[math]::Round($_.Length/1KB,1);
        LastWrite=$_.LastWriteTime.ToString('o') } }
  }
}
$out | ConvertTo-Json -Compress
""") or [])

    # ---- 6. Teams-specific crash/hang events (Application log) ------------- #
    teams["crash_events"] = as_list(ps_json(r"""
$s=(Get-Date).AddDays(-14)
try{
 Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000,1001,1002;StartTime=$s} `
   -MaxEvents 300 -ErrorAction Stop |
 Where-Object { $_.Message -match 'ms-teams|Teams\.exe|MSTeams' } |
 Select-Object -First 40 @{n='TimeCreated';e={$_.TimeCreated.ToString('o')}},Id,
   @{n='Provider';e={$_.ProviderName}},
   @{n='Message';e={($_.Message -split "`n")[0]}} | ConvertTo-Json -Compress
}catch{'[]'}
""") or [])

    # ---- 7. AppX deployment failures (why Teams won't install/update) ------ #
    teams["appx_errors"] = as_list(ps_json(r"""
$s=(Get-Date).AddDays(-14)
try{
 Get-WinEvent -FilterHashtable @{
   LogName='Microsoft-Windows-AppXDeploymentServer/Operational';
   Level=1,2; StartTime=$s} -MaxEvents 60 -ErrorAction Stop |
 Where-Object { $_.Message -match 'MSTeams|Teams' } |
 Select-Object -First 20 @{n='TimeCreated';e={$_.TimeCreated.ToString('o')}},Id,
   @{n='Message';e={($_.Message -split "`n")[0]}} | ConvertTo-Json -Compress
}catch{'[]'}
""") or [])

    # ---- 8. WebView2 runtime (hard prerequisite for new Teams) ------------- #
    teams["webview2"] = ps_json(r"""
$k = @(
 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
 'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
)
foreach($p in $k){ if(Test-Path $p){
  (Get-ItemProperty $p).pv | ConvertTo-Json -Compress; break } }
""")

    # ---- 9. Policy / registry blockers -------------------------------------#
    teams["policy"] = {
        "office_teams_key": run_powershell(
            r"$p='HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office\Teams';"
            r"if(Test-Path $p){(Get-ItemProperty $p | Out-String).Trim()}else{'not present'}"
        ),
        "allow_all_trusted_apps": run_powershell(
            r"$p='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock';"
            r"if(Test-Path $p){(Get-ItemProperty $p -Name AllowAllTrustedApps "
            r"-ErrorAction SilentlyContinue).AllowAllTrustedApps}else{''}"
        ),
        "autostart": as_list(ps_json(
            r"$k='HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run';"
            r"if(Test-Path $k){(Get-ItemProperty $k).PSObject.Properties | "
            r"Where-Object {$_.Name -match 'Teams' -or $_.Value -match 'teams'} | "
            r"Select-Object Name,Value | ConvertTo-Json -Compress}"
        ) or []),
    }

    # ---- 10. Outlook Teams Meeting add-in ---------------------------------- #
    teams["outlook_addin"] = run_powershell(
        r"$p='HKCU:\SOFTWARE\Microsoft\Office\Outlook\Addins\TeamsAddin.FastConnect';"
        r"if(Test-Path $p){$i=Get-ItemProperty $p;"
        r"'LoadBehavior=' + $i.LoadBehavior}else{'not installed'}"
    )

    # ---- 11. Connectivity to Teams service endpoints ----------------------- #
    teams["connectivity"] = as_list(ps_json(r"""
$targets = @('teams.microsoft.com','login.microsoftonline.com','config.teams.microsoft.com')
$out=@()
foreach($t in $targets){
  $r = $null
  try { $r = Test-NetConnection -ComputerName $t -Port 443 -WarningAction SilentlyContinue -ErrorAction Stop } catch {}
  $out += [pscustomobject]@{ Host=$t;
    TcpTestSucceeded= if($r){$r.TcpTestSucceeded}else{$false};
    RemoteAddress= if($r -and $r.RemoteAddress){$r.RemoteAddress.IPAddressToString}else{''} }
}
$out | ConvertTo-Json -Compress
""") or [])

    # ---- 12. Derived summary: is Teams installed, and which flavour? ------- #
    pkg = teams.get("new_teams_package") or {}
    has_new = bool(pkg.get("PackageFullName"))
    classic_hits = [d for d in teams["discovered_locations"]
                    if d.get("Kind") == "classic-teams-exe"]
    teams["summary"] = {
        "new_teams_installed": has_new,
        "new_teams_version": pkg.get("Version"),
        "new_teams_status": pkg.get("Status"),
        "classic_teams_present": bool(classic_hits),
        "both_installed": has_new and bool(classic_hits),
        "running": bool(teams["running_processes"]),
        "install_locations_found": [d.get("Path")
                                    for d in teams["discovered_locations"]
                                    if d.get("Kind") != "shortcut"],
    }
    if not has_new and not classic_hits:
        teams["_notes"].append(
            "No Teams installation detected (neither MSIX package nor classic exe).")
    return teams


# --------------------------------------------------------------------------- #
# WhatsApp Desktop  (diagnostics-only: process/crash/log health, NO message
# content, NO chat/contact data, NO media. Mirrors collect_teams() in shape.)
# --------------------------------------------------------------------------- #
#
# WhatsApp Desktop (Store/MSIX build) package family: "5319275A.WhatsAppDesktop"
# Executable: WhatsApp.exe
# User data root: %LOCALAPPDATA%\Packages\5319275A.WhatsAppDesktop_<suffix>
# (the publisher-id suffix can vary by build, so we discover it by wildcard
# instead of hardcoding it, same approach as the Teams collector).
# --------------------------------------------------------------------------- #

def collect_whatsapp():
    wa = {"_notes": []}

    # ---- 1. Package / install detection (MSIX, if installed via Store) ---- #
    wa["package"] = ps_json(
        "Get-AppxPackage -Name '*WhatsAppDesktop*' -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 Name,PackageFullName,Version,Architecture,"
        "InstallLocation,Status | ConvertTo-Json -Compress"
    )

    # ---- 2. Running process (real exe path + memory, no window content) --- #
    wa["running_processes"] = as_list(ps_json(
        "Get-Process -Name 'WhatsApp' -ErrorAction SilentlyContinue | "
        "Select-Object Name,Id,"
        "@{n='Path';e={$_.Path}},"
        "@{n='WorkingSetMB';e={[math]::Round($_.WorkingSet64/1MB,1)}},"
        "@{n='StartTime';e={if($_.StartTime){$_.StartTime.ToString('o')}else{''}}} "
        "| ConvertTo-Json -Compress"
    ) or [])

    # ---- 3. Filesystem discovery (bounded, install dirs + shortcuts only) - #
    discovery = ps_json(r"""
$found = @()
try {
  Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -Filter '5319275A.WhatsAppDesktop*' `
    -ErrorAction SilentlyContinue | ForEach-Object {
      $exe = Join-Path $_.FullName 'WhatsApp.exe'
      $found += [pscustomobject]@{
        Kind='whatsapp-install'; Path=$_.FullName;
        ExeExists=(Test-Path $exe); Modified=$_.LastWriteTime.ToString('o') }
    }
} catch {}
foreach ($root in @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs",
                    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")) {
  if (Test-Path $root) {
    Get-ChildItem $root -Recurse -Filter '*WhatsApp*.lnk' -ErrorAction SilentlyContinue |
      ForEach-Object {
        $found += [pscustomobject]@{ Kind='shortcut'; Path=$_.FullName;
          ExeExists=$true; Modified=$_.LastWriteTime.ToString('o') }
      }
  }
}
$found | ConvertTo-Json -Compress
""")
    wa["discovered_locations"] = as_list(discovery or [])

    # ---- 4. Data folder SIZE ONLY - no file names, no content enumeration - #
    # We deliberately do NOT list filenames (chat DB, media files) - only the
    # aggregate size/file-count of the profile folder, same privacy level as
    # the Teams collector's data_paths, for diagnosing disk-space / bloat
    # issues without touching any conversation data.
    wa["data_paths"] = as_list(ps_json(r"""
$root = Get-ChildItem "$env:LOCALAPPDATA\Packages" -Directory -Filter '5319275A.WhatsAppDesktop*' `
  -ErrorAction SilentlyContinue | Select-Object -First 1
$out = @()
if ($root) {
  $localstate = Join-Path $root.FullName 'LocalState'
  $localcache = Join-Path $root.FullName 'LocalCache'
  foreach ($p in @(@{N='whatsapp-localstate';P=$localstate},
                   @{N='whatsapp-localcache';P=$localcache})) {
    if (Test-Path $p.P) {
      $sz = 0; $n = 0
      try {
        $items = Get-ChildItem $p.P -Recurse -File -Force -ErrorAction SilentlyContinue
        $sz = ($items | Measure-Object Length -Sum).Sum
        $n  = ($items | Measure-Object).Count
      } catch {}
      $out += [pscustomobject]@{ Name=$p.N; Path=$p.P; Exists=$true;
        SizeMB=[math]::Round(($sz/1MB),1); FileCount=$n;
        LastWrite=(Get-Item $p.P).LastWriteTime.ToString('o') }
    } else {
      $out += [pscustomobject]@{ Name=$p.N; Path=$p.P; Exists=$false;
        SizeMB=0; FileCount=0; LastWrite='' }
    }
  }
}
$out | ConvertTo-Json -Compress
""") or [])

    # ---- 5. Crash/hang events (Application log, filtered to WhatsApp) ----- #
    wa["crash_events"] = as_list(ps_json(r"""
$s=(Get-Date).AddDays(-14)
try{
 Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000,1001,1002;StartTime=$s} `
   -MaxEvents 300 -ErrorAction Stop |
 Where-Object { $_.Message -match 'WhatsApp' } |
 Select-Object -First 40 @{n='TimeCreated';e={$_.TimeCreated.ToString('o')}},Id,
   @{n='Provider';e={$_.ProviderName}},
   @{n='Message';e={($_.Message -split "`n")[0]}} | ConvertTo-Json -Compress
}catch{'[]'}
""") or [])

    # ---- 6. AppX deployment failures (install/update problems) ------------ #
    wa["appx_errors"] = as_list(ps_json(r"""
$s=(Get-Date).AddDays(-14)
try{
 Get-WinEvent -FilterHashtable @{
   LogName='Microsoft-Windows-AppXDeploymentServer/Operational';
   Level=1,2; StartTime=$s} -MaxEvents 60 -ErrorAction Stop |
 Where-Object { $_.Message -match 'WhatsApp' } |
 Select-Object -First 20 @{n='TimeCreated';e={$_.TimeCreated.ToString('o')}},Id,
   @{n='Message';e={($_.Message -split "`n")[0]}} | ConvertTo-Json -Compress
}catch{'[]'}
""") or [])

    # ---- 7. Log files list (paths + sizes only, not opened/read) ---------- #
    wa["log_files"] = as_list(ps_json(r"""
$root = Get-ChildItem "$env:LOCALAPPDATA\Packages" -Directory -Filter '5319275A.WhatsAppDesktop*' `
  -ErrorAction SilentlyContinue | Select-Object -First 1
$out=@()
if ($root) {
  $logdir = Join-Path $root.FullName 'LocalState\logs'
  if (Test-Path $logdir) {
    Get-ChildItem $logdir -File -Recurse -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 8 |
      ForEach-Object { $out += [pscustomobject]@{ Path=$_.FullName;
        SizeKB=[math]::Round($_.Length/1KB,1);
        LastWrite=$_.LastWriteTime.ToString('o') } }
  }
}
$out | ConvertTo-Json -Compress
""") or [])

    # ---- 8. Derived summary ------------------------------------------------ #
    pkg = wa.get("package") or {}
    has_pkg = bool(pkg.get("PackageFullName"))
    wa["summary"] = {
        "installed": has_pkg or bool(wa["discovered_locations"]),
        "version": pkg.get("Version"),
        "status": pkg.get("Status"),
        "running": bool(wa["running_processes"]),
        "install_locations_found": [d.get("Path")
                                    for d in wa["discovered_locations"]
                                    if d.get("Kind") != "shortcut"],
    }
    if not wa["summary"]["installed"]:
        wa["_notes"].append("No WhatsApp Desktop installation detected.")
    return wa


# --------------------------------------------------------------------------- #
# Installed applications  (ALL programs on the machine, not just Teams/WhatsApp)
# --------------------------------------------------------------------------- #
#
# Sources, matching what "Apps & Features" / "Programs and Features" shows:
#   * registry Uninstall keys (per-machine 64-bit, per-machine WOW6432Node
#     32-bit, and per-user) - the canonical list of classic desktop installs
#     (this is where Chrome, Firefox/Mozilla, etc. show up).
#   * Get-AppxPackage - Store/MSIX apps (frameworks and resource packages
#     excluded, they aren't user-facing "programs").
# --------------------------------------------------------------------------- #

def collect_installed_apps():
    apps = as_list(ps_json(r"""
$paths = @(
 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$out = @()
foreach ($p in $paths) {
  Get-ItemProperty $p -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -and -not $_.SystemComponent } |
    ForEach-Object {
      $out += [pscustomobject]@{
        Name = $_.DisplayName
        Version = $_.DisplayVersion
        Publisher = $_.Publisher
        InstallDate = $_.InstallDate
        InstallLocation = $_.InstallLocation
        Source = 'registry'
      }
    }
}
try {
  Get-AppxPackage -ErrorAction SilentlyContinue |
    Where-Object { -not $_.IsFramework -and -not $_.IsResourcePackage } |
    ForEach-Object {
      $out += [pscustomobject]@{
        Name = $_.Name
        Version = $_.Version
        Publisher = $_.Publisher
        InstallDate = ''
        InstallLocation = $_.InstallLocation
        Source = 'appx'
      }
    }
} catch {}
$out | Sort-Object Name -Unique | ConvertTo-Json -Compress
""") or [])
    return {"apps": apps, "count": len(apps)}


def correlate_app_scan(installed_apps, event_logs):
    """
    For every installed app found, check whether it was actually checked
    against the collected logs, and how many matching entries turned up.
    log_hits == 0 means "checked, nothing found" - NOT "not scanned".
    """
    app_list = (installed_apps or {}).get("apps") or []
    app_errors = ((event_logs or {}).get("application") or {}).get(
        "app_errors_1000_1002") or []
    results = []
    for app in app_list:
        name = (app.get("Name") or "").strip()
        if not name:
            continue
        needle = name.lower()
        hits = [e for e in app_errors
                if needle in (e.get("Message") or "").lower()]
        results.append({
            "name": name,
            "version": app.get("Version") or "",
            "publisher": app.get("Publisher") or "",
            "source": app.get("Source") or "",
            "log_events_checked": len(app_errors),
            "log_hits": len(hits),
            "scanned": True,
        })
    results.sort(key=lambda r: r["name"].lower())
    return results


# --------------------------------------------------------------------------- #
# Local heuristics  (work offline, no API needed)
# --------------------------------------------------------------------------- #

def severity_rank(s):
    return {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(s, 5)


def analyze_locally(snap):
    """
    Rule-based findings. Each finding: id, severity, title, detail, remediation
    (a key into REMEDIATIONS, or None).
    """
    findings = []

    def add(fid, sev, title, detail, remediation=None):
        findings.append({
            "id": fid, "severity": sev, "title": title,
            "detail": detail, "remediation": remediation,
        })

    # --- Defender ---
    dfn = snap.get("defender", {}).get("status") or {}
    if dfn.get("RealTimeProtectionEnabled") is False:
        add("def-rtp", "critical", "Defender real-time protection is OFF",
            "Get-MpComputerStatus reports RealTimeProtectionEnabled = False.",
            "enable_defender_rtp")
    if dfn.get("AntivirusEnabled") is False:
        add("def-av", "critical", "Defender antivirus disabled",
            "AntivirusEnabled = False.", "enable_defender_rtp")
    sig_age = dfn.get("AntivirusSignatureAge")
    if isinstance(sig_age, int) and sig_age > 7:
        add("def-sig", "high", "Defender signatures are stale",
            f"AntivirusSignatureAge = {sig_age} days (>7).", "update_defender_sigs")

    threats = snap.get("defender", {}).get("recent_threats") or []
    if threats:
        add("def-threat", "high", f"{len(threats)} Defender detection(s) on record",
            "Historic threat detections present; review Resources for each.", None)

    # --- Firewall ---
    for prof in snap.get("security_posture", {}).get("firewall_profiles", []):
        if prof.get("Enabled") in (False, 0, "False"):
            add(f"fw-{prof.get('Name')}", "high",
                f"Firewall profile '{prof.get('Name')}' disabled",
                "Windows Firewall is off for this profile.", "enable_firewall")

    # --- SMBv1 ---
    if snap.get("security_posture", {}).get("smb1_enabled") in (True, "True", 1):
        add("smb1", "high", "SMBv1 is enabled",
            "Legacy SMBv1 is enabled — a known ransomware/lateral-movement vector.",
            "disable_smb1")

    # --- UAC ---
    if str(snap.get("security_posture", {}).get("uac_enabled")).strip() == "0":
        add("uac", "high", "UAC is disabled",
            "EnableLUA = 0. User Account Control is turned off.", "enable_uac")

    # --- RDP exposure ---
    rdp = str(snap.get("security_posture", {}).get("rdp_deny_connections")).strip()
    if rdp == "0":
        add("rdp", "medium", "RDP is enabled",
            "fDenyTSConnections = 0 (RDP accepting connections). Confirm this is "
            "intended and that NLA + firewall scoping are in place.", None)

    # --- BitLocker ---
    bl = snap.get("security_posture", {}).get("bitlocker") or []
    for v in bl:
        if v.get("ProtectionStatus") in (0, "Off", "0"):
            add(f"bl-{v.get('MountPoint')}", "medium",
                f"BitLocker off on {v.get('MountPoint')}",
                "Volume is not protected by BitLocker.", None)

    # --- Pending reboot ---
    if str(snap.get("security_posture", {}).get("pending_reboot")).strip() == "True":
        add("reboot", "low", "Reboot pending",
            "A pending reboot may be blocking update completion.", None)

    # --- Failed logons / brute force ---
    agg = snap.get("event_logs", {}).get("aggregate", {})
    tfl = agg.get("total_failed_logons", 0)
    if tfl >= 50:
        add("bruteforce", "high", f"High volume of failed logons ({tfl})",
            f"{tfl} failed-logon (4625) events in the lookback window — possible "
            "brute-force / password-spray. Review source IPs and accounts.", None)
    elif tfl >= 15:
        add("failed-logons", "medium", f"Elevated failed logons ({tfl})",
            f"{tfl} failed-logon events — above a quiet baseline.", None)

    # --- Account lockouts ---
    locks = snap.get("event_logs", {}).get("security", {}).get("account_lockouts_4740", [])
    if locks:
        add("lockouts", "medium", f"{len(locks)} account lockout(s)",
            "4740 lockout events present — correlate with the failed-logon sources.",
            None)

    # --- New accounts ---
    newacct = snap.get("event_logs", {}).get("security", {}).get("account_created_4720", [])
    if newacct:
        add("new-account", "high", f"{len(newacct)} account(s) created in window",
            "4720 account-creation events — verify each was authorized.", None)

    # --- Microsoft Teams ---
    tm = snap.get("teams", {}) or {}
    tsum = tm.get("summary", {}) or {}
    if tsum.get("new_teams_installed") or tsum.get("classic_teams_present"):
        if tsum.get("both_installed"):
            add("teams-both", "medium", "Both new and classic Teams are installed",
                "Classic Teams alongside new Teams causes duplicate notifications, "
                "meeting add-in conflicts and user confusion. Classic Teams is "
                "retired — remove it.", None)
        st = tsum.get("new_teams_status")
        if st and str(st).lower() not in ("ok", "0"):
            add("teams-pkgstatus", "high", f"Teams MSIX package status: {st}",
                "The Teams app package is not in an OK state — it may be tampered, "
                "staged, or needing repair (Reset/re-provision).", None)

        crashes = tm.get("crash_events", [])
        if len(crashes) >= 5:
            add("teams-crashloop", "high",
                f"Teams crash loop — {len(crashes)} crash/hang event(s) in 14 days",
                "Repeated Application 1000/1001/1002 events referencing Teams. "
                "Correlate with disk/NTFS events and cache size.", "clear_teams_cache")
        elif crashes:
            add("teams-crashes", "medium",
                f"{len(crashes)} Teams crash/hang event(s) in 14 days",
                "Intermittent Teams faults logged in the Application channel.",
                "clear_teams_cache")

        appx = tm.get("appx_errors", [])
        if appx:
            add("teams-appx", "high",
                f"{len(appx)} AppX deployment error(s) mentioning Teams",
                "Teams install/update is failing at the package level. Check "
                "AllowAllTrustedApps policy and the Office\\Teams registry key.",
                None)

        for p in tm.get("data_paths", []):
            if p.get("Name") in ("new-teams-userdata", "classic-teams-appdata") \
                    and (p.get("SizeMB") or 0) > 2048:
                add(f"teams-cache-{p.get('Name')}", "medium",
                    f"Teams cache is large ({p.get('SizeMB')} MB)",
                    f"{p.get('Path')} — an oversized cache causes slow starts and "
                    "sync problems.", "clear_teams_cache")

        if not tm.get("webview2"):
            add("teams-webview2", "high", "WebView2 runtime not detected",
                "New Teams requires the Microsoft Edge WebView2 Runtime. Without "
                "it the client fails to launch or renders blank.", None)

        unreachable = [c.get("Host") for c in tm.get("connectivity", [])
                       if not c.get("TcpTestSucceeded")]
        if unreachable:
            add("teams-network", "high",
                f"Cannot reach Teams endpoint(s): {', '.join(unreachable)}",
                "TCP 443 test failed — proxy, firewall or DNS is blocking Teams "
                "service endpoints. Sign-in and calls will fail.", None)

        addin = str(tm.get("outlook_addin", ""))
        if "LoadBehavior=" in addin and "LoadBehavior=3" not in addin:
            add("teams-addin", "medium",
                f"Outlook Teams Meeting add-in not active ({addin})",
                "LoadBehavior should be 3. Users cannot schedule Teams meetings "
                "from Outlook.", None)

    # --- WhatsApp Desktop (diagnostics-only) ---
    wa = snap.get("whatsapp", {}) or {}
    wsum = wa.get("summary", {}) or {}
    if wsum.get("installed"):
        st = wsum.get("status")
        if st and str(st).lower() not in ("ok", "0"):
            add("wa-pkgstatus", "high", f"WhatsApp package status: {st}",
                "The WhatsApp Desktop package is not in an OK state - may need "
                "repair or reinstall via Microsoft Store.", None)

        crashes = wa.get("crash_events", [])
        if len(crashes) >= 5:
            add("wa-crashloop", "high",
                f"WhatsApp crash loop - {len(crashes)} crash/hang event(s) in 14 days",
                "Repeated Application 1000/1001/1002 events referencing WhatsApp. "
                "Correlate with disk/NTFS events and cache size.", None)
        elif crashes:
            add("wa-crashes", "medium",
                f"{len(crashes)} WhatsApp crash/hang event(s) in 14 days",
                "Intermittent WhatsApp faults logged in the Application channel.",
                None)

        appx = wa.get("appx_errors", [])
        if appx:
            add("wa-appx", "high",
                f"{len(appx)} AppX deployment error(s) mentioning WhatsApp",
                "WhatsApp install/update is failing at the package level.", None)

        for p in wa.get("data_paths", []):
            if p.get("Name") == "whatsapp-localcache" and (p.get("SizeMB") or 0) > 2048:
                add(f"wa-cache-{p.get('Name')}", "medium",
                    f"WhatsApp cache is large ({p.get('SizeMB')} MB)",
                    f"{p.get('Path')} - an oversized cache can cause slow starts "
                    "and sync problems.", None)

    # --- Hardware / storage events ---
    hw = snap.get("event_logs", {}).get("hardware", {})
    whea = hw.get("whea_hardware_errors", [])
    if whea:
        add("whea", "critical", f"{len(whea)} WHEA hardware error(s)",
            "Windows Hardware Error Architecture logged machine-check events — "
            "possible failing CPU/RAM/PCIe or overheating. Investigate before "
            "data loss.", None)
    storage = hw.get("storage_and_disk", [])
    if storage:
        sev = "critical" if len(storage) >= 5 else "high"
        add("storage-events", sev, f"{len(storage)} disk/NTFS event(s)",
            "disk / Ntfs / storage-controller errors or warnings — a common early "
            "sign of a failing drive or filesystem corruption. Correlate with "
            "application crashes and run chkdsk / Repair-Volume.", None)

    # --- Disk space ---
    for v in snap.get("disk_health", {}).get("volumes", []):
        size = v.get("SizeGB") or 0
        free = v.get("FreeGB") or 0
        if size and free / size < 0.10:
            add(f"disk-{v.get('DriveLetter')}", "high",
                f"Low disk space on {v.get('DriveLetter')}:",
                f"{free}GB free of {size}GB (<10%).", "clear_temp")
        if v.get("HealthStatus") not in (None, "Healthy"):
            add(f"diskhealth-{v.get('DriveLetter')}", "high",
                f"Disk health warning on {v.get('DriveLetter')}:",
                f"HealthStatus = {v.get('HealthStatus')}.", None)

    findings.sort(key=lambda f: severity_rank(f["severity"]))
    return findings


# --------------------------------------------------------------------------- #
# Remediation engine  (self-repair, gated)
# --------------------------------------------------------------------------- #
#
# Each remediation:
#   risk      : "safe" (auto-applies under --apply) or "review" (always prompts)
#   needs_admin
#   desc      : what it does
#   ps_apply  : PowerShell to run when applying
#   rollback  : human-readable how-to-undo
# --------------------------------------------------------------------------- #

REMEDIATIONS = {
    "enable_firewall": {
        "risk": "safe", "needs_admin": True,
        "desc": "Enable all Windows Firewall profiles.",
        "ps_apply": "Set-NetFirewallProfile -All -Enabled True",
        "rollback": "Set-NetFirewallProfile -All -Enabled False",
    },
    "enable_defender_rtp": {
        "risk": "safe", "needs_admin": True,
        "desc": "Re-enable Defender real-time monitoring.",
        "ps_apply": "Set-MpPreference -DisableRealtimeMonitoring $false",
        "rollback": "Set-MpPreference -DisableRealtimeMonitoring $true",
    },
    "update_defender_sigs": {
        "risk": "safe", "needs_admin": True,
        "desc": "Force a Defender signature update.",
        "ps_apply": "Update-MpSignature",
        "rollback": "(signatures roll forward only; no undo needed)",
    },
    "disable_smb1": {
        "risk": "review", "needs_admin": True,
        "desc": "Disable the legacy SMBv1 protocol (may break very old NAS/printers).",
        "ps_apply": "Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force",
        "rollback": "Set-SmbServerConfiguration -EnableSMB1Protocol $true -Force",
    },
    "enable_uac": {
        "risk": "review", "needs_admin": True,
        "desc": "Re-enable User Account Control (requires reboot to take effect).",
        "ps_apply": ("Set-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\"
                     "CurrentVersion\\Policies\\System' -Name EnableLUA -Value 1"),
        "rollback": ("Set-ItemProperty ... EnableLUA -Value 0"),
    },
    "clear_teams_cache": {
        "risk": "review", "needs_admin": False,
        "desc": ("Close Teams and clear the new-Teams cache "
                 "(LocalCache\\Microsoft\\MSTeams). Backs the folder up first; "
                 "signs the user out of some settings and needs Teams restarted."),
        "ps_apply": (
            "$p = Join-Path $env:LOCALAPPDATA "
            "'Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams';"
            "if(Test-Path $p){"
            "  $bak = \"$p.bak-$(Get-Date -Format yyyyMMdd-HHmmss)\";"
            "  Get-Process ms-teams -ErrorAction SilentlyContinue | "
            "    Stop-Process -Force -ErrorAction SilentlyContinue;"
            "  Start-Sleep -Seconds 3;"
            "  Copy-Item $p $bak -Recurse -Force -ErrorAction SilentlyContinue;"
            "  Get-ChildItem $p -Force -ErrorAction SilentlyContinue | "
            "    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue;"
            "  Write-Output \"Cleared. Backup: $bak\""
            "} else { Write-Output 'New Teams cache path not present - nothing to do.' }"
        ),
        "rollback": ("Copy the .bak-<timestamp> folder created next to "
                     "LocalCache\\Microsoft\\MSTeams back over it, then restart Teams."),
    },
    "clear_temp": {
        "risk": "safe", "needs_admin": False,
        "desc": "Delete files in the current user's TEMP folder to reclaim space.",
        "ps_apply": ("Get-ChildItem $env:TEMP -Recurse -Force -ErrorAction "
                     "SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction "
                     "SilentlyContinue"),
        "rollback": "(deleted temp files are not recoverable)",
    },
}


def plan_remediations(findings):
    """Return the ordered, de-duplicated list of remediation keys to consider."""
    seen, plan = set(), []
    for f in findings:
        key = f.get("remediation")
        if key and key in REMEDIATIONS and key not in seen:
            seen.add(key)
            plan.append((key, f))
    return plan


def run_remediations(plan, apply_changes, assume_yes, admin):
    """
    Execute (or dry-run) the plan. Returns a list of action records for the report.
    """
    actions = []
    if not plan:
        log("No auto-remediable findings.", "info")
        return actions

    print()
    log(f"Remediation plan ({len(plan)} item(s)) — "
        f"{'APPLY mode' if apply_changes else 'DRY-RUN (no changes)'}",
        "warn" if apply_changes else "info")

    for key, finding in plan:
        r = REMEDIATIONS[key]
        rec = {
            "key": key, "desc": r["desc"], "risk": r["risk"],
            "for_finding": finding["title"], "rollback": r["rollback"],
            "status": "planned", "output": "",
        }
        print()
        log(f"{finding['title']}", "step")
        print(f"      Fix   : {r['desc']}")
        print(f"      Risk  : {r['risk']}   Needs admin: {r['needs_admin']}")
        print(f"      Cmd   : {r['ps_apply']}")
        print(f"      Undo  : {r['rollback']}")

        if not apply_changes:
            rec["status"] = "dry-run (would apply)"
            actions.append(rec)
            continue

        if r["needs_admin"] and not admin:
            rec["status"] = "skipped (not elevated)"
            log("Skipped — needs an elevated (Administrator) session.", "warn")
            actions.append(rec)
            continue

        # Risky changes always confirm, even with --yes for safe ones.
        must_confirm = (r["risk"] == "review") or (not assume_yes)
        if must_confirm:
            try:
                ans = input(f"      Apply this fix? [y/N] ").strip().lower()
            except EOFError:
                ans = "n"
            if ans not in ("y", "yes"):
                rec["status"] = "skipped (declined)"
                log("Skipped by operator.", "info")
                actions.append(rec)
                continue

        out = run_powershell(r["ps_apply"], timeout=180)
        rec["status"] = "applied"
        rec["output"] = out or "(no output)"
        log("Applied.", "ok")
        actions.append(rec)

    return actions


# --------------------------------------------------------------------------- #
# Sanitization (optional — strips obvious PII before sending to the API)
# --------------------------------------------------------------------------- #

def sanitize(snap):
    """
    Best-effort redaction of hostnames/usernames for privacy-sensitive clients.
    Not a guarantee — review before enabling for regulated data.
    """
    s = json.loads(json.dumps(snap))  # deep copy
    host = s.get("system", {}).get("hostname", "")
    user = s.get("system", {}).get("user", "")

    def scrub(obj):
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        if isinstance(obj, str):
            if host and host in obj:
                obj = obj.replace(host, "HOST")
            if user and user in obj:
                obj = obj.replace(user, "USER")
            return obj
        return obj

    s = scrub(s)
    if "hostname" in s.get("system", {}):
        s["system"]["hostname"] = "HOST"
    if "user" in s.get("system", {}):
        s["system"]["user"] = "USER"
    return s


# --------------------------------------------------------------------------- #
# Claude API
# --------------------------------------------------------------------------- #

def call_claude(snapshot, api_key, use_web_search=True, timeout=180):
    """
    Send the snapshot to Claude and return the analysis text (or an error dict).
    Uses only the standard library.
    """
    user_content = (
        "Analyze this Windows endpoint snapshot and produce the report described "
        "in your instructions. Snapshot JSON follows:\n\n"
        + json.dumps(snapshot, ensure_ascii=False, indent=2)
    )

    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4096,
        "system": LOG_ANALYST_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }
    if use_web_search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                          "max_uses": 5}]

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_ENDPOINT, data=data, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            pass
        return {"_error": f"HTTP {e.code}: {detail[:500]}"}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}

    # Concatenate all text blocks (there may be several with tool use).
    text = "\n".join(
        b.get("text", "") for b in payload.get("content", [])
        if b.get("type") == "text"
    ).strip()
    return {"analysis": text or "(model returned no text)",
            "stop_reason": payload.get("stop_reason"),
            "usage": payload.get("usage")}


def call_ollama(snapshot, model, host, timeout=600):
    """
    Send the snapshot to a local Ollama server and return the analysis text.
    Standard library only. No API key, no billing, runs offline.
    NOTE: local models have no live web search — external verification is limited
    to the model's own training knowledge.
    """
    user_content = (
        "Analyze this Windows endpoint snapshot and produce the report described "
        "in your instructions. For the EXTERNAL VERIFICATION section, you have no "
        "live web access — clearly label anything you state there as 'from model "
        "knowledge, verify manually' and do not invent CVE numbers or sources.\n\n"
        "Snapshot JSON follows:\n\n"
        + json.dumps(snapshot, ensure_ascii=False, indent=2)
    )
    body = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
        "messages": [
            {"role": "system", "content": LOG_ANALYST_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    data = json.dumps(body).encode("utf-8")
    url = host.rstrip("/") + "/api/chat"
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            pass
        hint = ""
        if e.code == 404:
            hint = (f" — model '{model}' not found. Run:  ollama pull {model}")
        return {"_error": f"Ollama HTTP {e.code}: {detail[:300]}{hint}"}
    except urllib.error.URLError as e:
        return {"_error": (f"Cannot reach Ollama at {host} ({e.reason}). "
                           "Is it installed and running? Try: ollama serve")}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}

    text = (payload.get("message") or {}).get("content", "").strip()
    return {"analysis": text or "(model returned no text)",
            "backend": "ollama", "model": model,
            "usage": {"input_tokens": payload.get("prompt_eval_count"),
                      "output_tokens": payload.get("eval_count")}}


def call_claude_cli(snapshot, bin_path="claude", model="", use_web_search=True,
                    timeout=600):
    """
    Analyze via the `claude` CLI (Claude Code) in headless/print mode.

    Runs on the machine that has Claude Code installed and logged in — intended
    for a central admin box, NOT every endpoint. Can use a Pro/Max subscription
    (via `claude setup-token`) so there is no per-token API bill.

    Safety: the snapshot is passed on STDIN (avoids Windows command-line length
    limits) and the agent is given NO shell/file tools — only WebSearch, and only
    if use_web_search is True. It cannot run commands on the machine.
    """
    instruction = (
        "You are given a Windows endpoint snapshot as JSON on standard input. "
        "Analyze it and produce the report described in your system instructions. "
        "Do not attempt to run any commands or read local files; work only from "
        "the JSON provided."
    )
    cmd = [
        bin_path, "-p", instruction,
        "--append-system-prompt", LOG_ANALYST_SYSTEM_PROMPT,
        "--output-format", "json",
        "--max-turns", "6" if use_web_search else "1",
        # Tightly scope tools: web search only (or nothing). Never Bash/Read/Edit.
        "--allowedTools", "WebSearch" if use_web_search else "",
    ]
    if model:
        cmd += ["--model", model]

    stdin_data = json.dumps(snapshot, ensure_ascii=False)
    try:
        proc = subprocess.run(
            cmd, input=stdin_data, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return {"_error": (
            f"'{bin_path}' not found. Install Node.js, then "
            "`npm install -g @anthropic-ai/claude-code`, then log in with "
            "`claude` (or `claude setup-token` for a subscription-backed token). "
            "This backend must run on a machine with Claude Code installed.")}
    except subprocess.TimeoutExpired:
        return {"_error": f"Claude CLI timed out after {timeout}s."}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}

    if proc.returncode != 0 and not proc.stdout:
        return {"_error": f"Claude CLI exited {proc.returncode}: "
                          f"{(proc.stderr or '').strip()[:400]}"}

    # --output-format json returns one object with result/cost/usage fields.
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        # Fall back to raw text if JSON parsing fails.
        text = (proc.stdout or "").strip()
        return {"analysis": text or "(CLI returned no text)",
                "backend": "claude_cli", "model": model or "cli-default"}

    if payload.get("is_error"):
        return {"_error": f"Claude CLI reported an error: "
                          f"{str(payload.get('result'))[:400]}"}

    usage = payload.get("usage") or {}
    return {
        "analysis": (payload.get("result") or "").strip() or "(no text)",
        "backend": "claude_cli",
        "model": model or "cli-default",
        "cost_usd": payload.get("total_cost_usd"),
        "usage": {"input_tokens": usage.get("input_tokens"),
                  "output_tokens": usage.get("output_tokens")},
    }


def run_ai_analysis(snapshot, backend, api_key, ollama_model, ollama_host,
                    cli_bin="claude", cli_model="", use_web_search=True):
    """Dispatch to the chosen AI backend. Returns the result dict."""
    if backend == "anthropic":
        return call_claude(snapshot, api_key, use_web_search=use_web_search)
    if backend == "claude_cli":
        return call_claude_cli(snapshot, bin_path=cli_bin, model=cli_model,
                               use_web_search=use_web_search)
    return call_ollama(snapshot, ollama_model, ollama_host)
# --------------------------------------------------------------------------- #

SEV_COLOR = {
    "critical": "#d32f2f", "high": "#e65100", "medium": "#f9a825",
    "low": "#2e7d32", "info": "#546e7a",
}


def esc(x):
    return html.escape(str(x), quote=True)


def _inline_md(text):
    """Inline Markdown -> HTML on already-escaped text: **bold**, `code`."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
    return text


def render_markdown(md):
    """
    Minimal, dependency-free Markdown renderer for the analyst report:
    #/##/### headings, - bullets, | tables |, --- rules, bold, inline code,
    paragraphs. Input is escaped first, so it is safe against HTML injection.
    """
    lines = esc(md).split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        # Horizontal rule
        if line.strip() in ("---", "***", "___"):
            out.append("<hr>")
            i += 1
            continue

        # Headings
        m = None
        for level, prefix in ((1, "# "), (2, "## "), (3, "### "), (4, "#### ")):
            if line.startswith(prefix):
                tag = {1: "h2", 2: "h3", 3: "h4", 4: "h5"}[level]
                out.append(f"<{tag}>{_inline_md(line[len(prefix):].strip())}</{tag}>")
                m = True
                break
        if m:
            i += 1
            continue

        # Tables: a header row of pipes followed by a --- separator row
        if line.lstrip().startswith("|") and i + 1 < n and \
                set(lines[i + 1].replace("|", "").replace(":", "").strip()) <= {"-", " "} \
                and "-" in lines[i + 1]:
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            header = cells(line)
            out.append('<table class="mdtbl"><thead><tr>'
                       + "".join(f"<th>{_inline_md(c)}</th>" for c in header)
                       + "</tr></thead><tbody>")
            i += 2
            while i < n and lines[i].lstrip().startswith("|"):
                out.append("<tr>" + "".join(f"<td>{_inline_md(c)}</td>"
                                             for c in cells(lines[i])) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        # Bullet list
        if line.lstrip().startswith(("- ", "* ")):
            out.append("<ul>")
            while i < n and lines[i].lstrip().startswith(("- ", "* ")):
                item = lines[i].lstrip()[2:].strip()
                out.append(f"<li>{_inline_md(item)}</li>")
                i += 1
            out.append("</ul>")
            continue

        # Numbered list (1. or 1) )
        import re as _re
        if _re.match(r"\d+[.)]\s", line.lstrip()):
            out.append("<ol>")
            while i < n and _re.match(r"\d+[.)]\s", lines[i].lstrip()):
                item = _re.sub(r"^\d+[.)]\s+", "", lines[i].lstrip()).strip()
                out.append(f"<li>{_inline_md(item)}</li>")
                i += 1
            out.append("</ol>")
            continue

        # Paragraph
        out.append(f"<p>{_inline_md(line.strip())}</p>")
        i += 1

    return "\n".join(out)


def generate_html_report(snap, findings, actions, claude_result, out_path):
    sysinfo = snap.get("system", {})
    scanned = sysinfo.get("scanned_at", now_iso())
    host = sysinfo.get("hostname", "unknown")

    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    badges = "".join(
        f'<span class="pill" style="background:{SEV_COLOR.get(s)}">{s.upper()}: {c}</span>'
        for s, c in sorted(counts.items(), key=lambda kv: severity_rank(kv[0]))
    ) or '<span class="pill" style="background:#2e7d32">NO ISSUES FLAGGED</span>'

    def finding_row(f):
        rem = ""
        if f.get("remediation"):
            r = REMEDIATIONS.get(f["remediation"], {})
            rem = (f'<div class="fix"><b>Auto-fix available:</b> {esc(r.get("desc",""))} '
                   f'<span class="risk">({esc(r.get("risk",""))})</span></div>')
        return f"""
        <div class="finding">
          <div class="fhead">
            <span class="dot" style="background:{SEV_COLOR.get(f['severity'])}"></span>
            <span class="ftitle">{esc(f['title'])}</span>
            <span class="fsev">{esc(f['severity'].upper())}</span>
          </div>
          <div class="fdetail">{esc(f['detail'])}</div>
          {rem}
        </div>"""

    findings_html = "".join(finding_row(f) for f in findings) or \
        '<p class="muted">No rule-based issues were flagged in this run.</p>'

    # Actions table
    if actions:
        rows = "".join(
            f"<tr><td>{esc(a['for_finding'])}</td><td>{esc(a['desc'])}</td>"
            f"<td>{esc(a['risk'])}</td><td><b>{esc(a['status'])}</b></td></tr>"
            for a in actions
        )
        actions_html = f"""<table class="tbl">
          <tr><th>Finding</th><th>Fix</th><th>Risk</th><th>Status</th></tr>{rows}
        </table>"""
    else:
        actions_html = '<p class="muted">No remediation actions were run this scan.</p>'

    # Claude analysis
    if claude_result is None:
        claude_html = ('<p class="muted">AI analysis was disabled for this run '
                       '(<code>--no-ai</code>).</p>')
    elif "_error" in claude_result:
        claude_html = (f'<p class="err">AI analysis failed: '
                       f'{esc(claude_result["_error"])}</p>')
    else:
        # Render the model text as pre-wrapped, HTML-escaped prose.
        analysis = render_markdown(claude_result.get("analysis", ""))
        usage = claude_result.get("usage") or {}
        model_used = claude_result.get("model") or CLAUDE_MODEL
        backend_used = claude_result.get("backend", "anthropic")
        cost = claude_result.get("cost_usd")
        cost_str = f' · ~${cost:.4f}' if isinstance(cost, (int, float)) else ''
        meta = (f'<p class="muted">Backend: {esc(backend_used)} · '
                f'Model: {esc(model_used)} · '
                f'in {usage.get("input_tokens","?")} / out '
                f'{usage.get("output_tokens","?")} tokens{esc(cost_str)}</p>')
        claude_html = f'{meta}<div class="ai">{analysis}</div>'

    sysinfo_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>"
        for k, v in sysinfo.items()
    )

    # Installed apps / scan coverage
    app_results = snap.get("app_scan_results") or []
    n_installed = (snap.get("installed_apps") or {}).get("count", len(app_results))
    if app_results:
        apps_rows = "".join(
            f"<tr><td>{esc(a['name'])}</td><td>{esc(a['version'])}</td>"
            f"<td>{esc(a['publisher'])}</td><td>{esc(a['source'])}</td>"
            f"<td>{'yes' if a['scanned'] else 'no'}</td>"
            f"<td>{a['log_hits']} of {a['log_events_checked']} checked</td></tr>"
            for a in app_results
        )
        apps_html = f"""
        <p class="muted">{len(app_results)} of {n_installed} installed app(s) matched
          and checked against Application-log errors (event IDs 1000/1002) from this
          run's lookback window. "0 of N" means the app WAS checked and no matching
          log entries were found — it does not mean it was skipped.</p>
        <table class="tbl">
          <tr><th>App</th><th>Version</th><th>Publisher</th><th>Source</th>
              <th>Scanned</th><th>Log hits</th></tr>
          {apps_rows}
        </table>"""
    else:
        apps_html = '<p class="muted">No installed applications were enumerated for this run.</p>'

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(APP_NAME)} — {esc(host)}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, Arial, sans-serif; margin:0;
          background:#f4f6f8; color:#1c2733; }}
  header {{ background:#11212e; color:#fff; padding:28px 40px; }}
  header h1 {{ margin:0 0 6px; font-size:22px; }}
  header .sub {{ color:#9fb3c8; font-size:13px; }}
  main {{ max-width:960px; margin:0 auto; padding:28px 24px 80px; }}
  section {{ background:#fff; border:1px solid #e2e8f0; border-radius:10px;
             padding:22px 26px; margin:18px 0; }}
  section h2 {{ margin:0 0 14px; font-size:16px; letter-spacing:.3px;
                text-transform:uppercase; color:#33475b; }}
  .pill {{ display:inline-block; color:#fff; font-size:12px; font-weight:600;
           padding:4px 10px; border-radius:20px; margin:2px 6px 2px 0; }}
  .finding {{ border-left:4px solid #cbd5e1; padding:10px 14px; margin:10px 0;
              background:#fafbfc; border-radius:0 8px 8px 0; }}
  .fhead {{ display:flex; align-items:center; gap:10px; }}
  .dot {{ width:10px; height:10px; border-radius:50%; flex:none; }}
  .ftitle {{ font-weight:600; flex:1; }}
  .fsev {{ font-size:11px; color:#64748b; font-weight:700; }}
  .fdetail {{ margin:6px 0 0 20px; color:#41505f; font-size:14px; }}
  .fix {{ margin:8px 0 0 20px; font-size:13px; color:#0b6b3a;
          background:#e9f7ef; padding:6px 10px; border-radius:6px; }}
  .risk {{ color:#8a6d00; }}
  .tbl {{ width:100%; border-collapse:collapse; font-size:14px; }}
  .tbl th, .tbl td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #eef2f6; }}
  .tbl th {{ background:#f1f5f9; }}
  .ai {{ font-size:14px; line-height:1.55;
         background:#fbfcfd; border:1px solid #eef2f6; border-radius:8px; padding:8px 18px; }}
  .ai h2 {{ font-size:17px; color:#11212e; border-bottom:2px solid #e2e8f0;
            padding-bottom:6px; margin:18px 0 10px; text-transform:none; letter-spacing:0; }}
  .ai h3 {{ font-size:15px; color:#22303c; border-bottom:1px solid #eef2f6;
            padding-bottom:4px; margin:16px 0 8px; text-transform:none; letter-spacing:0; }}
  .ai h4 {{ font-size:14px; color:#e65100; font-weight:700; margin:14px 0 4px; }}
  .ai h5 {{ font-size:13px; color:#54637a; margin:10px 0 4px; }}
  .ai ul, .ai ol {{ margin:6px 0 10px; padding-left:22px; }}
  .ai li {{ margin:3px 0; }}
  .ai p {{ margin:8px 0; }}
  .ai hr {{ border:none; border-top:1px solid #e2e8f0; margin:16px 0; }}
  .mdtbl {{ width:100%; border-collapse:collapse; font-size:13px; margin:10px 0; }}
  .mdtbl th, .mdtbl td {{ text-align:left; padding:6px 9px; border:1px solid #e6ebf1; }}
  .mdtbl th {{ background:#f1f5f9; }}
  .muted {{ color:#7a8699; font-size:14px; }}
  .err {{ color:#b3261e; }}
  code {{ background:#eef2f6; padding:1px 5px; border-radius:4px; }}
  footer {{ text-align:center; color:#93a1b0; font-size:12px; padding:20px; }}
</style></head>
<body>
<header>
  <h1>{esc(APP_NAME)}</h1>
  <div class="sub">Host: <b>{esc(host)}</b> &nbsp;·&nbsp; Scanned: {esc(scanned)}
   &nbsp;·&nbsp; v{esc(APP_VERSION)} &nbsp;·&nbsp;
   {'ELEVATED' if sysinfo.get('elevated') else 'NOT elevated'}</div>
</header>
<main>
  <section>
    <h2>Summary</h2>
    <div>{badges}</div>
    <p class="muted" style="margin-top:12px">
      {len(findings)} rule-based finding(s). {len(actions)} remediation action(s)
      recorded. AI analysis: {'included below' if claude_result and '_error' not in claude_result else 'not included'}.
    </p>
  </section>

  <section>
    <h2>AI Incident Analysis</h2>
    {claude_html}
  </section>

  <section>
    <h2>Rule-based Findings</h2>
    {findings_html}
  </section>

  <section>
    <h2>Remediation Actions</h2>
    {actions_html}
  </section>

  <section>
    <h2>Installed Applications — Scan Coverage</h2>
    {apps_html}
  </section>

  <section>
    <h2>System Inventory</h2>
    <table class="tbl">{sysinfo_rows}</table>
  </section>
</main>
<footer>Generated by {esc(APP_NAME)} v{esc(APP_VERSION)} · for internal MSP use ·
  raw data in the accompanying .json file</footer>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return out_path


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def build_snapshot(lookback_days):
    log("Collecting system inventory...", "step")
    system = safe(collect_system_info)
    log("Reading event logs...", "step")
    event_logs = safe(lambda: collect_event_logs(lookback_days))
    log("Checking Microsoft Defender...", "step")
    defender = safe(collect_defender)
    log("Checking security posture...", "step")
    posture = safe(collect_security_posture)
    log("Enumerating accounts...", "step")
    accounts = safe(collect_accounts)
    log("Enumerating services & startup...", "step")
    services = safe(collect_services_and_startup)
    log("Enumerating network listeners...", "step")
    network = safe(collect_network)
    log("Checking disk health...", "step")
    disks = safe(collect_disk_health)
    log("Locating and checking Microsoft Teams...", "step")
    teams = safe(collect_teams)
    log("Locating and checking WhatsApp Desktop...", "step")
    whatsapp = safe(collect_whatsapp)
    log("Enumerating ALL installed applications...", "step")
    installed_apps = safe(collect_installed_apps)
    app_scan_results = safe(lambda: correlate_app_scan(installed_apps, event_logs))
    n_apps = installed_apps.get("count", 0) if isinstance(installed_apps, dict) else 0
    n_scanned = len(app_scan_results) if isinstance(app_scan_results, list) else 0
    log(f"Found {n_apps} installed app(s); scanned {n_scanned} against event logs.", "ok")

    return {
        "meta": {"app": APP_NAME, "version": APP_VERSION, "generated": now_iso()},
        "system": system,
        "event_logs": event_logs,
        "defender": defender,
        "security_posture": posture,
        "accounts": accounts,
        "services": services,
        "network": network,
        "disk_health": disks,
        "teams": teams,
        "whatsapp": whatsapp,
        "installed_apps": installed_apps,
        "app_scan_results": app_scan_results,
    }


def config_path():
    """
    scanner.config.json sits NEXT TO the script/exe (not the current dir), so a
    compiled exe finds its own config wherever it's run from.
    """
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                           else os.path.abspath(__file__))
    return os.path.join(base, "scanner.config.json")


def load_config():
    """Read scanner.config.json if present. Never raises. Returns a dict."""
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
            return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def write_config_template():
    """Create a default scanner.config.json next to the exe if none exists."""
    path = config_path()
    if os.path.exists(path):
        return path
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({
                "backend": "ollama",
                "ollama_host": OLLAMA_HOST,
                "ollama_model": OLLAMA_MODEL,
                "claude_cli_bin": CLAUDE_CLI_BIN,
                "claude_cli_model": CLAUDE_CLI_MODEL,
                "api_key": ""
            }, fh, indent=2)
        return path
    except Exception:
        return None


def resolve_api_key(cli_key, cfg):
    """Priority: --api-key  >  ANTHROPIC_API_KEY env var  >  config file."""
    key = (cli_key or os.environ.get("ANTHROPIC_API_KEY")
           or cfg.get("api_key") or "").strip()
    if key.upper().startswith("PASTE"):
        return ""
    return key


def stdin_interactive():
    """True if we can prompt the user (a real console is attached)."""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except Exception:
        return False


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        return True
    except Exception:
        return False


def prompt_api_key_and_save(cfg):
    """Ask for an API key once, save it, and switch backend to anthropic."""
    print()
    print("  This build uses the Anthropic API, but no key is saved yet.")
    print("  Get one (starts with sk-ant-) at:")
    print("    https://console.anthropic.com/settings/keys")
    try:
        key = input("\n  Paste your API key (or press Enter to skip AI): ").strip()
    except EOFError:
        key = ""
    if key and not key.upper().startswith("PASTE"):
        cfg["backend"] = "anthropic"
        cfg["api_key"] = key
        if save_config(cfg):
            log("Saved. From now on, just launch — it'll run automatically.", "ok")
        return key
    return ""


def interactive_setup():
    """One-time wizard (auto-runs on first launch, or via --setup)."""
    cfg = load_config() or {}
    print(f"\n{C.B}{'='*64}{C.X}")
    print("  First-time setup — choose how the AI analysis runs")
    print(f"{C.B}{'='*64}{C.X}")
    print("   1) Anthropic API   just works, nothing to install (needs a key)")
    print("   2) Ollama          free & local (needs Ollama installed/running)")
    print("   3) Claude CLI      uses a Claude subscription on this machine")
    print("   4) No AI           rule-based findings only")
    try:
        choice = (input("\n  Choose 1-4 [1]: ").strip() or "1")
    except EOFError:
        choice = "1"

    if choice == "1":
        cfg["backend"] = "anthropic"
        try:
            key = input("  Paste your Anthropic API key: ").strip()
        except EOFError:
            key = ""
        if key and not key.upper().startswith("PASTE"):
            cfg["api_key"] = key
        else:
            log("No key entered — you can paste it on the next run.", "warn")
    elif choice == "2":
        cfg["backend"] = "ollama"
        host = input(f"  Ollama host [{cfg.get('ollama_host', OLLAMA_HOST)}]: ").strip()
        cfg["ollama_host"] = host or cfg.get("ollama_host", OLLAMA_HOST)
        model = input(f"  Model [{cfg.get('ollama_model', OLLAMA_MODEL)}]: ").strip()
        cfg["ollama_model"] = model or cfg.get("ollama_model", OLLAMA_MODEL)
    elif choice == "3":
        cfg["backend"] = "claude_cli"
    else:
        cfg["backend"] = "none"

    # Fill any missing defaults so the file is complete.
    cfg.setdefault("ollama_host", OLLAMA_HOST)
    cfg.setdefault("ollama_model", OLLAMA_MODEL)
    cfg.setdefault("claude_cli_bin", CLAUDE_CLI_BIN)
    cfg.setdefault("claude_cli_model", CLAUDE_CLI_MODEL)
    cfg.setdefault("api_key", "")
    save_config(cfg)
    log(f"Setup saved to {config_path()}", "ok")
    return cfg


def pause_if_frozen():
    """Keep the console open when double-clicked as an exe, so output is visible."""
    if getattr(sys, "frozen", False) and stdin_interactive():
        try:
            input("\nPress Enter to close...")
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} — scan, analyze, and optionally "
                    "repair a Windows endpoint.")
    p.add_argument("--out", default=None,
                   help="Output directory (default: .\\scan_<host>_<timestamp>)")
    p.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                   help=f"Event-log lookback in days (default {DEFAULT_LOOKBACK_DAYS})")
    p.add_argument("--no-ai", action="store_true",
                   help="Disable AI analysis (AI is ON by default).")
    p.add_argument("--backend", choices=["ollama", "anthropic", "claude_cli"],
                   default=None,
                   help="AI backend: ollama (local, free), anthropic (API), or "
                        "claude_cli (Claude Code, subscription-capable). "
                        "Default: ollama. Overrides the config file.")
    p.add_argument("--model", default=None,
                   help="Ollama model tag (e.g. llama3.1:8b, qwen2.5:7b).")
    p.add_argument("--ollama-host", default=None,
                   help="Ollama server URL (default http://localhost:11434).")
    p.add_argument("--cli-bin", default=None,
                   help="Path to the `claude` executable (claude_cli backend).")
    p.add_argument("--cli-model", default=None,
                   help="Model for the claude_cli backend (blank = CLI default).")
    p.add_argument("--api-key", default=None,
                   help="Anthropic API key (only for --backend anthropic).")
    p.add_argument("--no-web-search", action="store_true",
                   help="Disable web search (anthropic and claude_cli backends).")
    p.add_argument("--sanitize", action="store_true",
                   help="Redact hostname/username before sending to the model.")
    p.add_argument("--apply", action="store_true",
                   help="APPLY remediations (default is dry-run / preview only).")
    p.add_argument("--yes", action="store_true",
                   help="Auto-confirm SAFE fixes under --apply (risky ones still prompt).")
    p.add_argument("--no-repair", action="store_true",
                   help="Skip the remediation stage entirely.")
    p.add_argument("--setup", action="store_true",
                   help="Run the one-time backend/key setup wizard and exit.")
    args = p.parse_args()

    print(f"\n{C.B}{'='*64}{C.X}")
    print(f"  {APP_NAME}  v{APP_VERSION}")
    print(f"{C.B}{'='*64}{C.X}\n")

    # Explicit setup wizard.
    if args.setup:
        interactive_setup()
        pause_if_frozen()
        sys.exit(0)

    # First launch, interactive, no config yet, no backend/key forced on the CLI:
    # walk the user through a one-time choice so a plain double-click "just works".
    first_run = (not os.path.exists(config_path())
                 and not args.no_ai
                 and not args.backend
                 and not args.api_key
                 and stdin_interactive())
    if first_run:
        interactive_setup()

    if not is_windows():
        log("This scanner targets Windows. On a non-Windows host, collectors "
            "return empty and the report will be mostly blank — but it will not "
            "crash, so you can still exercise the pipeline.", "warn")

    if not is_admin() and is_windows():
        log("Not running elevated. Some checks (BitLocker, certain logs) and all "
            "repairs will be limited. Re-run as Administrator for a full scan.", "warn")

    # 1. Collect
    log("Starting scan...", "info")
    snap = build_snapshot(args.days)
    host = snap["system"].get("hostname", "host")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    out_dir = args.out or os.path.join(os.getcwd(), f"scan_{host}_{stamp}")
    os.makedirs(out_dir, exist_ok=True)

    # 2. Local heuristics
    log("Running local heuristics...", "info")
    findings = analyze_locally(snap)
    crit = [f for f in findings if f["severity"] in ("critical", "high")]
    log(f"{len(findings)} finding(s) — {len(crit)} high/critical.",
        "warn" if crit else "ok")

    # 3. AI analysis (ON by default; disable with --no-ai)
    claude_result = None
    if not args.no_ai:
        cfg = load_config()
        # Ensure a config template exists so the user can tune it later.
        write_config_template()
        backend = (args.backend or cfg.get("backend") or DEFAULT_BACKEND).lower()
        ollama_model = args.model or cfg.get("ollama_model") or OLLAMA_MODEL
        ollama_host = args.ollama_host or cfg.get("ollama_host") or OLLAMA_HOST
        cli_bin = args.cli_bin or cfg.get("claude_cli_bin") or CLAUDE_CLI_BIN
        cli_model = args.cli_model or cfg.get("claude_cli_model") or CLAUDE_CLI_MODEL

        payload = sanitize(snap) if args.sanitize else snap
        if args.sanitize:
            log("Snapshot sanitized (host/user redacted) before sending.", "info")

        if backend == "none":
            claude_result = None
            log("AI disabled in config — rule-based findings only.", "info")
        elif backend == "anthropic":
            key = resolve_api_key(args.api_key, cfg)
            if not key and stdin_interactive():
                key = prompt_api_key_and_save(cfg)  # one-time paste, then persists
            if not key:
                claude_result = {"_error": "No API key found. Run the app once with "
                                 "--setup, or set api_key in scanner.config.json."}
                log(claude_result["_error"], "err")
            else:
                log(f"Sending to Claude ({CLAUDE_MODEL}) for analysis...", "info")
                claude_result = run_ai_analysis(
                    payload, "anthropic", key, ollama_model, ollama_host,
                    use_web_search=not args.no_web_search)
        elif backend == "claude_cli":
            log(f"Analyzing via Claude CLI ({cli_bin}"
                f"{', ' + cli_model if cli_model else ''})...", "info")
            log("Uses this machine's Claude Code login/subscription.", "step")
            claude_result = run_ai_analysis(
                payload, "claude_cli", None, ollama_model, ollama_host,
                cli_bin=cli_bin, cli_model=cli_model,
                use_web_search=not args.no_web_search)
        else:
            log(f"Sending to local Ollama ({ollama_model} @ {ollama_host})...", "info")
            log("First run per model can be slow while it loads into memory.", "step")
            claude_result = run_ai_analysis(
                payload, "ollama", None, ollama_model, ollama_host)

        if claude_result and "_error" in claude_result:
            log(f"AI analysis error: {claude_result['_error']}", "err")
        elif claude_result:
            log("AI analysis received.", "ok")

    # 4. Remediation (dry-run unless --apply)
    actions = []
    if not args.no_repair:
        plan = plan_remediations(findings)
        actions = run_remediations(plan, apply_changes=args.apply,
                                   assume_yes=args.yes, admin=is_admin())

    # 5. Write outputs
    json_path = os.path.join(out_dir, "scan_data.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({"snapshot": snap, "findings": findings, "actions": actions,
                   "ai": claude_result}, fh, ensure_ascii=False, indent=2)

    html_path = os.path.join(out_dir, "report.html")
    generate_html_report(snap, findings, actions, claude_result, html_path)

    print()
    log(f"Report : {html_path}", "ok")
    log(f"Data   : {json_path}", "ok")

    # Open the report in the default browser on Windows.
    if is_windows():
        try:
            os.startfile(html_path)  # noqa
        except Exception:
            pass

    pause_if_frozen()  # keep window open when double-clicked (no effect under RMM)

    # Exit code reflects worst severity (useful for RMM scripting).
    if any(f["severity"] == "critical" for f in findings):
        sys.exit(2)
    if crit:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        try:
            if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
                input("\nPress Enter to close...")
        except Exception:
            pass
        sys.exit(3)