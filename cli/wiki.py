import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Auto-enforce virtual environment
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

console = Console()

def main():
    console.clear()

    wiki_markdown = """
# 📖 ViClaw Technical Wiki & Manual

Welcome to the definitive guide for ViClaw — an autonomous, local-first AI Agent.

---

## 1. The Terminal Super Menu
Running `viclaw` opens the Master Interface:

| Option | Action |
|--------|--------|
| **[1]** 💬 Interactive CLI Chat | Terminal conversation with the agent |
| **[2]** 🚀 Start/Restart Daemon | Launches background agent + WebUI |
| **[3]** 🛑 Stop Daemon | Gracefully kills the background process |
| **[4]** 📊 System Diagnostics | Poll CPU, RAM, Ollama registry, DB health |
| **[5]** 🩺 Agent Doctor | AI-powered self-healing Python diagnostics |
| **[6]** ⚙️  Update Configuration | Re-launches the setup wizard |
| **[7]** 📜 Chat History & Logs | Queries running daemon's `/api/history` live |
| **[8]** 🔄 Reinstall | Full reinstall, keeps memory intact |
| **[9]** 🗑️  Uninstall | Wipes daemon, venv, and data |
| **[10]** ☁️ OTA Updates | Pulls latest patches from GitHub |
| **[11]** 📖 ViClaw Wiki | This manual |

---

## 2. Interactive Chat Slash Commands
Type these directly in the chat interface:

| Command | Effect |
|---------|--------|
| `/reset` or `/new` | Clears short-term memory + SQLite checkpoint |
| `/status` | Active models, message count, skill roster |
| `/think [level]` | Sets reasoning verbosity for next response |
| `/compact` | Drops oldest half of context to save tokens |
| `/skills` | Lists all loaded tool schemas |
| `/update` | Triggers OTA updater engine inline |

---

## 3. Skills & ClawHub Marketplace
ViClaw uses **Skills (Tools)** for all external actions. Loaded at startup from `skills/`.

Built-in skills:

| Skill | What It Does |
|-------|-------------|
| `shell_engine` | Execute shell commands safely (MCP pattern) |
| `file_io` | Read, write, and build files on disk |
| `remote_ssh` | Execute commands on remote servers via Paramiko |
| `web_search` | DuckDuckGo scraper, returns ranked results |
| `homelab` | REST connector for HA, Sonarr, Radarr, Proxmox, etc. |
| `reminders` | Persistent scheduled task memory |
| `system_info` | CPU, RAM, disk, and uptime introspection |
| `sessions` | Agent-to-agent task delegation (Swarm) |

**Dynamic Skill Resolver:** If ViClaw encounters a task it has no tool for, it pauses and attempts to locate a matching skill on ClawHub. You approve the download — it's injected live without a restart.

**Hot Installs (Phase 30):** New skills are delta-loaded — only the new file is imported. Existing skills keep their runtime state untouched.

---

## 4. Auto-Dependency Healing
If any skill crashes due to a missing Python package (`ModuleNotFoundError`), ViClaw intercepts the stack trace, identifies the missing dependency, and asks your permission to run `pip install` or `apt-get install` automatically.

---

## 5. Network Discovery Scanner (50+ Services)
On installation, ViClaw actively maps your local subnet and hunts for:

- **Hypervisors:** Proxmox (8006), TrueNAS (80/443)
- **Media:** Plex (32400), Jellyfin (8096), Emby (8096)
- **Download:** Sonarr (8989), Radarr (7878), Prowlarr (9696), qBittorrent (8080)
- **SmartHome:** Home Assistant (8123), Node-RED (1880), Homebridge (8581)
- **Monitoring:** Grafana (3000), Portainer (9000), Netdata (19999)
- **Network:** Pi-Hole (80), AdGuard (3000), Nginx Proxy Manager (81)
- **Dev/DB:** Gitea (3000), Nextcloud (443), Vaultwarden (80)
- **Printers/IoT:** OctoPrint (5000), any SSH node (22)

Discovered services have their API tokens captured during the wizard. ViClaw can administer them autonomously.

---

## 6. Dashboards (3D & Tablet Kiosk)

### Main Dashboard `/dashboard`
3D animated glassmorphism UI with:
- Live chat with the agent (typing indicators, response paraphrasing)
- Diagnostic cards: daemon status, DB size, Ollama ping
- Skill browser and ClawHub installer
- Downloadable logs archive (ZIP)
- Agent Memory DB browser (live view of `short_term_checkpoint`)
- Document Vault (PDF/TXT ingestion into RAG)
- OTA update badge with one-click pull

### Tablet Kiosk `/kiosk`
Stream-Deck style glassmorphic layout:
- 3D animated speaking avatar (Jarvis mode)
- Clock, Pomodoro timer, Calendar widget
- Reminders integration
- Customizable iFrame grid for Home Assistant panels
- Atmospheric background adapts to time of day
- Full Web Speech API (STT voice input + TTS responses)

---

## 7. Security Model (Phase 30)

| What | How |
|------|-----|
| WebUI credentials | Set during install wizard, stored in `data/config.json` |
| No hardcoded defaults | Old `admin/claw` completely replaced |
| Session cookies | `httponly=True`, `samesite=lax`, 24h expiry |
| Automatic session cleanup | Expired sessions evicted hourly by background thread |
| Config isolation | `data/config.json` is gitignored — never committed |
| Memory isolation | `data/memory.db` is gitignored — your conversations are private |
| venv enforcement | All entry points `os.execv` into `.venv/bin/python3` |

To rotate credentials: run `viclaw` → `[6] Update Configuration`.

---

## 8. Memory Architecture (Phase 30)

ViClaw uses three memory layers:

| Layer | Storage | Behaviour |
|-------|---------|-----------|
| **Short-term** | RAM + SQLite checkpoint | Restored on daemon restart; per-session isolated |
| **Long-term** | SQLite `memories` table | Cosine similarity search via `nomic-embed-text` |
| **RAG Vault** | SQLite + embeddings | PDF/TXT document chunks ingested via WebUI |

The short-term checkpoint means **your conversation context survives daemon restarts**. It's wiped cleanly on `/reset` or when you uninstall.

---

## 9. Multi-Model AI Routing

ViClaw's `LLMRouter` analyses every message and routes silently:

| Role | Trigger | Example Models |
|------|---------|----------------|
| `fast` | Simple questions, routing, classification | `qwen2.5:3b` |
| `complex` | Long reasoning, analysis, planning | `llama3.2:8b` |
| `coding` | Code generation, debugging, scripting | `qwen2.5-coder` |
| `vision` | Base64 image inputs | `llava:latest` |

---

## 10. OTA Update System

ViClaw includes a background update engine (`core/updater.py`):
- Compares local vs remote Git HEAD SHA
- Stashes local config changes before pulling
- Updates pip dependencies if `requirements.txt` changed
- You control frequency (hourly/daily/weekly/manual) from the wizard

Trigger manually: `viclaw` → `[10] OTA Updates`.

---

## 11. Developer Notes

- **Config live reload:** `from core.config import reload_config; reload_config()` — no restart needed (Phase 30)
- **Thread-safe config:** `ConfigManager` is a `threading.RLock`-protected singleton
- **Delta skill loading:** `skill_manager._load_new_skills()` — only new files imported on ClawHub install
- **Heartbeat broadcasts** to all enabled platform connectors, not just `cli` (Phase 30)
- All data in `/data/` — delete only `config.json` to reset settings while keeping memory

For GUI access: `http://localhost:8501/wiki`
"""

    console.print(Panel.fit("[bold cyan]ViClaw Master Manual[/bold cyan] — v30", border_style="cyan"))
    console.print(Markdown(wiki_markdown))
    console.print("\n[dim]For GUI access, open http://localhost:8501/wiki on your network.[/dim]")

if __name__ == "__main__":
    main()
