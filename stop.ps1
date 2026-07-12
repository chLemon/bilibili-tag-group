$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$LogDir = Join-Path $PSScriptRoot "logs"
$BackendPidFile = Join-Path $LogDir "backend.pid"
$FrontendPidFile = Join-Path $LogDir "frontend.pid"

Write-Host "============================================"
Write-Host "  Bilibili Tag Group - Stopping Services"
Write-Host "============================================"

$stopped = $false

foreach ($pidFile in @($BackendPidFile, $FrontendPidFile)) {
    if (-not (Test-Path $pidFile)) {
        Write-Host "No PID file: $pidFile"
        continue
    }

    $savedPid = (Get-Content $pidFile -Raw).Trim()
    if (-not $savedPid -or (-not [int]::TryParse($savedPid, [ref]$null))) {
        Write-Host "Invalid or empty PID file: $pidFile, removing."
        Remove-Item $pidFile -Force
        $stopped = $true
        continue
    }

    $pidInt = [int]$savedPid
    $proc = Get-Process -Id $pidInt -ErrorAction SilentlyContinue

    if (-not $proc) {
        Write-Host "PID $pidInt not running, removing stale PID file."
        Remove-Item $pidFile -Force
        $stopped = $true
        continue
    }

    Write-Host "Stopping $($proc.ProcessName) (PID $pidInt) and children..."
    & taskkill /T /PID $proc.Id /F 2>$null
    # 如果 taskkill 失败或 PID 文件存的是子进程真实 PID，兜底用 Stop-Process
    if ($LASTEXITCODE -ne 0) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force
    $stopped = $true
}

Start-Sleep -Seconds 1

if ($stopped) {
    Write-Host "Services stopped."
} else {
    Write-Host "No running services found."
}

Write-Host "============================================"
