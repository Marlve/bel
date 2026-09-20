# Undoes install-autostart.ps1: stops Bel, removes the Startup shortcut and
# the Start menu folder.
#
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1
#
# Bel's saved state under ~/.bel is left alone unless -IncludeData is passed,
# and even then it is moved aside rather than deleted. Uninstalling is meant
# to undo what the installer did; throwing away notes-adjacent state is a
# separate decision, and timetable.ical-url in particular is not reproducible
# from anything in this repo.
#
# The repo itself is just a folder - delete it whenever, nothing outside it
# depends on it once the shortcuts are gone.

param([switch]$IncludeData)

$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'stop-bel.ps1')

$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Bel.lnk'
if (Test-Path -LiteralPath $startup) {
    Remove-Item -LiteralPath $startup -Force
    Write-Host "Removed the Startup shortcut."
} else {
    Write-Host "No Startup shortcut to remove."
}

$programs = Join-Path ([Environment]::GetFolderPath('Programs')) 'Bel'
if (Test-Path -LiteralPath $programs) {
    Remove-Item -LiteralPath $programs -Recurse -Force
    Write-Host "Removed the Start menu folder."
} else {
    Write-Host "No Start menu folder to remove."
}

# A scheduled task was how this worked before the Startup shortcut. Cleaned up
# here too, so a machine set up under the old scheme doesn't keep starting Bel
# from a task nobody remembers registering.
if (Get-ScheduledTask -TaskName 'Bel' -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName 'Bel' -Confirm:$false
    Write-Host "Removed the leftover 'Bel' scheduled task."
}

$bel = Join-Path $env:USERPROFILE '.bel'
if ($IncludeData) {
    if (Test-Path -LiteralPath $bel) {
        $moved = "$bel-removed-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss')
        Move-Item -LiteralPath $bel -Destination $moved
        Write-Host "Moved Bel's saved data to $moved"
        Write-Host "  (not deleted - it still holds timetable.ical-url and your wedge layout)"
    } else {
        Write-Host "No saved data to move."
    }
} elseif (Test-Path -LiteralPath $bel) {
    Write-Host ""
    Write-Host "Left alone: $bel"
    Write-Host "  Holds your calendar URL, wedge layout, card positions and the vault index."
    Write-Host "  To move it aside too, re-run with -IncludeData."
}

Write-Host ""
Write-Host "Bel will no longer start at logon. The repo folder can be deleted whenever."
