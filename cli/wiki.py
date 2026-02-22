import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Auto-enforce virtual environment
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

console = Console()

def main():
    console.clear()
    
    wiki_markdown = """
# 📖 ViClaw Technical Wiki & Manual

Welcome to the definitive guide for ViClaw (OpenClaw Clone).

## 1. The Terminal Super Menu
Running `./viclaw` opens the Master Interface:
- **[1] Interactive CLI Chat:** Raw text stream conversation with the agent.
- **[2] Start/Restart Background Daemon:** Binds AI logic to background loop, exposing WebUI on Port 8501.
- **[4] System Diagnostics:** Polls CPU, RAM, Network, and Ollama registry.
- **[5] Agent Doctor:** Autonomous script to self-heal Python environment or kill rogue locks.
- **[7] View Chat History & Action Logs:** Dumps the SQLite `memory.db` directly to console.
- **[10] OTA Updates:** Pulls latest patches from GitHub (vignan07081999/ViClaw) and hot-swaps them.

## 2. Interactive Chat Slash Commands
Bypass normal LLM reasoning by typing these prefixed commands:
- `/clear` - Instantly wipes short-term memory array to clear hallucinations.
- `/status` - Returns diagnostic state of Agent (active model, loaded skills).
- `/skills` - Prints exhaustive list of loaded Python tools and JSON schemas.
- `/update` - Triggers the OTA Updater Engine directly from chat.

## 3. Skills & ClawHub Marketplace
ViClaw uses **Tools (Skills)** for external actions (web scraping, shell execution, etc.).
- **Dynamic Skill Resolver:** If ViClaw lacks a tool, it pauses and queries ClawHub. If approved by you, it downloads the script natively and injects it live.

## 4. Auto-Dependency Healing
If a script crashes because of missing packages (e.g. `requests`), ViClaw intercepts the stack trace and asks for permission to run `pip install` or `apt-get install` to auto-heal its own environment.

## 5. Network Discovery Scanner 50+
On installation, ViClaw maps the subnet for 50+ tier-one HomeLab signatures:
- Proxmox, TrueNAS, Portainer
- Plex, Jellyfin, Sonarr, Radarr
- Home Assistant, Homebridge, Node-RED
- Grafana, Pi-Hole, OctoPrint

## 6. Dashboards (3D & Tablet Kiosk)
Access Web UI on **Port 8501**:
- **3D Dashboard (`/dashboard`)**: Monitoring-focused UI for debugging, logging, and skill installation.
- **Stream Deck Kiosk (`/kiosk`)**: Glassmorphic layout for tablets. Features a 3D animated robot, atmospheric CSS mapping time of day, Pomodoro timers, and customizable iFrames for Home Assistant.
"""

    console.print(Panel.fit("[bold cyan]ViClaw Master Manual[/bold cyan]", border_style="cyan"))
    console.print(Markdown(wiki_markdown))
    console.print("\n[dim]For GUI access, open http://localhost:8501/wiki on your network.[/dim]")

if __name__ == "__main__":
    main()
