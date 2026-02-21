#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "========================================================"
echo "          ViClaw (OpenClaw Clone) Installer             "
echo "========================================================"

echo "Checking for base OS dependencies..."
if ! command -v curl &> /dev/null || ! command -v lshw &> /dev/null; then
    echo "Attempting to install curl and lshw..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y curl lshw
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y curl lshw
    elif command -v pacman &> /dev/null; then
        sudo pacman -Sy --noconfirm curl lshw
    else
        echo "Could not find a supported package manager. Please install 'curl' and 'lshw' manually."
    fi
fi

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.9+ first."
    exit 1
fi

echo "Creating Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing Requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting Guided Configuration Wizard..."
python install.py

# Setup Systemd Service if root/sudo is available, else provide manual instructions
echo "Setting up systemd service to run ViClaw automatically..."
SERVICE_FILE="/etc/systemd/system/viclaw.service"

# Generate the service file content
cat << EOF > /tmp/viclaw.service
[Unit]
Description=ViClaw AI Agent Daemon
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

if [ "$EUID" -eq 0 ]; then
    mv /tmp/viclaw.service $SERVICE_FILE
    systemctl daemon-reload
    systemctl enable viclaw
    systemctl start viclaw
    echo "Service installed and started. Check status with 'systemctl status viclaw'."
elif command -v sudo &> /dev/null && [ -n "$SUDO_USER" ] || sudo -n true 2>/dev/null; then
    sudo mv /tmp/viclaw.service $SERVICE_FILE
    sudo systemctl daemon-reload
    sudo systemctl enable viclaw
    sudo systemctl start viclaw
    echo "Service installed and started via sudo. Check status with 'sudo systemctl status viclaw'."
else
    echo "Not running as root. To install the service manually so the agent auto-starts on reboot, run:"
    echo "sudo mv /tmp/viclaw.service /etc/systemd/system/viclaw.service"
    echo "sudo systemctl daemon-reload && sudo systemctl enable viclaw && sudo systemctl start viclaw"
fi
