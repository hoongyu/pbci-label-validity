# Keep a preprocessing sweep alive until it is actually finished.
#
#   .\supervise.ps1 -Descriptive -First 1 -Last 29
#
# Why this exists: on 2026-08-06 a descriptive worker died after 10 of 87
# sessions with an EMPTY stderr -- no traceback, no InsufficientMemory, just
# gone. An empty stderr means Python did not raise; the process was terminated
# from outside, which under sustained memory pressure is what Windows does. The
# sweep then sat idle for hours looking like it was working.
#
# The per-session memory guard in src/preprocess/resources.py prevents the
# machine from being driven into a bugcheck, but it cannot protect a worker
# against being killed. Nothing did. This does.
#
# It deliberately does NOT bypass the memory guard: each restarted worker still
# refuses to begin a session below the reserve and waits for it. This only
# ensures that a worker which dies gets replaced.

param(
    [int]$First = 1,
    [int]$Last = 29,
    [switch]$Descriptive,
    [int]$PollSeconds = 120,
    [int]$MaxRestarts = 50
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$module = if ($Descriptive) { "src.preprocess.descriptive" } else { "src.preprocess.run" }
$dir = if ($Descriptive) { "P1_published" } else { "P0" }
$pattern = if ($Descriptive) { "_power.json" } else { "_cov.npz" }

function Get-Done {
    $n = 0
    for ($s = $First; $s -le $Last; $s++) {
        for ($ses = 1; $ses -le 3; $ses++) {
            $p = Join-Path $root ("data\derived\{0}\sub-{1:D2}_ses-S{2}{3}" -f $dir, $s, $ses, $pattern)
            if (Test-Path $p) { $n++ }
        }
    }
    return $n
}

function Get-Worker {
    return @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -like "*$module*" -and $_.CommandLine -like "*--subjects*" })
}

$total = ($Last - $First + 1) * 3
$env:OMP_NUM_THREADS = "2"
$env:MKL_NUM_THREADS = "2"
$restarts = 0
$startedAt = Get-Date

Write-Host "supervising $module, subjects $First-$Last ($total sessions)"
Write-Host "poll every $PollSeconds s, up to $MaxRestarts restarts. Ctrl+C stops supervising"
Write-Host "(a running worker is left alive; re-run this to resume supervising)."
Write-Host ""

# Heartbeat, because the log was previously written only on a restart: a
# supervisor that is alive and one that died hours ago look identical when
# nothing needs restarting. It also records free memory, which is what actually
# governs whether the sweep is moving -- measured per-session times swing
# between 10 min on an idle machine and 157 min under pressure.
$lastBeat = (Get-Date).AddMinutes(-999)
$BeatMinutes = 30

while ($true) {
    $done = Get-Done
    if (((Get-Date) - $lastBeat).TotalMinutes -ge $BeatMinutes) {
        $free = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
        $alive = (Get-Worker).Count
        Write-Host ("[{0:HH:mm}] alive: {1}/{2} done, {3} worker(s), {4:N2} GB free" -f `
                    (Get-Date), $done, $total, $alive, $free)
        $lastBeat = Get-Date
    }
    if ($done -ge $total) {
        Write-Host ("[{0:HH:mm}] COMPLETE {1}/{2} after {3:N1} h, {4} restart(s)" -f `
                    (Get-Date), $done, $total, ((Get-Date) - $startedAt).TotalHours, $restarts)
        break
    }

    $worker = Get-Worker
    if ($worker.Count -eq 0) {
        if ($restarts -ge $MaxRestarts) {
            Write-Host "[$(Get-Date -f HH:mm)] hit MaxRestarts ($MaxRestarts); stopping. Something is wrong."
            break
        }
        $restarts++
        Start-Process -FilePath $py `
            -ArgumentList "-m", $module, "--quiet", "--subjects", $First, $Last `
            -WorkingDirectory $root -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $root "outputs\logs\sweep_A.log") `
            -RedirectStandardError  (Join-Path $root "outputs\logs\sweep_A.err") | Out-Null
        Write-Host ("[{0:HH:mm}] {1}/{2} done, no worker -> started one (restart #{3})" -f `
                    (Get-Date), $done, $total, $restarts)
        # Give it time to load MNE and claim memory before the next poll, so a
        # slow start is not mistaken for a death and restarted twice.
        Start-Sleep -Seconds 60
    }
    Start-Sleep -Seconds $PollSeconds
}
