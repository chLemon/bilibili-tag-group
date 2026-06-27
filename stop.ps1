$ErrorActionPreference = "Continue"

Set-Location $PSScriptRoot

Write-Host "============================================"
Write-Host "  Bilibili Tag Group - Stopping Services"
Write-Host "============================================"

$found = $false
$targetPorts = @(8000, 5173)
$netstat = netstat -ano 2>$null

foreach ($line in $netstat) {
    foreach ($port in $targetPorts) {
        if ($line -match ":$port\s+.*LISTENING\s+(\d+)") {
            $killedPid = [int]$Matches[1]
            Write-Host "Stopping process on port $port (PID $killedPid)..."
            Stop-Process -Id $killedPid -Force -ErrorAction SilentlyContinue
            $found = $true
        }
    }
}

# 兜底清理
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
    Where-Object { $_.CommandLine -match "bilibili-tag-group" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $found = $true }

Get-Process -Name "python", "node", "uvicorn" -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue; $found = $true }

Start-Sleep -Seconds 1

if ($found) {
    Write-Host ""
    Write-Host "Services stopped."
} else {
    Write-Host ""
    Write-Host "No running services found."
}

Write-Host "============================================"
