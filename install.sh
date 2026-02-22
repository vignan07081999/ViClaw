#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "========================================================"
echo "          ViClaw Installer             "
echo "========================================================"

echo "=== Phase 31.4: Scorched Earth Environment Cleanup ==="
echo "Purging stale processes..."
pkill -f viclaw || true
pkill -f main.py || true
pkill -f uvicorn || true
rm -f data/viclaw.pid 2>/dev/null || true

echo "Sanitizing shell profiles... (Removing legacy OpenClaw/ViClaw paths)"
_sanitize_profile() {
    local FILE="$1"
    if [ -f "$FILE" ]; then
        # Use a portable temporary file approach for sed -i compatibility
        sed '/openclaw/d' "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"
        sed '/viclaw/d' "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"
        echo "✓ Sanitized $FILE"
    fi
}

_sanitize_profile "/root/.bashrc"
_sanitize_profile "/root/.profile"
_sanitize_profile "/root/.bash_profile"
_sanitize_profile "$HOME/.bashrc"
_sanitize_profile "$HOME/.profile"

echo "Checking for base OS dependencies..."
if ! command -v curl &> /dev/null || ! command -v lshw &> /dev/null || ( command -v dpkg &> /dev/null && ! dpkg-query -W -f='${Status}' python3-venv 2>/dev/null | grep -q "ok installed" ); then
    echo "Attempting to install curl, lshw, and python3-venv..."
    
    SUDO=""
    if [ "$EUID" -ne 0 ]; then
        if command -v sudo &> /dev/null; then
            SUDO="sudo"
        else
            echo "You are not root and sudo is not installed. Please run this script as root."
            exit 1
        fi
    fi

    if command -v apt-get &> /dev/null; then
        $SUDO apt-get update && $SUDO apt-get install -y curl lshw python3-venv
    elif command -v dnf &> /dev/null; then
        $SUDO dnf install -y curl lshw python3
    elif command -v pacman &> /dev/null; then
        $SUDO pacman -Sy --noconfirm curl lshw python
    else
        echo "Could not find a supported package manager. Please install 'curl', 'lshw', and 'python3-venv' manually."
    fi
fi

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.9+ first."
    exit 1
fi

echo "Creating Python Virtual Environment..."
rm -rf .venv
if ! python3 -m venv .venv 2>/dev/null; then
    echo "Standard venv creation failed or ensurepip is missing. Attempting robust fallback..."
    rm -rf .venv
    python3 -m venv .venv --without-pip || { echo "Fatal Error: Failed to create python environment even without pip. Ensure python3 is installed correctly."; exit 1; }
    source .venv/bin/activate
    curl -fsSL https://bootstrap.pypa.io/get-pip.py | python3
else
    source .venv/bin/activate
fi

echo "Installing Requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting Guided Configuration Wizard..."
.venv/bin/python3 install.py

# ── Global CLI wrapper ──────────────────────────────────────────────────────
echo "Setting up global 'viclaw' command..."

VICLAW_SHIM="/usr/local/bin/viclaw"

# Write a real bash shim (not a symlink to a Python file).
# This works regardless of whether python3 is in PATH at the shebang level.
SHIM_CONTENT="#!/bin/bash
exec \"$DIR/.venv/bin/python3\" \"$DIR/viclaw\" \"\$@\""

_install_shim() {
    mkdir -p /usr/local/bin
    printf '%s\n' "$SHIM_CONTENT" > "$VICLAW_SHIM"
    chmod +x "$VICLAW_SHIM"
}

if [ "$EUID" -eq 0 ]; then
    _install_shim
elif command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
    sudo bash -c "$(declare -f _install_shim); VICLAW_SHIM='$VICLAW_SHIM'; SHIM_CONTENT=$(printf '%q' "$SHIM_CONTENT"); _install_shim"
else
    # Fall back: write to $HOME/.local/bin and patch PATH
    mkdir -p "$HOME/.local/bin"
    VICLAW_SHIM="$HOME/.local/bin/viclaw"
    printf '%s\n' "$SHIM_CONTENT" > "$VICLAW_SHIM"
    chmod +x "$VICLAW_SHIM"
    echo "WARNING: Could not write to /usr/local/bin. Installed to $HOME/.local/bin instead."
fi

echo "✓ Global command installed at: $VICLAW_SHIM"

# ── Ensure /usr/local/bin is in PATH ────────────────────────────────────────
# Aggressively patch every relevant profile for root and standard users.
_patch_path() {
    local FILE="$1"
    local LINE='export PATH="$PATH:/usr/local/bin:$HOME/.local/bin"'
    if [ -f "$FILE" ]; then
        if ! grep -q "/usr/local/bin" "$FILE" 2>/dev/null; then
            echo "" >> "$FILE"
            echo "# Added by ViClaw installer" >> "$FILE"
            echo "$LINE" >> "$FILE"
            echo "✓ PATH updated in $FILE"
        fi
    fi
}

# Root-specific profiles (CasaOS defaults)
_patch_path "/root/.bashrc"
_patch_path "/root/.profile"
_patch_path "/root/.bash_profile"
# Global profiles
_patch_path "/etc/bash.bashrc"
_patch_path "/etc/profile"
# User profiles
_patch_path "$HOME/.bashrc"
_patch_path "$HOME/.profile"

# Patch /etc/environment for system-wide static PATH
if [ -f /etc/environment ]; then
    if ! grep -q "/usr/local/bin" /etc/environment; then
        sed -i 's|^PATH="\(.*\)"|PATH="\1:/usr/local/bin"|' /etc/environment 2>/dev/null || true
        echo "✓ /etc/environment updated"
    fi
fi

# Make the shim immediately available in the current shell session
export PATH="$PATH:/usr/local/bin:$HOME/.local/bin"

# ── Systemd Service ──────────────────────────────────────────────────────────
echo "Setting up systemd service to run ViClaw automatically..."
SERVICE_FILE="/etc/systemd/system/viclaw.service"

cat <<EOF > /tmp/viclaw.service
[Unit]
Description=ViClaw AI Agent Daemon
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python3 $DIR/main.py
Restart=always
RestartSec=10
Environment="PATH=$PATH"

[Install]
WantedBy=multi-user.target
EOF

if [ "$EUID" -eq 0 ]; then
    mv /tmp/viclaw.service $SERVICE_FILE
    systemctl daemon-reload
    systemctl enable viclaw
    systemctl start viclaw
    echo "Service installed and started. Check status with 'systemctl status viclaw'."
elif command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
    sudo mv /tmp/viclaw.service $SERVICE_FILE
    sudo systemctl daemon-reload
    sudo systemctl enable viclaw
    sudo systemctl start viclaw
    echo "Service installed and started via sudo. Check status with 'sudo systemctl status viclaw'."
else
    echo "Not running as root. To install the service manually so the agent auto-starts on reboot, run:"
    echo "  sudo mv /tmp/viclaw.service /etc/systemd/system/viclaw.service"
    echo "  sudo systemctl daemon-reload && sudo systemctl enable viclaw && sudo systemctl start viclaw"
fi

# ── Finish ──────────────────────────────────────────────────────────────────
clear
echo "========================================================"
echo "          ViClaw Installation Complete!                 "
echo "========================================================"
echo ""
echo "!!! ACTION REQUIRED TO ENABLE COMMANDS !!!"
echo "To use the 'viclaw' command in this terminal, run:"
echo ""
echo "    source ~/.bashrc"
echo ""
echo "Then you can run:"
echo "    viclaw chat          - Open the interactive CLI"
echo "    viclaw diagnostics   - Check system health"
echo "    viclaw doctor        - Troubleshoot setup"
echo "    viclaw --help        - List all available commands"
echo ""
echo "WebUI is available at: http://localhost:8501"
echo "========================================================"
