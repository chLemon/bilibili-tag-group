@echo off
rem 停止前后端并备份数据仓库（Windows 入口）。逻辑见 scripts\manage.py。
rem 结尾 pause 让窗口驻留，方便用户看停止/备份输出。
cd /d "%~dp0.."
call scripts\ensure-uv.bat
if errorlevel 1 pause & exit /b 1
uv run python scripts\manage.py stop
pause
