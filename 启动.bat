@echo off
title Family Companion

echo ================================
echo    Family Companion System
echo ================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

echo Installing dependencies...
python -m pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    echo.
    echo Retrying...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Install failed. Try: python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

if "%DEEPSEEK_API_KEY%"=="" (
    echo.
    echo WARNING: DEEPSEEK_API_KEY not set
    set /p DEEPSEEK_API_KEY="Enter your DeepSeek API Key (or press Enter to skip): "
    echo.
)

echo.
echo Starting... Open http://localhost:8501
echo.

python -m streamlit run app.py --server.port 8501
pause
