# 🐾 ViClaw — The Ultimate Autonomous AI Agent for Linux Power Users & HomeLab Builders

**ViClaw** is a powerful, local-first, highly autonomous AI Agent framework designed explicitly for Linux enthusiasts, HomeLab tinkerers, and DevSecOps engineers. It runs invisibly as a background daemon on your server, acting as your personal intelligence layer. 

From managing Docker clusters to routing SSH commands across your subnet, querying Home Assistant, summarizing web links, or running isolated sub-agents—ViClaw represents the pinnacle of private, persistent AI automation.

![Licence](https://img.shields.io/badge/License-MIT-blue.svg) ![Python](https://img.shields.io/badge/Python-3.9%2B-green) ![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-lightgrey)

---

## 🌟 What's New?
We recently completed a massive architecture upgrade, pushing ViClaw beyond a chat bot into a true autonomous entity:
- 🎙️ **Native TTS Engine:** Offline Edge-TTS (`pyttsx3`) audio generation streams speech natively in the WebUI.
- 🌐 **Browser Automation (Playwright):** ViClaw can launch headless chromium to visually inspect websites, scrape JS-heavy content, and screenshot UI layouts for analysis.
- 💬 **Live Typing Indicators:** Integrated native "is typing..." indicators for Telegram, Discord, and WebUI streams.
- 🔄 **Autonomous Failover Chains:** If your primary LLM crashes, ViClaw transparently routes inference to fallback models.
- 🧠 **Named Sessions & RAG Memory:** Keep hundreds of isolated context containers via SQLite, enriched with localized vector embeddings (`nomic-embed-text`).
- 📂 **Daemon Watchdog Hooks:** Drop a file into `data/dropzone` and ViClaw will detect it, analyze the contents silently in the background, and summarize it for you.
- 📊 **Usage Metrics:** Granular SQLite token-tracking, latency measuring, and price estimation.
- ⚡ **ACP Stdio Bridge:** Control ViClaw synchronously from your IDE (Zed, Cursor) using the native NDJSON bridge `viclaw acp`.

---

## 🔥 Core Feature Highlights

| Feature | Description |
|---|---|
| **Zero-Touch AI Installer** | The wizard sniffs your network, identifies needed dependencies, tests AI models live, and talks you through the installation process contextually. |
| **Multi-Model Complexity Router** | Seamlessly routes prompts to fast models, complex models, or coding models based on regex and prompt heuristics. |
| **HomeLab Network Scanner** | Discovers 50+ self-hosted services (Proxmox, TrueNAS, Home Assistant, Sonarr, etc.) and auto-configures API access. |
| **Swarm Sub-Agents** | Deploy constrained child agents to parallelize heavily structured execution pipelines. |
| **Doctor CLI & Auto-Healing** | `viclaw doctor` recursively sanitizes missing dependencies, databases, or broken plugins. Even runtime errors trigger "May I run pip install this for you?" |
| **Live OTA Git Updates** | Trigger `updater.py` directly from chat to pull GitHub patches and safely hot-swap modules without dropping the daemon process. |
| **Premium 3D Dashboard** | Glassmorphism Web User Interface served locally on port `8501` featuring SSE-streaming and live markdown rendering. |
| **Hot ClawHub Installs** | Missed a tool? ViClaw searches our marketplace and hot-loads skills via `importlib` delta-loads. |

---

## 🚀 Installation

Target Environments: Headless **Debian/Ubuntu**, CasaOS, Proxmox CTs, macOS, or Raspberry Pi. 

**Requirements:**
```bash
sudo apt update && sudo apt install -y python3 python3-venv git curl
```

**One-Line Auto Deploy:**
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/vignan07081999/ViClaw/main/setup.sh)
```
*(Optionally, use standard `git clone` and execute `./install.sh`)*

The Guided Installer will explicitly check for system dependencies like `playwright` (Chromium) and `pyttsx3` dependencies, initialize the isolated Python virtual environment, ping your Ollama layer, and launch the conversational wizard to set up Telegram/Discord.

---

## 🛠️ Usage

ViClaw generates a global `/usr/local/bin/viclaw` mapping so you never touch the virtual environment directly. Simply run:
```bash
viclaw
```
This opens the Super Master TUI where you can:
1. Access the terminal-based interactive chat `viclaw chat`.
2. Launch or gracefully stop the Daemon.
3. Access telemetry (`viclaw diagnostics`) or trigger self-healing (`viclaw doctor`).

### Powerful Chat Slash Commands
| Command | Effect |
|---|---|
| `/new [name]` | Immediately creates a clean context session without wiping history. |
| `/poll create` | Spin up interactive interactive polls. |
| `/think [level]` | Toggle `<think>` verbosity parsing off/on. |
| `/skills` | Lists all loaded JSON Schema tool definitions. |

---

## 🌐 The 3D Web Dashboard

ViClaw binds to the nearest open port (default: **8501**).
- **`http://<SERVER_IP>:8501/dashboard`** — Premium web chat, diagnostics, TTS playback, and live system logging. 
- **`http://<SERVER_IP>:8501/kiosk`** — Optimized stream-deck interface for tablets with smart clocks and API widgets.
- **`http://<SERVER_IP>:8501/wiki`** — A detailed hyperlinked repository manual.

---

## 🔒 Security Model & DevSecOps Guarantee
We deeply respect local-first security paradigms:
- **No hardcoded defaults**: Credentials are set precisely during wizard generation.
- **Environment Isolation**: The app exclusively operates inside an ironclad `.venv`.
- **Pre-Deployment Audited**: The `viclaw` repository boasts a guaranteed passing score across Bandit (SAST), Safety (Dependency Checks), Flake8, and Radon.
- **Stateless Exposure**: Passwords or `.json` secrets never touch standard error outputs. 

Enjoy your autonomous network entity! 🐾