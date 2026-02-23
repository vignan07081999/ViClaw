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
| **[   ]** *ACP Bridge* | Run `viclaw acp` directly for the IDE JSON bridge |
| **[   ]** *Usage Telemetry* | Run `viclaw usage` for token statistics |

---

## 2. Interactive Chat Slash Commands
Type these directly in the chat interface:

| Command | Effect |
|---------|--------|
| `/reset` or `/new` | Clears short-term memory + SQLite checkpoint |
| `/new [name]` | Immediately creates a clean named session context |
| `/poll create` | Spin up interactive interactive polls |
| `/status` | Active models, message count, skill roster |
| `/think [level]` | Sets reasoning verbosity for next response |
| `/skills` | Lists all loaded tool schemas |

---

## 3. Core Engine Upgrades
ViClaw has been heavily expanded with autonomous sub-systems:

- **AI-Guided Installation:** The setup wizard tests models live and actively narrates your installation.
- **Failover Chain:** If the primary model fails or times out, ViClaw seamlessly routes execution to the backup model.
- **Background Watchdog Hooks:** Drop any text/PDF file into `data/dropzone/` and ViClaw will detect, analyze, and report on it silently.
- **Playwright Browser Skimming:** The integrated Browser Skill can launch Chromium headless to visually analyze or scrape sites.
- **TTS Audio Engine:** Utilizes local `pyttsx3` to stream audio responses automatically in the WebUI.
- **Typing Indicators:** Real-time Dispatch of `/typing` actions across Discord, Telegram, and the WebUI while the model executes tools.
- **Network Discovery Scanner:** Maps 50+ HomeLab services (Proxmox, TrueNAS, Home Assistant) silently.

---

## 4. Dashboards (3D & Tablet Kiosk)
ViClaw binds to port **8501**:
- **Main Dashboard (`/dashboard`):** 3D animated UI with live chat, token tracking, diagnostics, log archives, and Skill browsing.
- **Tablet Kiosk (`/kiosk`):** Smart Clock, Timer, RSS panels, and an embedded Speech-To-Text Voice API for ambient interaction.
- **Auth Model:** Session cookies use `httponly=True`, `samesite=lax`, with credentials hardened in `data/config.json`.

---

## 5. Multi-Model AI Routing
ViClaw's `LLMRouter` routes inferencing silently to optimize speed vs complexity:

| Role | Trigger | Example Models |
|------|---------|----------------|
| `fast` | Routine tasks, simple parsing | `qwen2.5:3b` |
| `complex`| Heavy analysis, web scraping | `llama3.2:8b` |
| `coding` | Tool extraction, bash commands| `qwen2.5-coder` |

---

## 6. Developer Notes
- **ACP Integration:** Point your cursor/zed IDE at `viclaw acp` to establish a direct stdio-bound NDJSON connection.
- **Config live reload:** `reload_config()` updates internal memory without restarting.
- **Security Audit:** ViClaw has achieved 100% compliance against SAST (Bandit), Mypy, Pylint, and Radon metrics.

For GUI access: `http://localhost:8501/wiki`
"""

    console.print(Panel.fit("[bold cyan]ViClaw Master Manual[/bold cyan] — v30", border_style="cyan"))
    console.print(Markdown(wiki_markdown))
    console.print("\n[dim]For GUI access, open http://localhost:8501/wiki on your network.[/dim]")

if __name__ == "__main__":
    main()
