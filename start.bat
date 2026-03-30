@echo off
REM Voice Chat Assistant 启动脚本
REM 启动后端（FastAPI）和前端（Vite）

echo ================================================
echo  Voice Chat Assistant - 启动服务
echo ================================================
echo.

REM 检查 .env
if not exist .env (
    echo [WARNING] 未找到 .env 文件，使用 .env.example
    copy .env.example .env
)

REM 检查 conda 环境
conda env list | findstr /C:"voice-chat" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] voice-chat conda 环境不存在，请先运行 setup\install.bat
    pause
    exit /b 1
)

echo [INFO] 启动后端服务（端口 8000）...
start "VoiceChat Backend" cmd /k "conda activate voice-chat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [INFO] 启动前端服务（端口 5173）...
start "VoiceChat Frontend" cmd /k "conda activate voice-chat && cd frontend && npm run dev"

echo.
echo [SUCCESS] 服务启动中...
echo.
echo  后端：http://localhost:8000
echo  前端：http://localhost:5173
echo  API文档：http://localhost:8000/docs
echo.
echo 关闭窗口时请运行 stop.bat 停止所有服务
pause
