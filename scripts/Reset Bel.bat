@echo off
REM Double-click me when Bel runs but its saved state is wrong - a card stuck
REM off-screen, or search answering out of a stale index. Nothing is deleted:
REM what gets cleared is copied to .bel\reset-backup-<date> first.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reset-bel.ps1"
echo.
pause
