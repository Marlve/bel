@echo off
REM Double-click me to close Bel. It still starts again at your next logon -
REM to stop that, use Task Manager > Startup apps and switch Bel off.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-bel.ps1"
echo.
pause
