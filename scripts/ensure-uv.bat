@echo off
rem 本文件含中文，必须以 UTF-8 代码页解析，否则 cmd（默认 GBK）会把中文行读成乱码
chcp 65001 >nul
rem 确保 uv 可用：已安装则直接返回；未安装则用 pip 安装，并把 pip 的
rem Scripts 目录加进当前会话 PATH（仅本次 cmd 窗口生效，不修改注册表，
rem 避免 setx 截断 PATH 的风险）。被 start/stop/restart.bat 以 call 方式调用，
rem 因此对 PATH 的修改会带回调用方。

where uv >nul 2>&1
if not errorlevel 1 exit /b 0

echo 未找到 uv，尝试用 pip 安装...

rem python 可能不在 PATH 但 py 启动器在，二者择一
where python >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] 未找到 python，请先安装 Python 并勾选 "Add python.exe to PATH"
        exit /b 1
    )
    set "PY=py"
)

%PY% -m pip install --user uv
if errorlevel 1 (
    echo [ERROR] pip 安装 uv 失败，请手动执行: %PY% -m pip install --user uv
    exit /b 1
)

rem pip --user 装到用户 Scripts 目录，通常不在 PATH；非 --user 则装在 Python
rem 自带 Scripts 目录。两个都加进当前会话 PATH，覆盖两种安装位置。
for /f "delims=" %%i in ('%PY% -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"') do set "PATH=%PATH%;%%i"
for /f "delims=" %%i in ('%PY% -c "import sysconfig; print(sysconfig.get_path('scripts'))"') do set "PATH=%PATH%;%%i"

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv 已安装但当前会话仍找不到，请新开一个命令行窗口重试
    exit /b 1
)
echo uv 安装完成
exit /b 0
