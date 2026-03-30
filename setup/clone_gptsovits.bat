@echo off
REM 克隆 GPT-SoVITS 源码到 GPT-SoVITS/ 目录
REM 与 voice-cloning-service 保持一致

echo [INFO] 开始克隆 GPT-SoVITS...

if exist GPT-SoVITS (
    echo [INFO] GPT-SoVITS 目录已存在，跳过克隆
    echo [INFO] 如需更新，请手动执行：cd GPT-SoVITS && git pull
    goto :end
)

git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT-SoVITS
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 克隆失败，请检查网络连接或 Git 配置
    pause
    exit /b 1
)

echo [SUCCESS] GPT-SoVITS 克隆完成

:end
echo.
echo [INFO] 下一步：运行 python setup/download_models.py 下载预训练模型
pause
