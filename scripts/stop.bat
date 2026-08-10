@echo off
rem Windows entry: stop backend + frontend and back up the data repo.
rem All logic lives in scripts\manage.py. Trailing pause keeps the window
rem open so the user can read the stop/backup output.
rem NOTE: keep this file pure ASCII (see ensure-uv.bat for why).
cd /d "%~dp0.."
set PYTHONUTF8=1
call scripts\ensure-uv.bat
if errorlevel 1 pause & exit /b 1
uv run python scripts\manage.py stop
pause
