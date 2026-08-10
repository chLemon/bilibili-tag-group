@echo off
rem Windows entry: start backend + frontend. All logic lives in scripts\manage.py.
rem %~dp0 is this script's directory; cd /d to the project root so paths stay
rem correct when double-clicked. Trailing pause keeps the window open so the
rem user can read the startup output.
rem NOTE: keep this file pure ASCII (see ensure-uv.bat for why).
rem PYTHONUTF8 makes manage.py emit UTF-8 logs, consistent with macOS/Linux.
cd /d "%~dp0.."
set PYTHONUTF8=1
call scripts\ensure-uv.bat
if errorlevel 1 pause & exit /b 1
uv run python scripts\manage.py start
pause
