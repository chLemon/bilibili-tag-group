@echo off
cd /d "%~dp0"
echo Stopping...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
echo Starting...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
