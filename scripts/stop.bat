@echo off
cd /d "%~dp0.."
uv run python scripts\manage.py stop
pause
