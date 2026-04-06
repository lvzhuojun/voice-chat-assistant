@echo off
REM Clone GPT-SoVITS source into GPT-SoVITS/ directory

echo [INFO] Cloning GPT-SoVITS...

if exist GPT_SoVITS (
    echo [INFO] GPT_SoVITS directory already exists, skipping clone
    echo [INFO] To update, run manually: cd GPT_SoVITS ^&^& git pull
    goto :end
)

git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT_SoVITS
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Clone failed. Check your network connection or Git config.
    pause
    exit /b 1
)

echo [SUCCESS] GPT-SoVITS cloned successfully

:end
echo.
echo [INFO] Next step: run  python setup/download_models.py  to download pretrained models
pause
