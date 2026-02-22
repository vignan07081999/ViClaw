# ViClaw 🐾 — Autonomous AI Agent for Linux & HomeLab

ViClaw is a powerful, **local-first, autonomous AI agent framework** built for Linux power users, HomeLab engineers, and self-hosted ecosystem builders.

It runs as an invisible background daemon on your server — managing Docker containers, running SSH commands across your subnet, querying APIs (Home Assistant, Proxmox, Radarr, Jellyfin, etc.), and maintaining a persistent, vector-embedded memory bank of everything you speak about.

---

## 🔥 Feature Highlights

| Feature | Description |
|---|---|
| **Zero-Touch Ollama Installer** | Wizard detects, installs, and pulls AI models automatically |
| **Multi-Model Complexity Router** | Routes prompts to fast/complex/coding models automatically |
| **HomeLab Network Scanner** | Discovers 50+ services (Proxmox, TrueNAS, HA, Sonarr, etc.) on install |
| **Proactive Heartbeat** | Agent spontaneously messages you on Telegram/Discord if idle |
| **OTA Git Updates** | Safely pulls GitHub patches and hot-swaps them without wiping your config |
| **3D Web Dashboard** | Premium Glassmorphism UI on port 8501 with 3D animated bot head |
| **Stream Deck Kiosk** | Tablet-optimized UI with timers, calendar, and iFrames |
| **RAG Memory Vault** | SQLite + Ollama `nomic-embed-text` cosine-similarity long-term memory |
| **Natural Language Cron** | "Remind me in 15 minutes" — a scheduler tracks this natively |
| **Multimodal Vision & Voice** | Image drops piped into `llava`, and Web Speech API TTS avatar |
| **Swarm Sub-Agents** | Deploy persona-constrained child agents for parallel sub-tasks |
| **Multi-User WebUI Auth** | Per-session authentication with config-stored credentials |
| **Hot ClawHub Installs** | Install skills at runtime without restarting the daemon |
| **Context Persistence** | Short-term memory checkpointed to SQLite — survives daemon restarts |
| **Live Config Reload** | Change settings without restarting — `reload_config()` re-reads disk |

---

## 🚀 Installation

ViClaw targets headless **Debian/Ubuntu**, CasaOS, Proxmox CTs, or Raspberry Pis with Python 3.9+.

### Requirements

```bash
sudo apt update && sudo apt install -y python3 python3-venv git curl
```

### One-Line Auto Deploy

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/vignan07081999/ViClaw/main/setup.sh)
```

This single command:
1. Clones the repo into `./ViClaw/`
2. Installs OS deps (`curl`, `lshw`, `python3-venv`) via apt
3. Builds an isolated `.venv` Python sandbox
4. Boots the interactive Setup Wizard
5. Detects and installs Ollama + pulls your selected models
6. Creates a `/usr/local/bin/viclaw` global command

### Manual Clone

```bash
git clone https://github.com/vignan07081999/ViClaw.git
cd ViClaw
chmod +x install.sh
./install.sh
```

---

## 🛠️ Usage

Once installed, `viclaw` is available globally. You never need to touch the Python virtual environment manually.

```
viclaw              → Opens the Super Master Menu
viclaw chat         → Drop directly into terminal chat
viclaw diagnostics  → Health check: Ollama ping, DB size, sys logs
viclaw doctor       → AI-powered self-healing diagnostics
```

### Super Menu Options

| Option | Action |
|---|---|
| `[1]` 💬 Interactive CLI Chat | Talk to the agent in your terminal |
| `[2]` 🚀 Start/Restart Daemon | Launches background agent + WebUI |
| `[3]` 🛑 Stop Daemon | Gracefully kills the background process |
| `[4]` 📊 Diagnostics | Polls CPU, RAM, Ollama, DB health |
| `[5]` 🩺 Doctor | Self-heals Python environment issues |
| `[6]` ⚙️ Update Configuration | Re-runs the wizard to change settings |
| `[7]` 📜 Chat History | Queries running daemon's `/api/history` live |
| `[8]` 🔄 Reinstall | Full reinstall without wiping memory |
| `[9]` 🗑️ Uninstall | Wipes daemon, venv, and data |
| `[10]` ☁️ OTA Updates | Pulls latest patches from GitHub |
| `[11]` 📖 ViClaw Wiki | Opens this manual in terminal |

### Slash Commands (in chat)

| Command | Effect |
|---|---|
| `/reset` or `/new` | Clears short-term memory + SQLite checkpoint |
| `/status` | Shows active models and message count |
| `/think [level]` | Adjusts reasoning verbosity |
| `/compact` | Compresses context to save memory |
| `/skills` | Lists all loaded tools |

---

## 🌐 Web Dashboard

ViClaw auto-detects port collisions and binds to the nearest open port (default: **8501**).

```
http://<SERVER_IP>:8501          → Login gateway
http://<SERVER_IP>:8501/dashboard → 3D animated dashboard
http://<SERVER_IP>:8501/kiosk     → Tablet Kiosk (Stream Deck mode)
http://<SERVER_IP>:8501/wiki      → This wiki in browser
```

### Security

- Credentials are set **during the install wizard** (`conf_webui` step)
- Stored in `data/config.json` under `webui.credentials` — never hardcoded
- Session cookies use `httponly=True`, `samesite=lax`
- Expired sessions are evicted automatically each hour
- Use `viclaw config` or re-run `./install.sh` to rotate credentials

---

## 🏗️ Architecture Overview

```
main.py            — Daemon entrypoint: OTA thread, platform manager, WebUI
launcher.py        — Cross-platform PID management (start/stop/restart)
install.py         — Interactive setup wizard (Rich + questionary TUI)
viclaw.py          — Super Menu CLI
viclaw             — Global wrapper (os.execv → .venv/bin/python3)

core/
  agent.py         — Main agentic loop: XML tool calls, heartbeat, swarm
  config.py        — Thread-safe ConfigManager with live reload()
  memory.py        — Short-term (SQLite checkpoint) + long-term (RAG/cosine)
  models.py        — LLMRouter: Ollama + LiteLLM, complexity routing, XML extraction
  updater.py       — OTA git pull engine
  scanner.py       — Subnet port scanner (50+ HomeLab signatures)
  scheduler.py     — Natural language cron (background thread)
  rag.py           — Document ingestion + vector search
  swarm.py         — Sub-agent delegation

skills/
  manager.py       — BaseSkill + SkillManager (delta hot-load on ClawHub install)
  shell_engine.py  — MCP shell execution
  file_io.py       — File read/write/build
  remote_ssh.py    — Paramiko remote server commands
  web_search.py    — DuckDuckGo scraper
  homelab.py       — REST API connector (HA, Sonarr, Radarr, Proxmox, etc.)
  reminders.py     — Persistent scheduled reminders
  system_info.py   — CPU/RAM/disk introspection
  sessions.py      — Agent-to-agent delegation
  clawhub_client.py— ClawHub marketplace downloader

integrations/
  messaging.py     — PlatformManager: Telegram, Discord, WhatsApp, CLI

webui/
  app.py           — FastAPI server (auth, chat, diagnostics, RAG, history)
  dashboard.html   — 3D animated premium dashboard
  kiosk.html       — Stream Deck tablet layout
  wiki.html        — This manual
```

---

## 🔒 Security Model

- **No hardcoded defaults**: Credentials are generated during wizard setup, never shipped in code
- **Config isolation**: `data/config.json` is in `.gitignore` — it never gets committed
- **Memory isolation**: `data/memory.db` is also gitignored — your conversations stay private
- **venv enforcement**: All entry points auto-exec into `.venv/bin/python3` to prevent system Python contamination
- **Session expiry**: WebUI sessions expire after 24h and are cleaned up hourly

---

## ♻️ Uninstallation

### Kill the Daemon

```bash
# Via launcher (recommended)
viclaw              # → Option [3] Stop Daemon

# Via systemd (if using systemd service)
sudo systemctl stop viclaw && sudo systemctl disable viclaw
sudo rm /etc/systemd/system/viclaw.service && sudo systemctl daemon-reload
```

### Full Wipe

```bash
rm -rf ~/ViClaw
```

### Remove Ollama Models (Optional — get disk space back)

```bash
ollama rm qwen2.5:3b
ollama rm qwen2.5-coder:latest
ollama rm llama3.2:3b
ollama rm nomic-embed-text  # RAG embedding model
```

### Uninstall Ollama Engine Completely

```bash
sudo systemctl stop ollama
sudo rm -rf /usr/local/bin/ollama /usr/share/ollama /etc/ollama
```

---

## 🛠️ Developer Notes

- **Config changes take effect live**: `from core.config import reload_config; reload_config()` — no restart needed
- **New skills hot-load**: `skill_manager._load_new_skills()` only imports new files, existing skills keep their runtime state
- **Context is persistent**: short-term context survives daemon restarts via `short_term_checkpoint` SQLite table
- **Heartbeat routes everywhere**: Proactive messages are sent to all enabled platform connectors, not just CLI
- All persistent data lives in `/data` — delete only `data/config.json` to reset config while keeping memory

---

## 📖 Full Wiki

See the in-app wiki at `http://<SERVER_IP>:8501/wiki` or run `viclaw` → `[11]`.