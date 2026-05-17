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

set DEEPSEEK_API_KEY=sk-032e2e8065ae4e66a64a95d8fea81dd7

echo.
echo Starting... Open http://localhost:8501
echo.

echo Trying port 8501...
python -m streamlit run app.py --server.port 8501 --server.headless true 2>nul
if errorlevel 1 (
    echo Port 8501 busy, trying 8502...
    python -m streamlit run app.py --server.port 8502 --server.headless true
)
pause
