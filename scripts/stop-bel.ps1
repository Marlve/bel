# Closes the running Bel, if there is one.
#
#   powershell -ExecutionPolicy Bypass -File scripts\stop-bel.ps1
#
# This does not stop Bel coming back at the next logon - for that, either
#   Disable-ScheduledTask -TaskName Bel        (off, but kept)
#   Unregister-ScheduledTask -TaskName Bel -Confirm:$false   (gone)

$ErrorActionPreference = 'Stop'

$found = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*src?main.py*' }

if (-not $found) {
    Write-Host "Bel isn't running."
    return
}

foreach ($entry in $found) {
    $process = Get-Process -Id $entry.ProcessId -ErrorAction SilentlyContinue
    if (-not $process) { continue }

    # Ask first, so Qt gets its aboutToQuit and anything mid-write finishes.
    # Bel's windows are frameless overlays and may expose no main window at
    # all, in which case CloseMainWindow can't deliver anything and says so.
    $asked = $false
    try { $asked = $process.CloseMainWindow() } catch { }
    if ($asked -and $process.WaitForExit(5000)) {
        Write-Host "Closed Bel (pid $($entry.ProcessId))."
        continue
    }

    Stop-Process -Id $entry.ProcessId -Force
    Write-Host "Stopped Bel (pid $($entry.ProcessId))."
}
