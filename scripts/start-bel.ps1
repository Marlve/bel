# What the "Bel" scheduled task runs at logon (see install-autostart.ps1).
#
# The task could launch pythonw.exe directly, but going through this script
# buys two things worth the extra file: a single-instance guard, and a log of
# why a boot that didn't start Bel didn't start it. Nothing is visible at
# logon, so without the log a failed start is silent.

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$entry = Join-Path $repo 'src\main.py'
$log = Join-Path $env:USERPROFILE '.bel\startup.log'

function Write-Log($message) {
    $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
    Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

try {
    # One instance only. The pie menu registers Ctrl+Shift+Space through
    # RegisterHotKey, which fails when the combination is already taken - so a
    # second copy would run with a dead hotkey and never say so. Matches
    # python.exe too, since a hand-started copy uses that.
    $running = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*src?main.py*' }
    if ($running) {
        Write-Log ("already running (pid {0}) - nothing to do" -f ($running.ProcessId -join ', '))
        exit 0
    }

    if (-not (Test-Path -LiteralPath $entry)) {
        Write-Log "entry point missing: $entry"
        exit 1
    }

    # pythonw, not python: python.exe would hold a console window open behind
    # the overlay for as long as Bel runs. claude.py already expects this -
    # it guards sys.stdout being None under pythonw.
    $python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
    if (-not $python) { $python = 'C:\Python313\pythonw.exe' }
    if (-not (Test-Path -LiteralPath $python)) {
        Write-Log "pythonw not found at $python"
        exit 1
    }

    $process = Start-Process -FilePath $python -ArgumentList $entry -WorkingDirectory $repo -PassThru
    Write-Log ("started {0} (pid {1})" -f $python, $process.Id)
} catch {
    Write-Log "failed: $_"
    exit 1
}
