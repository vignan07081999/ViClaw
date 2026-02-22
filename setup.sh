#!/bin/bash
set -e

echo "========================================================"
echo "          ViClaw Setup Script          "
echo "========================================================"

if ! command -v git &> /dev/null; then
    echo "Git is not installed. Please install git first."
    exit 1
fi

DEST_DIR="ViClaw"

if [ -d "$DEST_DIR" ]; then
    echo "Directory $DEST_DIR already exists. Please remove it or run ./install.sh from inside it."
    exit 1
fi

echo "Cloning ViClaw repository..."
git clone https://github.com/vignan07081999/ViClaw.git "$DEST_DIR"

cd "$DEST_DIR"
chmod +x install.sh
chmod +x uninstall.sh
chmod +x viclaw

echo "Starting installation..."
./install.sh
