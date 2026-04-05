@echo off
REM voice-chat-assistant setup script
REM Creates the conda environment and installs all dependencies

echo ================================================
echo  Voice Chat Assistant - Environment Setup
echo ================================================
echo.

REM ── Check conda ─────────────────────────────────────────────────────────────
where conda >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda not found. Install Miniconda or Anaconda first.
    pause
    exit /b 1
)

REM ── Detect conda base (portable) ─────────────────────────────────────────────
for /f "delims=" %%i in ('conda info --base 2^>nul') do set CONDA_BASE=%%i
if not defined CONDA_BASE (
    echo [ERROR] Cannot determine conda base directory.
    pause
    exit /b 1
)

REM ── Create or skip conda environment ─────────────────────────────────────────
echo [INFO] Checking for voice-chat conda environment...
conda env list | findstr /C:"voice-chat" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] voice-chat environment already exists
    echo [INFO] To recreate it: conda env remove -n voice-chat
    goto :pip_deps
)

echo [INFO] Creating conda environment from environment.yml (Python 3.10)...
conda env create -f environment.yml
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Environment creation failed. Check environment.yml.
    pause
    exit /b 1
)
echo [OK] conda environment created

REM ── Install / update pip backend requirements ────────────────────────────────
:pip_deps
echo.
echo [INFO] Installing / updating backend pip requirements...
call "%CONDA_BASE%\Scripts\activate.bat" voice-chat
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [WARN] Some pip packages failed. Check output above.
)

REM ── Install GPT-SoVITS inference requirements ────────────────────────────────
echo.
echo [INFO] Installing GPT-SoVITS inference dependencies...
pip install -r requirements-gptsovits.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] GPT-SoVITS dependencies install failed.
    echo [INFO] Try manually: pip install -r requirements-gptsovits.txt
    pause
    exit /b 1
)
echo [OK] GPT-SoVITS inference dependencies installed

REM ── Windows: fix _lzma DLL if missing ───────────────────────────────────────
echo.
echo [INFO] Checking Windows lzma support...
python -c "import _lzma" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARN] _lzma not found in voice-chat env, attempting fix...
    if exist "%CONDA_BASE%\DLLs\_lzma.pyd" (
        copy /Y "%CONDA_BASE%\DLLs\_lzma.pyd" "%CONDA_BASE%\envs\voice-chat\DLLs\_lzma.pyd" >nul
        echo [OK] Copied _lzma.pyd
    )
    if exist "%CONDA_BASE%\Library\bin\liblzma.dll" (
        copy /Y "%CONDA_BASE%\Library\bin\liblzma.dll" "%CONDA_BASE%\envs\voice-chat\Library\bin\liblzma.dll" >nul
        echo [OK] Copied liblzma.dll
    )
    python -c "import _lzma" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [OK] _lzma is now available
    ) else (
        echo [WARN] Could not fix _lzma automatically.
        echo [INFO] Run: conda install -n voice-chat -c conda-forge liblzma
    )
) else (
    echo [OK] lzma support OK
)

REM ── Frontend ─────────────────────────────────────────────────────────────────
:frontend
echo.
echo [INFO] Installing frontend dependencies...
cd frontend
npm install
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)
cd ..
echo [OK] Frontend dependencies installed

echo.
echo ================================================
echo  Setup complete!
echo ================================================
echo.
echo Next steps:
echo   1. Run  setup\clone_gptsovits.bat        to clone GPT-SoVITS
echo   2. Copy .env.example to .env and fill in your API keys
echo   3. Run  conda activate voice-chat ^&^& python setup/download_models.py
echo      to download pretrained models and create runtime links
echo   4. Run  start.bat                         to launch all services
echo.
pause
