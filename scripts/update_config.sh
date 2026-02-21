#!/bin/bash
set -e

DIR="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "========================================================"
echo "          ViClaw Configuration Updater                  "
echo "========================================================"

if [ ! -d "venv" ]; then
    echo "ViClaw is not installed. Please run install.sh first."
    exit 1
fi

source venv/bin/activate
python install.py

# Restart the service if it exists to apply new config
if systemctl list-units --full -all | grep -Fq "viclaw.service"; then
    echo "Restarting viclaw service to apply configuration..."
    sudo systemctl restart viclaw
    echo "Service restarted."
fi
