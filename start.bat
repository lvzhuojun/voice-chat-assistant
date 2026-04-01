@echo off
REM Voice Chat Assistant 启动脚本
REM 顺序：Docker(postgres+redis) -> Alembic迁移 -> 后端 -> 前端

echo ================================================
echo  Voice Chat Assistant - 启动服务
echo ================================================
echo.

REM 检查 .env
if not exist .env (
    echo [WARNING] 未找到 .env 文件，使用 .env.example
    copy .env.example .env
)

REM 激活 conda 环境（失败则报错退出）
call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 无法激活 voice-chat conda 环境，请先运行 setup\install.bat
    pause
    exit /b 1
)

REM ── 第一步：启动 PostgreSQL + Redis (Docker) ──────────────────
echo [INFO] 启动 PostgreSQL + Redis (Docker)...
docker compose -f docker/docker-compose.yml up -d postgres redis
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker 启动失败，请确认 Docker Desktop 正在运行
    pause
    exit /b 1
)

REM 等待 PostgreSQL 健康检查通过（最多等 30 秒）
echo [INFO] 等待 PostgreSQL 就绪...
set /a WAIT=0
:WAIT_LOOP
timeout /t 2 /nobreak >nul
docker compose -f docker/docker-compose.yml exec -T postgres pg_isready -U voice -d voicechat >nul 2>&1
if %ERRORLEVEL% equ 0 goto DB_READY
set /a WAIT+=2
if %WAIT% geq 30 (
    echo [ERROR] PostgreSQL 30秒内未就绪，请检查 Docker 日志：
    echo         docker compose -f docker/docker-compose.yml logs postgres
    pause
    exit /b 1
)
goto WAIT_LOOP

:DB_READY
echo [INFO] PostgreSQL 已就绪

REM ── 第二步：运行数据库迁移 ────────────────────────────────────
echo [INFO] 运行数据库迁移 (Alembic)...
alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Alembic 迁移返回非零（可能已是最新），继续启动...
)

REM ── 第三步：启动后端 ──────────────────────────────────────────
echo [INFO] 启动后端服务（端口 8000）...
start "VoiceChat Backend" cmd /k "call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat && cd /d D:\Lyuzhuojun\Project\Forsis\voice-chat-assistant && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

REM ── 第四步：启动前端 ──────────────────────────────────────────
echo [INFO] 启动前端服务（端口 5173）...
start "VoiceChat Frontend" cmd /k "call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat && cd /d D:\Lyuzhuojun\Project\Forsis\voice-chat-assistant\frontend && npm run dev"

echo.
echo [SUCCESS] 所有服务启动中...
echo.
echo  PostgreSQL : localhost:5432
echo  Redis      : localhost:6379
echo  后端        : http://localhost:8000
echo  前端        : http://localhost:5173
echo  API文档     : http://localhost:8000/docs
echo.
echo 停止服务请运行 stop.bat
pause
