@echo off
title Woodlands Zone 6 - Community Hub
color 0A
cls

echo ==========================================
echo   WOODLANDS ZONE 6 - COMMUNITY HUB
echo   Streamlit Launcher
echo ==========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://python.org
    echo.
    pause
    exit /b 1
)

echo [OK] Python detected.
python --version
echo.

:: Check if virtual environment exists, create if not
if not exist "venv\" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment found.
)
echo.

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

:: Check if requirements are installed
echo [INFO] Checking dependencies...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies (first run may take 2-3 minutes)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
) else (
    echo [OK] Dependencies already installed.
)
echo.

:: Launch Streamlit
echo ==========================================
echo   LAUNCHING STREAMLIT APP...
echo   Browser will open automatically
echo   Press Ctrl+C to stop the server
echo ==========================================
echo.

streamlit run app.py --server.headless true

:: Deactivate on exit
call venv\Scripts\deactivate.bat
echo.
echo [INFO] App stopped. Press any key to close...
pause >nul
