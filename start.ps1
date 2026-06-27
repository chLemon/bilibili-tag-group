$ErrorActionPreference = "Continue"

Set-Location $PSScriptRoot

$LogDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Remove-Item (Join-Path $LogDir "*.log") -Force -ErrorAction SilentlyContinue

$LauncherLog    = Join-Path $LogDir "launcher.log"
$BackendStdout  = Join-Path $LogDir "backend-stdout.log"
$BackendStderr  = Join-Path $LogDir "backend-stderr.log"
$FrontendStdout = Join-Path $LogDir "frontend-stdout.log"
$FrontendStderr = Join-Path $LogDir "frontend-stderr.log"
$MigrationLog   = Join-Path $LogDir "migration.log"

Start-Transcript -Path $LauncherLog -Append | Out-Null

Write-Host "============================================"
Write-Host "  Bilibili Tag Group Launcher"
Write-Host "============================================"

# ============================================================
# 检查是否已经启动
# ============================================================
$alreadyRunning = $false
foreach ($port in @(8000, 5173)) {
    $lines = netstat -ano 2>$null | Select-String ":$port.*LISTENING"
    foreach ($line in $lines) {
        if ($line -match "LISTENING\s+(\d+)") {
            $checkPid = [int]$Matches[1]
            $proc = Get-Process -Id $checkPid -ErrorAction SilentlyContinue
            if ($proc) { $alreadyRunning = $true; break }
        }
    }
}

if ($alreadyRunning) {
    Write-Host ""
    Write-Host "Services are already running."
    Write-Host "  Backend:  http://localhost:8000"
    Write-Host "  Frontend: http://localhost:5173"
    Write-Host ""
    Write-Host "Run stop.bat to stop them first, then try again."
    Stop-Transcript | Out-Null
    try { Read-Host "Press Enter to close" } catch { }
    exit 0
}

# ============================================================
# 清理残留
# ============================================================
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
    Where-Object { $_.CommandLine -match "bilibili-tag-group" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Get-Process -Name "python", "node" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path -match "bilibili-tag-group" } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1

# ============================================================
# 检查依赖
# ============================================================
Write-Host "[1/4] Checking Node.js..."
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js not found."
    Stop-Transcript | Out-Null
    try { Read-Host "Press Enter to close" } catch { }
    exit 1
}

Write-Host "[2/4] Checking Python..."
$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] .venv not found."
    Stop-Transcript | Out-Null
    try { Read-Host "Press Enter to close" } catch { }
    exit 1
}

Write-Host "[3/4] Database migration..."
$AlembicExe = Join-Path $PSScriptRoot ".venv\Scripts\alembic.exe"
cmd /c "`"$AlembicExe`" upgrade head >>`"$MigrationLog`" 2>&1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Migration failed. See: $MigrationLog"
    Get-Content $MigrationLog -ErrorAction SilentlyContinue | Write-Host
    Stop-Transcript | Out-Null
    try { Read-Host "Press Enter to close" } catch { }
    exit 1
}
Write-Host "       Migration OK"

# ============================================================
# 启动服务
# ============================================================
Write-Host "[4/4] Starting services..."

$UvicornExe = Join-Path $PSScriptRoot ".venv\Scripts\uvicorn.exe"
$FrontendDir = Join-Path $PSScriptRoot "frontend"

$backendProcess = Start-Process -FilePath $UvicornExe `
    -ArgumentList "app.main:app --reload --host 127.0.0.1 --port 8000" `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $BackendStdout -RedirectStandardError $BackendStderr

$frontendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c `"cd /d `"$FrontendDir`" && npm run dev`"" `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $FrontendStdout -RedirectStandardError $FrontendStderr

# ============================================================
# 等待前端就绪
# ============================================================
Write-Host "Waiting for frontend to be ready..."

$maxRetries = 30
$ready = $false
for ($i = 1; $i -le $maxRetries; $i++) {
    Start-Sleep -Seconds 1
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 5173)
        $tcp.Close()
        $ready = $true
        break
    } catch { }
}

if (-not $ready) {
    Write-Host "[WARN] Frontend did not start within 30 seconds."
    Write-Host "       Check: $FrontendStdout"
    Get-Content $FrontendStdout -ErrorAction SilentlyContinue | Write-Host
}

# ============================================================
# 打开浏览器
# ============================================================
if ($ready) {
    Write-Host "Frontend is ready, opening browser..."
    Start-Process "http://localhost:5173"
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Logs:     $LogDir"
Write-Host "============================================"
Write-Host ""

Stop-Transcript | Out-Null
