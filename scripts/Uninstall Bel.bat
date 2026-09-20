@echo off
REM Double-click me to stop Bel starting at logon and remove its shortcuts.
REM Your saved data is kept unless you ask for it to go too.
echo This stops Bel and removes its Startup and Start menu shortcuts.
echo.
echo Your saved data (calendar URL, wedge layout, card positions, vault index)
echo lives in %USERPROFILE%\.bel and is kept by default.
echo.
set "WITHDATA="
set /p "ANSWER=Move that data aside as well? [y/N] "
if /i "%ANSWER%"=="y" set "WITHDATA=-IncludeData"
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-autostart.ps1" %WITHDATA%
echo.
pause
