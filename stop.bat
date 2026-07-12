@echo off
cd /d "%~dp0"
echo Stopping...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
pause
