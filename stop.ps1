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

    $savedPid = Get-Content $pidFile -Raw
    $proc = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue

    if (-not $proc) {
        Write-Host "PID $savedPid not running, removing stale PID file."
        Remove-Item $pidFile -Force
        $stopped = $true
        continue
    }

    Write-Host "Stopping $($proc.ProcessName) (PID $savedPid)..."
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
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
