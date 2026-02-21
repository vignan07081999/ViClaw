#!/bin/bash

set -e

echo "========================================================"
echo "          OpenClaw Clone - Interactive Installer        "
echo "========================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if Python > 3.9 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.9+ first.${NC}"
    exit 1
fi

echo -e "${GREEN}Creating Python Virtual Environment...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}Installing Requirements...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${GREEN}Starting Guided Configuration Wizard...${NC}"
python install.py

echo -e "${GREEN}Installation Complete! Activate the virtual environment using 'source venv/bin/activate' and run 'python main.py' to start.${NC}"
