#!/bin/bash
set -e

# Auto-detect ViClaw directory if piped via curl
if [ -f "viclaw" ] && [ -d ".venv" ]; then
    echo "Detected ViClaw installation in current directory: $PWD"
elif [ -d "ViClaw" ] && [ -f "ViClaw/viclaw" ]; then
    echo "Detected ViClaw installation in ./ViClaw"
    cd ViClaw
elif [ -d "$HOME/ViClaw" ] && [ -f "$HOME/ViClaw/viclaw" ]; then
    echo "Detected ViClaw installation in $HOME/ViClaw"
    cd "$HOME/ViClaw"
else
    read -p "Could not auto-detect ViClaw folder. Enter the absolute path to your ViClaw installation directory: " custom_path
    if [ -d "$custom_path" ] && [ -f "$custom_path/viclaw" ]; then
        cd "$custom_path"
    else
        echo "Valid ViClaw installation not found at that path. Exiting."
        exit 1
    fi
fi

echo "========================================================"
echo "          ViClaw (OpenClaw Clone) Uninstaller           "
echo "========================================================"
echo "Warning: This action is destructive and will remove ViClaw from your system."
echo

read -p "1. Do you want to stop and remove the background systemd daemon? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if systemctl is-active --quiet viclaw 2>/dev/null; then
        echo "Stopping viclaw daemon..."
        sudo systemctl stop viclaw || true
        sudo systemctl disable viclaw || true
        sudo rm -f /etc/systemd/system/viclaw.service || true
        sudo systemctl daemon-reload || true
        echo "✓ Systemd daemon removed."
    else
        echo "- Systemd daemon not active or not found."
    fi
fi

read -p "2. Do you want to delete the Python Virtual Environment (.venv)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d ".venv" ]; then
        rm -rf .venv
        echo "✓ .venv deleted."
    else
        echo "- .venv directory not found."
    fi
fi

read -p "3. Do you want to delete all user data, configuration (config.json), memories, and SQLite DBs? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "data" ]; then
        rm -rf data
        echo "✓ User data deleted."
    else
        echo "- Data directory not found."
    fi
fi

read -p "4. Do you want to delete downloaded local AI models via Ollama? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v ollama &> /dev/null; then
        echo ""
        echo "Below are your installed Ollama models:"
        ollama list
        echo ""
        read -p "Enter the exact name of a model to delete (or press Enter to skip): " model_to_del
        if [ ! -z "$model_to_del" ]; then
            ollama rm "$model_to_del"
            echo "✓ Model deleted."
        fi
        echo "Note: You can permanently remove Ollama itself using 'sudo systemctl stop ollama' and removing its binaries."
    else
        echo "- Ollama engine not found natively."
    fi
fi

echo ""
echo "========================================================"
echo "          TOTAL WIPEOUT MODE (CLEAN SLATE)             "
echo "========================================================"
read -p "6. Do you want to wipe ALL footprints (temp files, caches, logs)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Wiping temporary files..."
    rm -rf /tmp/viclaw_* 2>/dev/null || true
    echo "Wiping python caches..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo "Wiping data folder..."
    rm -rf data 2>/dev/null || true
    echo "✓ System footprints wiped."
fi

echo ""
echo "========================================================"
read -p "7. **DANGER**: Do you want to completely delete this entire ViClaw repository folder? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    LOCAL_DIR=$PWD
    cd ..
    # Clean up any residual /tmp items before self-destructing
    rm -rf /tmp/viclaw_* 2>/dev/null || true
    rm -rf "$LOCAL_DIR"
    echo "✓ ViClaw repository completely deleted from disk."
    echo "A TRUE FRESH START HAS BEEN PREPARED."
    exit 0
fi

echo ""
echo "Uninstallation process complete."
