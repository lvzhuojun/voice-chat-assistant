@echo off
REM voice-chat-assistant setup script
REM Creates the conda environment and installs all dependencies

echo ================================================
echo  Voice Chat Assistant - Environment Setup
echo ================================================
echo.

REM Check conda is available
where conda >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda not found. Install Miniconda or Anaconda first.
    pause
    exit /b 1
)

echo [INFO] Checking for voice-chat conda environment...
conda env list | findstr /C:"voice-chat" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] voice-chat environment already exists
    echo [INFO] To recreate it, run: conda env remove -n voice-chat
    goto :gptsovits_deps
)

echo [INFO] Creating conda environment from environment.yml (Python 3.10)...
conda env create -f environment.yml
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Environment creation failed. Check environment.yml.
    pause
    exit /b 1
)

echo [SUCCESS] conda environment created

:gptsovits_deps
echo.
echo [INFO] Installing GPT-SoVITS inference dependencies...
echo [INFO] This may take several minutes on first run.
conda run -n voice-chat pip install -r requirements-gptsovits.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] GPT-SoVITS dependencies install failed.
    echo [INFO] Try manually: conda activate voice-chat
    echo [INFO]               pip install -r requirements-gptsovits.txt
    pause
    exit /b 1
)

echo [SUCCESS] GPT-SoVITS inference dependencies installed

:frontend
echo.
echo [INFO] Installing frontend dependencies...
cd frontend
call conda run -n voice-chat npm install
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)
cd ..

echo [SUCCESS] Frontend dependencies installed

echo.
echo ================================================
echo  Setup complete!
echo ================================================
echo.
echo Next steps:
echo   1. Run  setup\clone_gptsovits.bat        to clone GPT-SoVITS
echo   2. Run  conda activate voice-chat         then
echo           python setup/download_models.py   to download pretrained models
echo   3. Copy .env.example to .env and fill in your settings
echo   4. Run  start.bat                         to launch all services
echo.
pause
