@echo off
rem reset-data: clear all business data files under private-data\bilibili-tag-group\
rem (truncate the local data store, project returns to initial state).
rem
rem Deletes:
rem   - 7 business data JSON files (creators / tags / creator_tags / videos /
rem     video_statuses / sync_tasks / tag_sync_configs)
rem   - all *.bak-* backup files
rem   - all *.lock files
rem   - .DS_Store
rem Keep: cookies.json (Bilibili login state; delete manually if needed)
rem
rem Run stop.bat first to avoid backend writing during cleanup.
rem Data dir defaults to ..\private-data\bilibili-tag-group (app\config.py).
rem NOTE: keep this file pure ASCII (see ensure-uv.bat for why).

cd /d "%~dp0.."
set "PROJECT_ROOT=%cd%"
set "DATA_DIR=%PROJECT_ROOT%\..\private-data\bilibili-tag-group"

if not exist "%DATA_DIR%" (
    echo [ERROR] data dir not found: %DATA_DIR%
    pause
    exit /b 1
)
pushd "%DATA_DIR%" 2>nul
set "DATA_DIR=%cd%"
popd

echo About to clear data dir: %DATA_DIR%
echo.
echo Will delete:
echo   - 7 business data JSON (creators / tags / creator_tags / videos /
echo     video_statuses / sync_tasks / tag_sync_configs)
echo   - all *.bak-* backup files
echo   - all *.lock files
echo   - .DS_Store
echo Keep: cookies.json (Bilibili login state)
echo.
set "answer="
set /p answer=Confirm? [y/N]:
if /i not "%answer%"=="y" if /i not "%answer%"=="yes" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
for %%f in (creators.json tags.json creator_tags.json videos.json video_statuses.json sync_tasks.json tag_sync_configs.json) do (
    if exist "%DATA_DIR%\%%f" (
        del /f /q "%DATA_DIR%\%%f"
        echo deleted %%f
    )
)

rem backup / lock files (for loop skips when no match)
for %%f in ("%DATA_DIR%\*.bak-*") do del /f /q "%%f"
for %%f in ("%DATA_DIR%\*.lock") do del /f /q "%%f"
if exist "%DATA_DIR%\.DS_Store" del /f /q "%DATA_DIR%\.DS_Store"
echo cleaned *.bak-* / *.lock / .DS_Store

echo.
echo Done. Data cleared; API will return empty lists.
echo JsonRepo recreates data files on first write.
pause
