<#
.SYNOPSIS
  CPU/RAM monitor for the AGENT_665956_V10_15_3_RW EDR/AV agent - pure
  PowerShell, nothing else needed (no Python, no internet, no Notepad).

.DESCRIPTION
  Run with no -Name to just list current processes (use this before AND
  after installing the agent, to spot which process is new).

  Run with -Name to start logging CPU%/RAM of matching process(es) to a
  JSON file every -IntervalSeconds, until -DurationSeconds elapses or you
  press Ctrl+C.

.EXAMPLE
  .\monitor_av_resources.ps1
  (lists processes so you can find the agent's name)

.EXAMPLE
  .\monitor_av_resources.ps1 -Name agent -IntervalSeconds 2 -DurationSeconds 3600 -OutputPath usage.json

.EXAMPLE
  # No file at all needed - you can select this whole script's text and
  # paste it directly into an open PowerShell window, then on the next
  # line call:
  Watch-AvResources -Name agent -IntervalSeconds 2
#>

[CmdletBinding()]
param(
    [string[]]$Name,
    [double]$IntervalSeconds = 2,
    [double]$DurationSeconds = 0,
    [string]$OutputPath = "av_resource_usage.json"
)

function Get-MatchingProcesses {
    param([string[]]$Patterns)
    Get-Process | Where-Object {
        $procName = $_.ProcessName
        $procPath = $null
        try { $procPath = $_.Path } catch { }
        $hit = $false
        foreach ($pat in $Patterns) {
            if ($procName -like "*$pat*") { $hit = $true; break }
            if ($procPath -and $procPath -like "*$pat*") { $hit = $true; break }
        }
        $hit
    }
}

function Watch-AvResources {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string[]]$Name,
        [double]$IntervalSeconds = 2,
        [double]$DurationSeconds = 0,
        [string]$OutputPath = "av_resource_usage.json"
    )

    $logicalCpus = [Environment]::ProcessorCount
    $cpuTimeBaseline = @{}   # pid -> last seen TotalProcessorTime in seconds

    $initial = Get-MatchingProcesses -Patterns $Name
    if (-not $initial) {
        Write-Host "No matching process yet - will keep checking every interval until one appears (start the agent now if you haven't)." -ForegroundColor Yellow
    }
    foreach ($p in $initial) {
        try { $cpuTimeBaseline[$p.Id] = $p.CPU } catch { $cpuTimeBaseline[$p.Id] = 0 }
    }

    $samples = New-Object System.Collections.Generic.List[object]
    $start = Get-Date
    $lastSampleTime = $start

    $durationText = if ($DurationSeconds -gt 0) { "for $DurationSeconds s" } else { "until Ctrl+C" }
    Write-Host "Watching for: $($Name -join ', ')"
    Write-Host "Logging every $IntervalSeconds s to $OutputPath, $durationText."

    try {
        while ($true) {
            Start-Sleep -Seconds $IntervalSeconds
            $now = Get-Date
            $elapsedSinceLast = ($now - $lastSampleTime).TotalSeconds
            $lastSampleTime = $now

            $current = Get-MatchingProcesses -Patterns $Name
            $perProc = @()
            $totalCpuPct = 0.0
            $totalRssMb = 0.0

            foreach ($p in $current) {
                $cpuPct = 0.0
                $rssMb = 0.0
                $threads = 0
                try {
                    $curCpu = $p.CPU
                    if ($null -eq $curCpu) { $curCpu = 0 }
                    if ($cpuTimeBaseline.ContainsKey($p.Id) -and $elapsedSinceLast -gt 0) {
                        $cpuPct = [Math]::Round((($curCpu - $cpuTimeBaseline[$p.Id]) / $elapsedSinceLast) * 100, 2)
                        if ($cpuPct -lt 0) { $cpuPct = 0.0 }
                    }
                    $cpuTimeBaseline[$p.Id] = $curCpu
                } catch {
                    # Some EDR/AV agents run as Protected Process Light (PPL) and
                    # deny even admin reads of CPU/handles - that's the product's
                    # own self-defense, not a bug in this script.
                }
                try { $rssMb = [Math]::Round($p.WorkingSet64 / 1MB, 2) } catch { }
                try { $threads = $p.Threads.Count } catch { }

                $perProc += [ordered]@{
                    pid          = $p.Id
                    name         = $p.ProcessName
                    cpu_percent  = $cpuPct
                    rss_mb       = $rssMb
                    num_threads  = $threads
                }
                $totalCpuPct += $cpuPct
                $totalRssMb  += $rssMb
            }

            $currentIds = $current | ForEach-Object { $_.Id }
            foreach ($k in @($cpuTimeBaseline.Keys)) {
                if ($currentIds -notcontains $k) { $cpuTimeBaseline.Remove($k) }
            }

            $sysCpuPct = $null
            try {
                $cpuLoad = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
                $sysCpuPct = [Math]::Round([double]$cpuLoad.PercentProcessorTime, 2)
            } catch { }

            $ramUsedMb = $null; $ramTotalMb = $null; $ramUsedPct = $null
            try {
                $os = Get-CimInstance Win32_OperatingSystem
                $ramTotalMb = [Math]::Round($os.TotalVisibleMemorySize / 1KB, 2)
                $ramUsedMb  = [Math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1KB, 2)
                $ramUsedPct = [Math]::Round(($ramUsedMb / $ramTotalMb) * 100, 2)
            } catch { }

            $entry = [ordered]@{
                timestamp  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                elapsed_s  = [Math]::Round(($now - $start).TotalSeconds, 1)
                target     = [ordered]@{
                    processes                 = $perProc
                    process_count             = $perProc.Count
                    cpu_percent_sum           = [Math]::Round($totalCpuPct, 2)
                    cpu_percent_of_all_cores  = [Math]::Round($totalCpuPct / $logicalCpus, 2)
                    rss_mb_sum                = [Math]::Round($totalRssMb, 2)
                }
                system     = [ordered]@{
                    cpu_percent      = $sysCpuPct
                    ram_used_mb      = $ramUsedMb
                    ram_total_mb     = $ramTotalMb
                    ram_used_percent = $ramUsedPct
                }
            }
            $samples.Add($entry)

            $out = [ordered]@{
                target_name_patterns = $Name
                interval_s            = $IntervalSeconds
                logical_cpus          = $logicalCpus
                samples                = $samples
            }
            ($out | ConvertTo-Json -Depth 8) | Set-Content -Path $OutputPath -Encoding UTF8

            "[{0,7:N1}s] procs={1} cpu%={2,6:N1} ram={3,8:N1}MB" -f `
                $entry.elapsed_s, $perProc.Count, $entry.target.cpu_percent_sum, $entry.target.rss_mb_sum |
                Write-Host

            if ($DurationSeconds -gt 0 -and $entry.elapsed_s -ge $DurationSeconds) { break }
        }
    }
    finally {
        if ($samples.Count -gt 0) {
            $cpuVals = $samples | ForEach-Object { $_.target.cpu_percent_sum }
            $ramVals = $samples | ForEach-Object { $_.target.rss_mb_sum }
            $summary = [ordered]@{
                cpu_percent_sum = [ordered]@{
                    min = ($cpuVals | Measure-Object -Minimum).Minimum
                    max = ($cpuVals | Measure-Object -Maximum).Maximum
                    avg = [Math]::Round((($cpuVals | Measure-Object -Average).Average), 2)
                }
                ram_mb_sum = [ordered]@{
                    min = ($ramVals | Measure-Object -Minimum).Minimum
                    max = ($ramVals | Measure-Object -Maximum).Maximum
                    avg = [Math]::Round((($ramVals | Measure-Object -Average).Average), 2)
                }
                sample_count = $samples.Count
                duration_s   = $samples[$samples.Count - 1].elapsed_s
            }
            $out = [ordered]@{
                target_name_patterns = $Name
                interval_s            = $IntervalSeconds
                logical_cpus          = $logicalCpus
                summary                = $summary
                samples                = $samples
            }
            ($out | ConvertTo-Json -Depth 8) | Set-Content -Path $OutputPath -Encoding UTF8

            Write-Host ""
            Write-Host "--- Summary ---"
            Write-Host ("Samples: {0}  Duration: {1}s" -f $summary.sample_count, $summary.duration_s)
            Write-Host ("CPU% sum: min={0} avg={1} max={2}" -f $summary.cpu_percent_sum.min, $summary.cpu_percent_sum.avg, $summary.cpu_percent_sum.max)
            Write-Host ("RAM MB sum: min={0} avg={1} max={2}" -f $summary.ram_mb_sum.min, $summary.ram_mb_sum.avg, $summary.ram_mb_sum.max)
            Write-Host "Full log written to $OutputPath"
        } else {
            Write-Host "No samples collected."
        }
    }
}

# --- entry point when run as a script (not dot-sourced) -------------------
if ($MyInvocation.InvocationName -ne '.') {
    if (-not $Name -or $Name.Count -eq 0) {
        Write-Host "No -Name given - listing running processes so you can find the agent's name." -ForegroundColor Cyan
        Write-Host "Run this once BEFORE installing the agent and once AFTER, and compare what's new.`n" -ForegroundColor Cyan
        "{0,-8} {1,-30} {2}" -f "PID", "NAME", "PATH" | Write-Host
        Get-Process | Sort-Object ProcessName | ForEach-Object {
            "{0,-8} {1,-30} {2}" -f $_.Id, $_.ProcessName, $_.Path
        } | Write-Host
        Write-Host "`nOnce you know the name, re-run:" -ForegroundColor Yellow
        Write-Host "  .\monitor_av_resources.ps1 -Name 'part_of_name' -IntervalSeconds 2 -DurationSeconds 3600 -OutputPath usage.json" -ForegroundColor Yellow
    } else {
        Watch-AvResources -Name $Name -IntervalSeconds $IntervalSeconds -DurationSeconds $DurationSeconds -OutputPath $OutputPath
    }
}
