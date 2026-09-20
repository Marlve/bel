@echo off
REM Double-click me to start Bel without waiting for the next logon. Safe to
REM click twice - it checks whether Bel is already running first.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-bel.ps1"
echo.
pause
