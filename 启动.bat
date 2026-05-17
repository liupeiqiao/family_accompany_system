@echo off
chcp 65001 >nul
title 亲情陪伴系统
setlocal enabledelayedexpansion

echo ================================
echo     🏠 亲情陪伴系统
echo ================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安装 Python，请从 https://python.org 下载安装
    pause
    exit /b 1
)

echo 📦 检查依赖...
pip install -r requirements.txt -q 2>nul

if "%DEEPSEEK_API_KEY%"=="" (
    echo.
    echo ⚠️  未设置 DEEPSEEK_API_KEY
    set /p API_KEY="请输入 DeepSeek API Key（回车跳过）: "
    if not "!API_KEY!"=="" set "DEEPSEEK_API_KEY=!API_KEY!"
)

echo.
echo 🚀 启动中... 浏览器打开 http://localhost:8501
echo    按 Ctrl+C 停止
echo.

python -m streamlit run app.py --server.port 8501 --server.headless true

pause
