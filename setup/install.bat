@echo off
REM voice-chat-assistant 安装脚本
REM 创建 conda 环境并安装所有依赖

echo ================================================
echo  Voice Chat Assistant - 环境安装
echo ================================================
echo.

REM 检查 conda
where conda >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 未找到 conda，请先安装 Miniconda 或 Anaconda
    pause
    exit /b 1
)

echo [INFO] 检查 voice-chat 环境...
conda env list | findstr /C:"voice-chat" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] voice-chat 环境已存在
    echo [INFO] 如需重建，请先执行：conda env remove -n voice-chat
    goto :frontend
)

echo [INFO] 创建 conda 环境（Python 3.10）...
conda env create -f environment.yml
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 环境创建失败，请检查 environment.yml
    pause
    exit /b 1
)

echo [SUCCESS] conda 环境创建完成

:frontend
echo.
echo [INFO] 安装前端依赖...
cd frontend
call conda run -n voice-chat npm install
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm install 失败
    pause
    exit /b 1
)
cd ..

echo [SUCCESS] 前端依赖安装完成

echo.
echo ================================================
echo  安装完成！
echo ================================================
echo.
echo 下一步：
echo   1. 运行 setup\clone_gptsovits.bat 克隆 GPT-SoVITS
echo   2. 运行 conda activate voice-chat ^&^& python setup/download_models.py 下载预训练模型
echo   3. 复制 .env.example 为 .env 并配置
echo   4. 运行 start.bat 启动服务
echo.
pause
