#!/bin/bash
set -e

DIR="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "========================================================"
echo "          ViClaw Uninstaller                            "
echo "========================================================"
echo "This will remove the ViClaw systemd service and delete the repository folder."
read -p "Are you sure you want to completely uninstall ViClaw? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    if systemctl list-units --full -all | grep -Fq "viclaw.service"; then
        echo "Stopping and removing systemd service..."
        sudo systemctl stop viclaw || true
        sudo systemctl disable viclaw || true
        sudo rm -f /etc/systemd/system/viclaw.service
        sudo systemctl daemon-reload
    fi
    
    echo "Removing repository directory ($DIR)..."
    cd ..
    rm -rf "$DIR"
    echo "ViClaw has been successfully uninstalled."
else
    echo "Uninstall aborted."
fi
