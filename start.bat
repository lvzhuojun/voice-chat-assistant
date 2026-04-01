@echo off
REM Voice Chat Assistant - Start Script
REM Order: Docker (postgres+redis) -> Alembic migration -> Backend -> Frontend

echo ================================================
echo  Voice Chat Assistant - Starting Services
echo ================================================
echo.

REM Check .env
if not exist .env (
    echo [WARNING] .env not found, copying from .env.example
    copy .env.example .env
)

REM Activate conda environment
call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Cannot activate voice-chat conda env. Run setup\install.bat first.
    pause
    exit /b 1
)

REM Step 1: Start PostgreSQL + Redis via Docker
echo [INFO] Starting PostgreSQL + Redis (Docker)...
docker compose -f docker/docker-compose.yml up -d postgres redis
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker failed to start. Make sure Docker Desktop is running.
    pause
    exit /b 1
)

REM Wait for PostgreSQL to be ready (up to 30 seconds)
echo [INFO] Waiting for PostgreSQL...
set /a WAIT=0
:WAIT_LOOP
timeout /t 2 /nobreak >nul
docker compose -f docker/docker-compose.yml exec -T postgres pg_isready -U voice -d voicechat >nul 2>&1
if %ERRORLEVEL% equ 0 goto DB_READY
set /a WAIT+=2
if %WAIT% geq 30 (
    echo [ERROR] PostgreSQL not ready after 30s. Check logs:
    echo         docker compose -f docker/docker-compose.yml logs postgres
    pause
    exit /b 1
)
goto WAIT_LOOP

:DB_READY
echo [INFO] PostgreSQL is ready

REM Step 2: Run database migrations
echo [INFO] Running Alembic migrations...
alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Alembic returned non-zero (may already be up to date), continuing...
)

REM Step 3: Start backend
echo [INFO] Starting backend (port 8000)...
start "VoiceChat Backend" cmd /k "call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat && cd /d D:\Lyuzhuojun\Project\Forsis\voice-chat-assistant && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

REM Step 4: Start frontend
echo [INFO] Starting frontend (port 5173)...
start "VoiceChat Frontend" cmd /k "call D:\Anaconda3\Scripts\activate.bat D:\Anaconda3\envs\voice-chat && cd /d D:\Lyuzhuojun\Project\Forsis\voice-chat-assistant\frontend && npm run dev"

echo.
echo [SUCCESS] All services starting...
echo.
echo  PostgreSQL : localhost:5432
echo  Redis      : localhost:6379
echo  Backend    : http://localhost:8000
echo  Frontend   : http://localhost:5173
echo  API Docs   : http://localhost:8000/docs
echo.
echo To stop all services, run stop.bat
pause
