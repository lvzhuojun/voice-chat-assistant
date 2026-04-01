
# Voice Chat Assistant 停止脚本 (PowerShell)
Write-Host "[INFO] 停止 Voice Chat Assistant 服务..." -ForegroundColor Yellow

$ProjectRoot = $PSScriptRoot

# 停止占用 8000 端口的进程（后端）
$proc8000 = netstat -ano | Select-String ":8000 " | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Select-Object -Unique
foreach ($pid in $proc8000) {
    if ($pid -match '^\d+$' -and $pid -ne '0') {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

# 停止占用 5173 端口的进程（前端）
$proc5173 = netstat -ano | Select-String ":5173 " | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Select-Object -Unique
foreach ($pid in $proc5173) {
    if ($pid -match '^\d+$' -and $pid -ne '0') {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

# 停止 Docker 容器
Write-Host "[INFO] 停止 Docker 容器 (postgres + redis)..." -ForegroundColor Yellow
docker compose -f "$ProjectRoot\docker\docker-compose.yml" stop postgres redis

Write-Host "[SUCCESS] 所有服务已停止" -ForegroundColor Green
Read-Host "按 Enter 退出"
