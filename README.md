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

---

## 🚀 Installation & Setup

ViClaw is designed to be installed on headless Debian/Ubuntu Linux distributions, lightweight containers (like CasaOS or Proxmox CTs), or Raspberry Pis.

### 1. Requirements

You must have **Python 3.9+** and `git` installed.

```bash
# On Debian / Ubuntu
sudo apt update && sudo apt install -y python3 python3-venv git
```

### 2. Clone & Execute

```bash
git clone https://github.com/vignan07081999/ViClaw.git
cd ViClaw
chmod +x install.sh
./install.sh
```

**The script handles everything:**
1. It downloads OS dependencies (`curl`, `lshw`, `python3-venv`).
2. It builds isolated Python environments for execution safety.
3. The Setup Wizard will boot. **If you don't have Ollama installed**, tell the setup wizard YES, and it will deploy the local daemon natively and pull the models automatically.
4. It will bind the WebUI and background daemon scripts.

### 3. Usage & Interacting

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