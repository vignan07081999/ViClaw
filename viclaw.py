import os
import sys

# Auto-enforce virtual environment
root_dir = os.path.dirname(os.path.abspath(__file__))
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(root_dir, ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

sys.path.insert(0, root_dir)

import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def main():
    while True:
        console.clear()
        console.print(Panel.fit("[bold magenta]ViClaw Super Menu[/bold magenta]", border_style="magenta"))
        console.print("[1] 💬 Interactive CLI Chat")
        console.print("[2] 🚀 Start/Restart Background Daemon (Enables WebUI)")
        console.print("[3] 🛑 Stop Background Daemon")
        console.print("[4] 📊 System Diagnostics & Health")
        console.print("[5] 🩺 Agent Doctor (Troubleshoot & Fix)")
        console.print("[6] ⚙️  Update Configuration")
        console.print("[7] 📜 View Chat History & Action Logs")
        console.print("[8] 🔄 Reinstall ViClaw")
        console.print("[9] 🗑️  Uninstall ViClaw")
        console.print("[10] ☁️ Check for Github OTA Updates")
        console.print("[11] 📖 ViClaw Wiki & Manual")
        console.print("[0] 🚪 Exit")
        
        choice = Prompt.ask("\nSelect an option", choices=[str(i) for i in range(12)], default="1")
        
        if choice == "0":
            break
        elif choice == "1":
            subprocess.run([sys.executable, os.path.join(root_dir, "cli/chat.py")])
        elif choice == "2":
            subprocess.run([sys.executable, os.path.join(root_dir, "launcher.py"), "restart"])
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "3":
            subprocess.run([sys.executable, os.path.join(root_dir, "launcher.py"), "stop"])
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "4":
            subprocess.run([sys.executable, os.path.join(root_dir, "cli/diagnostics.py")])
        elif choice == "5":
            subprocess.run([sys.executable, os.path.join(root_dir, "cli/doctor.py")])
        elif choice == "6":
            subprocess.run(["bash", os.path.join(root_dir, "scripts/update_config.sh")])
        elif choice == "7":
            console.print("\n[bold cyan]--- Recent Agent Memory & Action Logs ---[/bold cyan]")
            try:
                from core.config import get_webui_port
                port = get_webui_port()
                import requests as req
                res = req.get(f"http://localhost:{port}/api/history", timeout=3)
                if res.status_code == 200:
                    history = res.json().get("history", [])
                    if not history:
                        console.print("[dim]No chat history yet. Start a conversation first.[/dim]")
                    else:
                        for entry in history:
                            role = entry.get("role", "unknown").upper()
                            content = entry.get("content", "")
                            if role == "USER":
                                console.print(f"[bold blue]USER:[/bold blue] {content}")
                            elif role == "ASSISTANT":
                                console.print(f"[bold magenta]VICLAW:[/bold magenta] {content}")
                            elif role == "SYSTEM":
                                console.print(f"[dim yellow]SYSTEM/TOOL:[/dim yellow] {content}")
                else:
                    console.print(f"[red]Daemon returned HTTP {res.status_code}.[/red]")
            except Exception as e:
                console.print(f"[red]Could not reach daemon: {e}[/red]")
                console.print("[dim]Is the background daemon running? Try option 2 to start it.[/dim]")
            Prompt.ask("\nPress Enter to return to menu...")
        elif choice == "8":
            subprocess.run(["bash", os.path.join(root_dir, "scripts/reinstall.sh")])
        elif choice == "9":
            subprocess.run(["bash", os.path.join(root_dir, "scripts/uninstall.sh")])
            if not os.path.exists(os.path.join(root_dir, "data/config.json")):
                break
        elif choice == "10":
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from core.updater import UpdaterEngine
            console.print("\n[yellow]Checking Github for new ViClaw patches...[/yellow]")
            try:
                updater = UpdaterEngine()
                has_update, loc_hash, rem_hash, msg = updater.check_for_updates()
                if has_update:
                    console.print(Panel(f"[bold cyan]Update Available![/bold cyan]\nLocal: {loc_hash}\nRemote: {rem_hash}\n\n[dim]Newest Patch:[/dim] {msg}", border_style="cyan"))
                    if Prompt.ask("Do you want to pull and install this update now?", choices=["y", "n"], default="y") == "y":
                        success, log = updater.trigger_pull()
                        if success:
                            console.print(f"[bold green]✓ {log}[/bold green]")
                            console.print("Please restart the background daemon to apply code changes.")
                        else:
                            console.print(f"[bold red]✗ {log}[/bold red]")
                else:
                    console.print(f"[bold green]✓ You are running the latest version.[/bold green] ({loc_hash})\n[dim]{msg}[/dim]")
            except Exception as e:
                console.print(f"[red]Updater error: {e}[/red]")
            Prompt.ask("\nPress Enter to return to menu...")
        elif choice == "11":
            subprocess.run([sys.executable, os.path.join(root_dir, "cli/wiki.py")])
            Prompt.ask("\nPress Enter to return to menu...")

if __name__ == "__main__":
    main()
