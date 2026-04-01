
# Voice Chat Assistant 启动脚本 (PowerShell)
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " Voice Chat Assistant - 启动服务" -ForegroundColor Cyan
Write-Host "================================================"
Write-Host ""

$ProjectRoot = $PSScriptRoot

# 检查 .env
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "[WARNING] 未找到 .env，使用 .env.example" -ForegroundColor Yellow
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
}

# ── 第一步：启动 PostgreSQL + Redis (Docker) ──────────────────
Write-Host "[INFO] 启动 PostgreSQL + Redis (Docker)..." -ForegroundColor Green
docker compose -f "$ProjectRoot\docker\docker-compose.yml" up -d postgres redis
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker 启动失败，请确认 Docker Desktop 正在运行" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# 等待 PostgreSQL 就绪（最多 30 秒）
Write-Host "[INFO] 等待 PostgreSQL 就绪..." -ForegroundColor Green
$waited = 0
while ($waited -lt 30) {
    Start-Sleep -Seconds 2
    $waited += 2
    docker compose -f "$ProjectRoot\docker\docker-compose.yml" exec -T postgres pg_isready -U voice -d voicechat 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[INFO] PostgreSQL 已就绪 (${waited}s)" -ForegroundColor Green
        break
    }
    Write-Host "  等待中... ${waited}s"
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PostgreSQL 30秒内未就绪" -ForegroundColor Red
    Write-Host "        可运行：docker compose -f docker\docker-compose.yml logs postgres"
    Read-Host "按 Enter 退出"
    exit 1
}

# ── 第二步：运行数据库迁移 ────────────────────────────────────
Write-Host "[INFO] 运行数据库迁移 (Alembic)..." -ForegroundColor Green
& "D:\Anaconda3\envs\voice-chat\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Alembic 返回非零（可能已是最新版本），继续..." -ForegroundColor Yellow
}

# ── 第三步：启动后端 ──────────────────────────────────────────
Write-Host "[INFO] 启动后端服务（端口 8000）..." -ForegroundColor Green
Start-Process "cmd.exe" -ArgumentList "/k", "call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat && cd /d $ProjectRoot && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 3

# ── 第四步：启动前端 ──────────────────────────────────────────
Write-Host "[INFO] 启动前端服务（端口 5173）..." -ForegroundColor Green
Start-Process "cmd.exe" -ArgumentList "/k", "call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat && cd /d $ProjectRoot\frontend && npm run dev"

Write-Host ""
Write-Host "[SUCCESS] 所有服务启动中..." -ForegroundColor Green
Write-Host ""
Write-Host "  PostgreSQL : localhost:5432"
Write-Host "  Redis      : localhost:6379"
Write-Host "  后端        : http://localhost:8000"
Write-Host "  前端        : http://localhost:5173"
Write-Host "  API文档     : http://localhost:8000/docs"
Write-Host ""
Write-Host "停止服务请运行：.\stop.ps1" -ForegroundColor Yellow
Read-Host "按 Enter 关闭此窗口（后端/前端在独立窗口继续运行）"
