@echo off
title Telegram Expense Tracker Bot Launcher
cd /d "%~dp0\.."

if not exist venv (
    echo Creating virtualenv...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

if not exist .env (
    copy .env.example .env
    echo Please edit .env file with your real BOT_TOKEN!
    pause
    exit /b
)

echo Starting Telegram Bot...
python bot.py
pause
