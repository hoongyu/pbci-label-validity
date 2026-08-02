# Relaunch the P0 preprocessing sweep after a reboot.
#
#   .\sweep.ps1            # 4 workers (default)
#   .\sweep.ps1 -Workers 2 # fewer, if RAM is tight
#   .\sweep.ps1 -Status    # just report progress and exit
#
# Safe to run any time. Completed subject-sessions are skipped, so this resumes
# rather than restarts; running it twice by accident wastes nothing.

param(
    [int]$Workers = 4,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$derived = Join-Path $root "data\derived\P0"

function Show-Progress {
    $done = @(Get-ChildItem "$derived\*_cov.npz" -ErrorAction SilentlyContinue)
    Write-Host "derived subject-sessions: $($done.Count) / 87"
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

# One worker per contiguous subject block. Each subject-session is independent
# and seeds are fixed in config.yaml, so splitting changes nothing about the
# results -- only how long it takes.
$blocks = switch ($Workers) {
    1 { @(@(1, 29)) }
    2 { @(@(1, 15), @(16, 29)) }
    3 { @(@(1, 10), @(11, 20), @(21, 29)) }
    default { @(@(6, 11), @(12, 17), @(18, 23), @(24, 29)) }
}

$env:OMP_NUM_THREADS = "2"
$env:MKL_NUM_THREADS = "2"

$i = 0
foreach ($b in $blocks) {
    $tag = [char](65 + $i)
    Start-Process -FilePath $py `
        -ArgumentList "-m", "src.preprocess.run", "--quiet", "--subjects", $b[0], $b[1] `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root "outputs\logs\sweep_$tag.log") `
        -RedirectStandardError  (Join-Path $root "outputs\logs\sweep_$tag.err") | Out-Null
    Write-Host "worker ${tag}: subjects $($b[0])-$($b[1])"
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
