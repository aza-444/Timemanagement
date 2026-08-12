#!/bin/bash

# Exit on error
set -e

echo "=== Telegram Expense Bot Linux Installer & Autostart Setup ==="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "1. Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtualenv created."
fi

echo "2. Installing dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "3. Creating .env if not exists..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "CRITICAL: Please edit .env file and set your BOT_TOKEN before starting!"
fi

echo "4. Setting up Systemd Service..."
SERVICE_FILE="/etc/systemd/system/timemanagement_bot.service"
CURRENT_USER="$(whoami)"

cat <<EOF | sudo tee $SERVICE_FILE > /dev/null
[Unit]
Description=Telegram Expense Tracker Bot (Aiogram 3.x)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python bot.py
Restart=always
RestartSec=5
StandardOutput=append:$PROJECT_DIR/bot.log
StandardError=append:$PROJECT_DIR/bot.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "5. Enabling and starting Systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable timemanagement_bot
sudo systemctl restart timemanagement_bot

echo ""
echo "=== INSTALLATION COMPLETE ==="
echo "Status check command: sudo systemctl status timemanagement_bot"
echo "Logs command: tail -f $PROJECT_DIR/bot.log"
