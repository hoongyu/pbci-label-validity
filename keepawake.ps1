# Keep the machine awake for the duration of a sweep, then stop.
#
#   .\keepawake.ps1 -Hours 8      # hold the system awake for 8 h, then release
#
# Why this exists: a detached sweep worker survives closing its terminal but
# NOT the machine sleeping. This machine's AC standby timeout is 60 minutes, so
# an overnight sweep would run for one hour and then die silently -- the single
# most likely way to lose a night of compute.
#
# This deliberately does NOT change the power plan. `powercfg /change
# standby-timeout-ac 0` would work but is a permanent system setting that
# someone has to remember to undo. SetThreadExecutionState is a *runtime
# request*: it lasts only while this process lives, expires on its own after
# -Hours, and is released if the process is killed. Nothing to remember, and
# nothing left behind if the machine reboots.
#
# ES_SYSTEM_REQUIRED keeps the system running; the display is deliberately NOT
# held, so the screen still turns off and saves power.
#
# To release early, just kill this process (its PID is printed at startup).

param(
    [double]$Hours = 8.0
)

$ErrorActionPreference = "Stop"

Add-Type -Namespace Win32 -Name Power -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

# Written in decimal on purpose: Windows PowerShell 5.1 parses the hex literal
# 0x80000000 as Int32, which overflows to -2147483648 and then refuses to cast
# to UInt32. 2147483648 is unambiguous.
$ES_CONTINUOUS       = [uint32]2147483648    # 0x80000000
$ES_SYSTEM_REQUIRED  = [uint32]1             # 0x00000001

$deadline = (Get-Date).AddHours($Hours)
Write-Host ("keepawake PID $PID : holding the system awake until {0:HH:mm} " -f $deadline)
Write-Host "(display may still sleep). Kill this process to release early."

try {
    while ((Get-Date) -lt $deadline) {
        # Re-assert periodically rather than once: the flag is per-thread, and
        # re-asserting also means a hung loop cannot silently keep the machine
        # awake past the deadline.
        $r = [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
        if ($r -eq 0) { Write-Host "SetThreadExecutionState failed; machine may sleep." }
        Start-Sleep -Seconds 60
    }
}
finally {
    # Release the request so normal power management resumes immediately,
    # including when this process is killed or the deadline passes.
    [void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS)
    Write-Host "keepawake released; normal sleep behaviour restored."
}
