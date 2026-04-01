@echo off
REM Voice Chat Assistant - Stop Script

echo [INFO] Stopping Voice Chat Assistant services...

REM Kill process on port 8000 (backend)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill process on port 5173 (frontend)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Stop Docker containers
echo [INFO] Stopping Docker containers (postgres + redis)...
docker compose -f docker/docker-compose.yml stop postgres redis >nul 2>&1

echo [SUCCESS] All services stopped
pause
