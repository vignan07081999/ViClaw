# ViClaw (OpenClaw Python Clone) 🐾

ViClaw is an immensely powerful, local-first, autonomous AI agent framework designed specifically for Linux hackers, HomeLab engineers, and self-hosted ecosystem integrators. 

It acts as an intelligent, proactive daemon running invisibly on your server—capable of managing Docker containers, executing SSH commands globally across your subnet, probing APIs (Home Assistant, Proxmox, Radarr, etc.), and remembering everything you talk about via long-term persistent memory banks.

## 🔥 Core Features

- **Zero-Touch Local AI**: The wizard natively detects and installs the `ollama` inferencing engine if you don't have it. ViClaw will completely autonomously pull curated models (like `qwen2.5` and `llama3.2`) and serve them itself.
- **Autonomous Complexity Routing**: You don't need to manually switch AI models. `LLMRouter` analyzes every prompt you send. Need to write a script? ViClaw silently connects to `qwen2.5-coder`. Need a quick server ping? It routes to a blazing fast 3-billion-parameter model to save RAM.
- **HomeLab Network Scanner**: ViClaw actively maps your `192.168.x.x` subnet during installation, hunting for Proxmox, TrueNAS, Sonarr, Radarr, Jellyfin, and SSH nodes. It prompts you for their API Tokens and stores them securely so the AI can administer your entire infrastructure organically.
- **Proactive Heartbeat**: ViClaw doesn't just respond mechanically—it thinks. A background heartbeat occasionally wakes the LLM up, allowing it to spontaneously message you on Telegram/Discord if a server goes down or if it has an idle thought.
- **Over-The-Air Git Updates**: Built-in OTA functionality safely checks Github for pushes, downloads new skills, and restarts the daemon automatically without wiping your private `data/config.json`.
- **Dynamic 3D Web Dashboard**: Access a stunning 3D Glassmorphism UI hosted locally to chat with the agent, view diagnostic metrics, and read the raw JSON reasoning logs parsing in real-time.
- **Swarm Sub-agents**: Deploy dynamic, persona-driven child agents to run sub-tasks natively with constrained permissions.
- **RAG Memory Vault**: ViClaw remembers. It commits facts to an internal SQLite vector graph via `nomic-embed-text` and performs Cosine Similarity lookups.
- **Natural Language Cron**: "Remind me to check the oven in 15 minutes". A background python daemon natively tracks and schedules future LLM generations.
- **Multimodal Vision & Voice**: The Kiosk supports native Text-to-Speech avatars, and the web app accepts Base64 image drops seamlessly piped into models like `llava`.

## 🚀 Installation & Setup

ViClaw is designed to be installed on headless Debian/Ubuntu Linux distributions, lightweight containers (like CasaOS or Proxmox CTs), or Raspberry Pis.

### 1. Requirements

You must have **Python 3.9+** and `git` installed.

```bash
# On Debian / Ubuntu
sudo apt update && sudo apt install -y python3 python3-venv git curl
```

### 2. Global Installation Snippet

You can completely auto-deploy the Github repository and trigger the Setup Wizard seamlessly via this single line snippet from any working directory:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/vignan07081999/ViClaw/main/setup.sh)
```

**What this snippet does natively:**
1. Verifies `git` exists and clones the agent into a `./ViClaw/` directory safely.
2. Changes permissions and automatically boots `./install.sh`.
3. Downloads OS dependencies (`curl`, `lshw`, `python3-venv`) via apt/pacman contextually.
4. Builds an isolated `.venv` Python sandbox array natively avoiding global overlaps.
5. Boots the Setup Wizard. If Ollama is missing, the wizard injects it naturally.

### 3. Global Uninstaller Snippet

If you want to completely wipe ViClaw, its virtual environment, the systemd daemon, and all User Data Memory databases interactively, run:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/vignan07081999/ViClaw/main/uninstall.sh)
```

### 4. Manual Clone & Execute

If you prefer to review the source code manually before executing scripts, bypass the global setup snippet and clone manually:

```bash
git clone https://github.com/vignan07081999/ViClaw.git
cd ViClaw
chmod +x install.sh
./install.sh
```

### 5. Usage & Interacting

Once installed, we created a global wrapper script so you never have to mess with Python virtual environments manually. Everything is executed through `./viclaw`.

- `./viclaw` - Opens the Super Master Control Menu.
- `./viclaw chat` - Drop directly into the local terminal chat interface.
- `./viclaw diagnostics` - Check connection latency, database health, and memory buffer states.
- `./viclaw doctor` - Automatically reads system crash logs and uses the LLM to recursively debug the Python codebase.

### The Web Dashboard 🌐

ViClaw dynamically spins up a beautiful UI. CasaOS usually blocks port `8501`. ViClaw will **auto-detect collisions** and bind to the nearest open port (e.g., `8502`).

Access it on your local network:
`http://<SERVER_IP>:8501/dashboard` (check terminal output for exact port).

---

## 🗑️ Uninstallation 

If you want to completely scrub ViClaw from your host node:

### 1. Kill the Daemon

If you used the Systemd daemon wrapper:
```bash
sudo systemctl stop viclaw
sudo systemctl disable viclaw
sudo rm /etc/systemd/system/viclaw.service
sudo systemctl daemon-reload
```

If you used the cross-platform launcher:
```bash
cd ViClaw
./viclaw launcher stop
```

### 2. Nuke the Directory
```bash
rm -rf ~/ViClaw
```

### 3. Uninstall Ollama Models (Optional)
If you told ViClaw to automatically download massive 3B and 8B parameter Local LLM weights and you want your SSD space back:
```bash
ollama rm qwen2.5:3b
ollama rm qwen2.5-coder
ollama rm llama3.2:3b
```
If you want to completely uninstall the Ollama daemon:
```bash
sudo systemctl stop ollama
sudo rm -rf /usr/local/bin/ollama /usr/share/ollama /etc/ollama
```

---

## 🛠️ Modding & Architecture

All persistent data, memory databases, and configuration settings are securely sandboxed inside the `/data` folder. If you screw up the installation, you don't need to reinstall the python modules. Just delete `data/config.json` and type `./viclaw` to trigger the setup wizard organically again!

---

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