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
    [int]$First = 1,            # subject range, inclusive -- lets a pilot run
    [int]$Last = 29,            # a subset before committing to all 29
    [switch]$Descriptive,
    [switch]$Status,
    [switch]$Watch,             # live progress, redrawn until Ctrl+C
    [int]$Every = 20            # -Watch refresh interval, seconds
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

function Get-Done {
    param([int]$f, [int]$l, [bool]$desc)
    $n = 0
    for ($s = $f; $s -le $l; $s++) {
        for ($ses = 1; $ses -le 3; $ses++) {
            $p = if ($desc) {
                Join-Path $root ("data\derived\P1_descriptive\sub-{0:D2}_ses-S{1}_power.json" -f $s, $ses)
            } else {
                Join-Path $root ("data\derived\P0\sub-{0:D2}_ses-S{1}_cov.npz" -f $s, $ses)
            }
            if (Test-Path $p) { $n++ }
        }
    }
    return $n
}

function Show-Watch {
    param([int]$f, [int]$l, [bool]$desc, [int]$every)

    $total = ($l - $f + 1) * 3
    $label = if ($desc) { "P1 descriptive (band power)" } else { "P0 (ML variant)" }
    $startDone = Get-Done $f $l $desc
    $startTime = Get-Date

    while ($true) {
        $done = Get-Done $f $l $desc
        $pct = if ($total) { 100.0 * $done / $total } else { 0 }
        $width = 34
        $fill = [math]::Round($width * $pct / 100)
        $bar = ('#' * $fill) + ('.' * ($width - $fill))

        $running = @(Get-Process python -ErrorAction SilentlyContinue |
                     Where-Object { $_.WorkingSet64 -gt 100MB })
        $free = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB

        # Rate from work done since this watch started -- an ETA from the whole
        # history would be wrong after any pause, crash or reboot.
        $elapsed = ((Get-Date) - $startTime).TotalMinutes
        $delta = $done - $startDone
        $eta = if ($delta -gt 0 -and $elapsed -gt 0) {
            $perSession = $elapsed / $delta
            $mins = ($total - $done) * $perSession
            if ($mins -lt 90) { "{0:N0} min" -f $mins } else { "{0:N1} h" -f ($mins / 60) }
        } else { "--" }

        Clear-Host
        Write-Host "  $label   subjects $f-$l" -ForegroundColor Cyan
        Write-Host ""
        Write-Host ("  [$bar] {0}/{1}  {2:N1}%" -f $done, $total, $pct)
        Write-Host ""
        Write-Host ("  workers  : {0}" -f $running.Count)
        foreach ($p in $running) {
            $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine
            $r = if ($cl -match '--subjects\s+(\d+)\s+(\d+)') { $Matches[1] + '-' + $Matches[2] } else { '?' }
            Write-Host ("             subjects {0,-6} {1,5:N0} MB   {2,4:N0} min" -f `
                        $r, ($p.WorkingSet64 / 1MB), ((Get-Date) - $p.StartTime).TotalMinutes)
        }
        $memColour = if ($free -lt 2.0) { "Red" } elseif ($free -lt 3.5) { "Yellow" } else { "Gray" }
        Write-Host ("  free RAM : {0:N2} GB" -f $free) -ForegroundColor $memColour
        Write-Host ("  done this session: {0}   ETA: {1}" -f $delta, $eta)
        Write-Host ""

        if ($done -ge $total) {
            Write-Host "  COMPLETE" -ForegroundColor Green
            return
        }
        if ($running.Count -eq 0) {
            Write-Host "  No workers running -- relaunch with:" -ForegroundColor Yellow
            $flag = if ($desc) { " -Descriptive" } else { "" }
            Write-Host "    .\sweep.ps1$flag -First $f -Last $l" -ForegroundColor Yellow
            return
        }
        Write-Host "  Ctrl+C to stop watching (workers keep running)" -ForegroundColor DarkGray
        Start-Sleep -Seconds $every
    }
}

if ($Watch) { Show-Watch $First $Last ([bool]$Descriptive) $Every; return }
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
$size = [math]::Ceiling(($Last - $First + 1) / $Workers)
$blocks = @()
for ($s = $First; $s -le $Last; $s += $size) {
    $blocks += , @($s, [math]::Min($s + $size - 1, $Last))
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
