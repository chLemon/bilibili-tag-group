@echo off
rem Ensure uv is available: return immediately if found; otherwise install it
rem via pip and add pip's Scripts dirs to the current session PATH (session
rem only, no registry writes, avoids the setx PATH-truncation pitfall).
rem Called via "call" from start/stop/restart.bat, so PATH changes propagate
rem back to the caller.
rem NOTE: keep this file pure ASCII. cmd parses batch files in the system ANSI
rem codepage (GBK on zh-CN systems) and chcp 65001 does NOT reliably fix
rem parsing of non-ASCII lines, so all Chinese output lives in manage.py.

where uv >nul 2>&1
if not errorlevel 1 exit /b 0

echo uv not found, installing via pip...

rem python may be absent from PATH while the py launcher is present; try both
where python >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] python not found. Install Python and check "Add python.exe to PATH"
        exit /b 1
    )
    set "PY=py"
)

%PY% -m pip install --user uv
if errorlevel 1 (
    echo [ERROR] pip install uv failed. Run manually: %PY% -m pip install --user uv
    exit /b 1
)

rem pip --user installs into the user Scripts dir (usually not on PATH);
rem a non-user install lands in Python's own Scripts dir. Add both to the
rem current session, and persist the user Scripts dir to the user PATH (via
rem PowerShell registry write, not setx which truncates at 1024 chars) so
rem future windows find uv directly.
for /f "delims=" %%i in ('%PY% -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"') do (
    set "PATH=%PATH%;%%i"
    powershell -NoProfile -Command "$p=[Environment]::GetEnvironmentVariable('Path','User'); if ($p -notlike '*%%i*') { [Environment]::SetEnvironmentVariable('Path', $p + ';%%i', 'User') }" >nul 2>&1
)
for /f "delims=" %%i in ('%PY% -c "import sysconfig; print(sysconfig.get_path('scripts'))"') do set "PATH=%PATH%;%%i"

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv installed but still not found on PATH; open a new terminal and retry
    exit /b 1
)
echo uv installed
exit /b 0
