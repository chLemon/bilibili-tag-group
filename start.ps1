$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$LogDir = Join-Path $PSScriptRoot "logs"
$BackendPidFile = Join-Path $LogDir "backend.pid"
$FrontendPidFile = Join-Path $LogDir "frontend.pid"
$BackendPort = 8000
$FrontendPort = 5173

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ============================================================
# 检查是否已经启动
# ============================================================
$alreadyRunning = $false
foreach ($pidFile in @($BackendPidFile, $FrontendPidFile)) {
    if (Test-Path $pidFile) {
        $savedPid = (Get-Content $pidFile -Raw).Trim()
        if ($savedPid -and [int]::TryParse($savedPid, [ref]$null)) {
            $pidInt = [int]$savedPid
            $proc = Get-Process -Id $pidInt -ErrorAction SilentlyContinue
            if ($proc) {
                $alreadyRunning = $true
                break
            }
        }
        Remove-Item $pidFile -Force  # 僵尸或无效 PID 文件，清理掉
    }
}

if ($alreadyRunning) {
    Write-Host "Services are already running, opening browser..."
    Start-Process "http://localhost:$FrontendPort"
    exit 0
}

# ============================================================
# 检查依赖
# ============================================================
Write-Host "============================================"
Write-Host "  Bilibili Tag Group Launcher"
Write-Host "============================================"

Write-Host "[1/4] Checking Node.js..."
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js not found."
    exit 1
}

Write-Host "[2/4] Checking Python..."
$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "       .venv not found, creating..."
    $pythonCmd = $null
    foreach ($candidate in @("py", "python3", "python")) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        # 排除 Microsoft Store 占位程序
        if ($found.Source -match "WindowsApps") { continue }
        # 验证是真 Python
        $ver = & $found.Source --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "Python") {
            $pythonCmd = $found.Source
            break
        }
    }
    if (-not $pythonCmd) {
        Write-Host "[ERROR] Python not found. Install from https://www.python.org/downloads/"
        Write-Host "        Make sure 'Add Python to PATH' is checked during installation."
        exit 1
    }
    Write-Host "       Using: $pythonCmd"
    $venvOutput = & $pythonCmd -m venv .venv 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create .venv:"
        Write-Host $venvOutput
        exit 1
    }
    & $PythonExe -m pip install -e ".[dev]" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to install dependencies"
        exit 1
    }
    Write-Host "       .venv created and dependencies installed."
}

Write-Host "[3/5] Checking private-data directory..."
$PrivateDataDir = Join-Path $PSScriptRoot "..\private-data\bilibili-tag-group"
if (-not (Test-Path $PrivateDataDir)) {
    Write-Host "       Creating $PrivateDataDir ..."
    New-Item -ItemType Directory -Force -Path $PrivateDataDir | Out-Null
}
$DbFile = Join-Path $PrivateDataDir "my_bilibili.db"
if (Test-Path $DbFile) {
    Write-Host "       Database found: $DbFile"
} else {
    Write-Host "       Database not found, will be created on first run: $DbFile"
}

Write-Host "[4/5] Database migration..."
$AlembicExe = Join-Path $PSScriptRoot ".venv\Scripts\alembic.exe"
$MigrationLog = Join-Path $LogDir "migration.log"
& $AlembicExe upgrade head 2>&1 | Out-File -FilePath $MigrationLog -Encoding UTF8
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Migration failed. See: $MigrationLog"
    Get-Content $MigrationLog -ErrorAction SilentlyContinue | Write-Host
    exit 1
}
Write-Host "       Migration OK"

# ============================================================
# 启动服务
# ============================================================
Write-Host "[5/5] Starting services..."

$UvicornExe = Join-Path $PSScriptRoot ".venv\Scripts\uvicorn.exe"
$FrontendDir = Join-Path $PSScriptRoot "frontend"

# 检查并安装前端依赖
$NodeModulesDir = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModulesDir)) {
    Write-Host "       node_modules not found, running npm install..."
    $npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npmCmd) { $npmCmd = (Get-Command npm -ErrorAction SilentlyContinue).Source }
    if (-not $npmCmd) {
        Write-Host "[ERROR] npm not found."
        exit 1
    }
    $installLog = Join-Path $LogDir "npm-install.log"
    $installProc = Start-Process `
        -FilePath $npmCmd `
        -ArgumentList "install" `
        -WorkingDirectory $FrontendDir `
        -Wait `
        -NoNewWindow `
        -RedirectStandardOutput $installLog `
        -RedirectStandardError $installLog `
        -PassThru
    if ($installProc.ExitCode -ne 0) {
        Write-Host "[ERROR] npm install failed. See: $installLog"
        Get-Content $installLog -Tail 20 | Write-Host
        exit 1
    }
    Write-Host "       npm install OK"
}

# 启动后端 (uvicorn)
$BackendLog = Join-Path $LogDir "backend.log"
$backendProc = Start-Process `
    -FilePath $UvicornExe `
    -ArgumentList "app.main:app --host 127.0.0.1 --port $BackendPort" `
    -WindowStyle Hidden `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendLog `
    -PassThru

# 启动前端 (vite)
$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) { $npmCmd = (Get-Command npm -ErrorAction SilentlyContinue).Source }
$FrontendLog = Join-Path $LogDir "frontend.log"
$frontendProc = Start-Process `
    -FilePath $npmCmd `
    -ArgumentList "run dev" `
    -WorkingDirectory $FrontendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError $FrontendLog `
    -PassThru

# ============================================================
# 等待服务就绪
# ============================================================
function Test-Port($Port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        if ($tcp.ConnectAsync("127.0.0.1", $Port).Wait(1000)) {
            $tcp.Close()
            return $true
        }
        $tcp.Close()
    } catch {}
    return $false
}

function Wait-ForPort($Port, $TimeoutSeconds) {
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

Write-Host "       Waiting for backend on port $BackendPort..."
$backendReady = Wait-ForPort $BackendPort 15
if (-not $backendReady) {
    Write-Host "[WARN] Backend did not start within 15 seconds. See: $BackendLog"
} else {
    $backendProc.Id | Out-File -FilePath $BackendPidFile -NoNewline
    Write-Host "       Backend ready (PID $($backendProc.Id))"
}

Write-Host "       Waiting for frontend on port $FrontendPort..."
$frontendReady = Wait-ForPort $FrontendPort 30
if (-not $frontendReady) {
    Write-Host "[WARN] Frontend did not start within 30 seconds. See: $FrontendLog"
} else {
    $frontendProc.Id | Out-File -FilePath $FrontendPidFile -NoNewline
    Write-Host "       Frontend ready (PID $($frontendProc.Id))"
}

if ($frontendReady) {
    Write-Host "       Opening browser..."
    Start-Process "http://localhost:$FrontendPort"
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Backend:  http://localhost:$BackendPort"
Write-Host "  Frontend: http://localhost:$FrontendPort"
Write-Host "  Logs:     $LogDir"
Write-Host "============================================"
