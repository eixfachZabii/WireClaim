@echo off
setlocal enabledelayedexpansion

echo =================================================================
echo   WireClaim - QuantCo Tournament Runner (Windows)
echo =================================================================

cd /d "%~dp0"

:: 1. Check for .env
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env >nul
        echo Please edit .env and set your TEAM_API_KEY.
    )
)

:: 2. Create .venv if not exists
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Ensure python is on PATH.
        exit /b 1
    )
)

:: 3. Activate .venv
call .venv\Scripts\activate.bat

:: 4. Install requirements
if exist "requirements.txt" (
    echo Installing dependencies...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
)

:: 5. Run main.py
echo Running main.py...
python main.py %*
