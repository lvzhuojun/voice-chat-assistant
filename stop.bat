@echo off
REM Voice Chat Assistant 停止脚本

echo [INFO] 停止 Voice Chat Assistant 服务...

REM 停止占用 8000 端口的进程（后端）
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM 停止占用 5173 端口的进程（前端）
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM 停止 Docker 容器（postgres + redis）
echo [INFO] 停止 Docker 容器 (postgres + redis)...
docker compose -f docker/docker-compose.yml stop postgres redis >nul 2>&1

echo [SUCCESS] 所有服务已停止
pause
