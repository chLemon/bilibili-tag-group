@echo off
rem Windows entry: restart = stop + start. All logic lives in scripts\manage.py.
rem Trailing pause keeps the window open so the user can read the output.
rem NOTE: keep this file pure ASCII (see ensure-uv.bat for why).
cd /d "%~dp0.."
set PYTHONUTF8=1
call scripts\ensure-uv.bat
if errorlevel 1 pause & exit /b 1
uv run python scripts\manage.py restart
pause
