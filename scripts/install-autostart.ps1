# Sets up Bel to start at logon, and puts Stop/Reset in the Start menu.
# Run once:
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
#
# A shortcut in the Startup folder rather than a scheduled task, on purpose.
# Task Scheduler's defaults each kill a long-running overlay in their own way
# - a 3-day execution limit, stop-on-battery, and a "run whether logged on or
# not" mode that lands a GUI in session 0 where nothing is visible. A Startup
# shortcut has none of those, and it can be switched off from Task Manager >
# Startup apps without typing anything.

$ErrorActionPreference = 'Stop'

$launcher = Join-Path $PSScriptRoot 'start-bel.ps1'
if (-not (Test-Path -LiteralPath $launcher)) { throw "launcher missing: $launcher" }

$shell = New-Object -ComObject WScript.Shell

function New-Lnk($path, $target, $arguments, $description, $windowStyle) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $target
    $lnk.Arguments = $arguments
    $lnk.WorkingDirectory = Split-Path -Parent $PSScriptRoot
    $lnk.Description = $description
    $lnk.WindowStyle = $windowStyle
    $lnk.Save()
}

$hidden = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $launcher

# 1. Start at logon.
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Bel.lnk'
New-Lnk $startup 'powershell.exe' $hidden 'Starts the Bel desktop overlay.' 7   # 7 = minimized

# 2. Stop / Reset / Start / Uninstall, searchable from the Start menu.
$programs = Join-Path ([Environment]::GetFolderPath('Programs')) 'Bel'
foreach ($name in 'Stop', 'Reset', 'Start', 'Uninstall') {
    New-Lnk (Join-Path $programs "$name Bel.lnk") (Join-Path $PSScriptRoot "$name Bel.bat") '' "$name Bel." 1
}

Write-Host "Bel now starts at logon."
Write-Host "  Startup shortcut : $startup"
Write-Host "  Start menu       : $programs"
Write-Host "  Turn autostart off: Task Manager > Startup apps > Bel > Disable"
Write-Host "  Log              : $env:USERPROFILE\.bel\startup.log"
