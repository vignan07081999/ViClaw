#!/bin/bash
set -e

DIR="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "========================================================"
echo "          ViClaw Reinstaller                            "
echo "========================================================"

echo "This will wipe the current Python virtual environment and reinstall all dependencies."
read -p "Proceed? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    if systemctl list-units --full -all | grep -Fq "viclaw.service"; then
        echo "Stopping viclaw service temporarily..."
        sudo systemctl stop viclaw || true
    fi

    echo "Removing venv..."
    rm -rf .venv/

    echo "Re-running install shell script..."
    ./install.sh

    echo "Reinstallation complete!"
else
    echo "Reinstall aborted."
fi
