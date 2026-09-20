# Registers the "Bel" scheduled task, so Bel starts at logon. Run once:
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
#
# No admin rights needed - the task is registered for the current user only.
# To undo:  Unregister-ScheduledTask -TaskName Bel -Confirm:$false

$ErrorActionPreference = 'Stop'

$launcher = Join-Path $PSScriptRoot 'start-bel.ps1'
if (-not (Test-Path -LiteralPath $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $launcher)

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
# ExecutionTimeLimit defaults to 3 days, after which the scheduler kills the
# task - Bel would disappear mid-week with nothing to show why. Zero disables
# the limit. DontStopIfGoingOnBatteries matters for the same reason on a
# laptop: the default stops the task when the charger comes out.

# Interactive, not "whether logged on or not": a task running as a service
# lands in session 0, where a Qt overlay draws to a desktop nobody can see.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'Bel' `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'Starts the Bel desktop overlay at logon (scripts/start-bel.ps1).' `
    -Force | Out-Null

Write-Host "Registered scheduled task 'Bel'."
Write-Host "  Run now:   Start-ScheduledTask -TaskName Bel"
Write-Host "  Status:    Get-ScheduledTaskInfo -TaskName Bel"
Write-Host "  Remove:    Unregister-ScheduledTask -TaskName Bel -Confirm:`$false"
Write-Host "  Log:       $env:USERPROFILE\.bel\startup.log"
