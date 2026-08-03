# Relaunch a preprocessing sweep after a reboot.
#
#   .\sweep.ps1                  # P0, worker count sized to free RAM
#   .\sweep.ps1 -Descriptive     # P1 descriptive-variant band power
#   .\sweep.ps1 -Status          # report progress and exit
#   .\sweep.ps1 -Workers 1       # force a count (still refuses if RAM is short)
#
# Safe to run any time. Completed subject-sessions are skipped, so this resumes
# rather than restarts; running it twice by accident wastes nothing.
#
# Worker count is DERIVED FROM FREE MEMORY, not fixed. On 2026-08-03 four
# concurrent workers bugchecked this machine with DIRTY_NOWRITE_PAGES_CONGESTION
# (0xFD) -- the memory manager could not flush dirty pages fast enough. Each
# worker peaks near 1.3 GB, and this machine idles with only ~2 GB free because
# other applications hold most of it, so a fixed count is unsafe by
# construction: what is spare changes over the hours a sweep takes.
#
# The workers additionally refuse to begin any subject-session below
# RESERVE_GB free (src/preprocess/resources.py), so this is a second line of
# defence rather than the only one.

param(
    [int]$Workers = 0,          # 0 = derive from free memory
    [switch]$Descriptive,
    [switch]$Status
)

# Memory per worker at peak, and headroom left for the OS write-back cache.
$PerWorkerGB = 1.6
$ReserveGB = 3.0

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$derived = Join-Path $root "data\derived\P0"

function Show-Progress {
    $done = @(Get-ChildItem "$derived\*_cov.npz" -ErrorAction SilentlyContinue)
    Write-Host "P0 (ML variant, decoding)  : $($done.Count) / 87"

    $descDir = Join-Path $root "data\derived\P1_descriptive"
    $desc = @(Get-ChildItem "$descDir\*_power.json" -ErrorAction SilentlyContinue)
    if (Test-Path $descDir) {
        Write-Host "P1 descriptive (band power): $($desc.Count) / 87"
    }

    $running = @(Get-Process python -ErrorAction SilentlyContinue |
                 Where-Object { $_.WorkingSet64 -gt 100MB })
    Write-Host "workers running: $($running.Count)"
    foreach ($p in $running) {
        $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine
        $r = if ($cl -match '--subjects\s+(\d+)\s+(\d+)') { $Matches[1] + '-' + $Matches[2] } else { '?' }
        $wall = ((Get-Date) - $p.StartTime).TotalMinutes
        Write-Host ("  PID {0}: subjects {1}, {2} MB, wall {3:N0} min" -f `
                    $p.Id, $r, [math]::Round($p.WorkingSet64 / 1MB), $wall)
    }
    $free = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2)
    Write-Host "free RAM: $free GB"
}

if ($Status) { Show-Progress; return }

$existing = @(Get-Process python -ErrorAction SilentlyContinue |
              Where-Object { $_.WorkingSet64 -gt 100MB })
if ($existing.Count -gt 0) {
    Write-Host "$($existing.Count) worker(s) already running; not starting more."
    Show-Progress
    return
}

# Size the worker count to what is actually free right now, never to the core
# count. Fixed concurrency is what crashed the machine.
$freeGB = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
$affordable = [math]::Floor(($freeGB - $ReserveGB) / $PerWorkerGB)
if ($affordable -lt 1) {
    Write-Host ("Only {0:N2} GB free. Need {1:N1} GB reserve + {2:N1} GB per worker." -f `
                $freeGB, $ReserveGB, $PerWorkerGB)
    Write-Host "Close something (a browser, or an MCP server holding several GB) and retry."
    Write-Host "Nothing was started -- this is the check that prevents another 0xFD crash."
    return
}
$affordable = [math]::Min($affordable, 4)

if ($Workers -gt 0) {
    if ($Workers -gt $affordable) {
        Write-Host ("Requested {0} workers but only {1} fit in {2:N2} GB free; using {1}." -f `
                    $Workers, $affordable, $freeGB)
        $Workers = $affordable
    }
} else {
    $Workers = $affordable
}
Write-Host ("{0:N2} GB free -> {1} worker(s)" -f $freeGB, $Workers)

# One worker per contiguous subject block. Each subject-session is independent
# and seeds are fixed in config.yaml, so splitting changes nothing about the
# results -- only how long it takes.
$module = if ($Descriptive) { "src.preprocess.descriptive" } else { "src.preprocess.run" }
$first, $last = 1, 29
$size = [math]::Ceiling(($last - $first + 1) / $Workers)
$blocks = @()
for ($s = $first; $s -le $last; $s += $size) {
    $blocks += , @($s, [math]::Min($s + $size - 1, $last))
}

$env:OMP_NUM_THREADS = "2"
$env:MKL_NUM_THREADS = "2"

$i = 0
foreach ($b in $blocks) {
    $tag = [char](65 + $i)
    Start-Process -FilePath $py `
        -ArgumentList "-m", $module, "--quiet", "--subjects", $b[0], $b[1] `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root "outputs\logs\sweep_$tag.log") `
        -RedirectStandardError  (Join-Path $root "outputs\logs\sweep_$tag.err") | Out-Null
    Write-Host "worker ${tag}: subjects $($b[0])-$($b[1])  [$module]"
    $i++
    # Stagger: every worker loads raw 500 Hz data at startup, before resampling
    # halves it. Launching together spikes memory and can drive the machine into
    # swap; 20 s apart keeps the peaks from coinciding.
    if ($i -lt $blocks.Count) { Start-Sleep -Seconds 20 }
}

Write-Host ""
Show-Progress
Write-Host ""
Write-Host "Workers are detached and survive closing this terminal, but NOT a"
Write-Host "reboot or sleep. Re-run .\sweep.ps1 after the machine restarts."
