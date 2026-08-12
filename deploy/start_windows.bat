@echo off
title Telegram Expense Tracker Bot
cd /d "%~dp0\.."

echo ============================================
echo   Telegram Expense Tracker Bot
echo ============================================

:: ── Python mavjudligini tekshirish ───────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [XATO] Python topilmadi! https://python.org dan Python 3.10+ o'rnating.
    echo "PATH ga qo'shishni unutmang (Add to PATH belgilang)!"
    pause
    exit /b 1
)

:: ── Virtual muhit yaratish ────────────────────────────────────────────────────
if not exist venv (
    echo [INFO] Virtual muhit yaratilmoqda...
    python -m venv venv
    if errorlevel 1 (
        echo [XATO] Virtual muhit yaratib bo'lmadi!
        pause
        exit /b 1
    )
)

:: ── Aktivatsiya ───────────────────────────────────────────────────────────────
call venv\Scripts\activate.bat

:: ── Kutubxonalarni o'rnatish ──────────────────────────────────────────────────
echo [INFO] Kutubxonalar tekshirilmoqda...
pip install --upgrade pip -q
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [XATO] requirements.txt o'rnatib bo'lmadi!
    pause
    exit /b 1
)

:: ── .env fayl tekshiruvi ──────────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [DIQQAT] .env fayli yaratildi. BOT_TOKEN ni kiriting!
        notepad .env
        pause
        exit /b 0
    ) else (
        echo [XATO] .env fayli topilmadi va .env.example ham yo'q!
        pause
        exit /b 1
    )
)

:: ── Botni ishga tushirish ─────────────────────────────────────────────────────
echo [INFO] Bot ishga tushirilmoqda...
echo [INFO] To'xtatish uchun: Ctrl+C
echo ============================================
python bot.py

echo.
echo [INFO] Bot to'xtadi.
pause
