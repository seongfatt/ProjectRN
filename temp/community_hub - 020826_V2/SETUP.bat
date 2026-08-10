@echo off
title Community Hub - Setup
color 0B
cls

echo ==========================================
echo   SETUP - Install Dependencies Only
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

if not exist "venv\" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo [INFO] Installing/updating packages...
pip install -r requirements.txt
echo.
echo [OK] Setup complete! Run START_APP.bat to launch.
pause
