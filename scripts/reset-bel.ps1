# Puts Bel back to a clean start: stop it, move its throwaway state aside,
# start it again.
#
#   powershell -ExecutionPolicy Bypass -File scripts\reset-bel.ps1
#
# Nothing is deleted. Everything cleared is moved into
# ~/.bel/reset-backup-<timestamp>/ first, so a reset that turns out to be the
# wrong idea can be undone by copying it back.
#
# What this fixes: a card stranded off-screen after a monitor change (that
# lives in cards/), or search answering out of a stale index.

$ErrorActionPreference = 'Stop'

$bel = Join-Path $env:USERPROFILE '.bel'

# Derived or throwaway, all of it rebuilt on demand. Two things are
# deliberately NOT here, because they are choices the user made rather than
# state Bel derived, and neither can be reproduced from the repo:
#   timetable.ical-url    - the actual calendar subscription URL
#   cards/wedges.json     - the pie menu's relabelled/reordered wedges
$clearable = @(
    'vault-index.sqlite3',    # rebuilt on the next lookup
    'claude-cwd',             # the CLI's session bucket, already reset at every startup
    'hotkey.log',
    'startup.log'
)

# cards/ is cleared file by file rather than wholesale: it mixes per-card
# geometry (throwaway, and what strands a card off-screen after a monitor
# change) with wedges.json, which is configuration.
$keepInCards = @('wedges.json')

& (Join-Path $PSScriptRoot 'stop-bel.ps1')

$moved = @()
$backup = Join-Path $bel ("reset-backup-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
foreach ($name in $clearable) {
    $path = Join-Path $bel $name
    if (-not (Test-Path -LiteralPath $path)) { continue }
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    Move-Item -LiteralPath $path -Destination (Join-Path $backup $name)
    $moved += $name
}

$cards = Join-Path $bel 'cards'
if (Test-Path -LiteralPath $cards) {
    foreach ($file in Get-ChildItem -LiteralPath $cards -File) {
        if ($keepInCards -contains $file.Name) { continue }
        New-Item -ItemType Directory -Force -Path (Join-Path $backup 'cards') | Out-Null
        Move-Item -LiteralPath $file.FullName -Destination (Join-Path (Join-Path $backup 'cards') $file.Name)
        $moved += "cards\$($file.Name)"
    }
}

if ($moved) {
    Write-Host ("Cleared: {0}" -f ($moved -join ', '))
    Write-Host "Kept a copy in $backup"
} else {
    Write-Host "Nothing to clear."
}
Write-Host "Kept: timetable.ical-url, cards\wedges.json"

& (Join-Path $PSScriptRoot 'start-bel.ps1')
Start-Sleep -Seconds 2
$running = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*src?main.py*' }
if ($running) {
    Write-Host "Bel restarted (pid $($running.ProcessId -join ', '))."
} else {
    Write-Host "Bel did not come back - see $bel\startup.log"
}
