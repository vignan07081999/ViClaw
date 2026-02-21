import os
import sys
import json
import sqlite3
import requests
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import print as rprint

# Ensure we're running from the root of OpenClawClone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import get_config

console = Console()

def clear():
    console.clear()

def check_ollama_status(url):
    try:
        res = requests.get(f"{url.rstrip('/')}/api/tags", timeout=5)
        if res.status_code == 200:
            return "[bold green]Online[/bold green]"
        return f"[bold red]Offline (Error Code {res.status_code})[/bold red]"
    except Exception as e:
        return f"[bold red]Unreachable[/bold red] ({e})"

def get_db_size():
    db_path = "data/memory.db"
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.2f} MB"
    return "Not initialized"

def check_service_status():
    try:
        result = subprocess.run(["systemctl", "is-active", "viclaw"], capture_output=True, text=True)
        status = result.stdout.strip()
        if status == "active":
            return "[bold green]Running (Active)[/bold green]"
        elif status == "inactive":
            return "[bold yellow]Stopped (Inactive)[/bold yellow]"
        else:
            return f"[dim]{status}[/dim]"
    except Exception:
        return "[dim]systemctl unavailable (Not installed as service)[/dim]"

def view_logs():
    try:
        console.print("[dim]Fetching last 50 lines of background logs... Press 'q' to exit if paginated.[/dim]\n")
        subprocess.run(["journalctl", "-u", "viclaw", "-n", "50", "--no-pager"])
    except Exception as e:
        console.print(f"[red]Error fetching logs: {e}[/red]")
    input("\nPress Enter to return...")

def run_script(script_name):
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", script_name)
    if not os.path.exists(script_path):
        console.print(f"[red]Error: {script_name} not found in scripts directory![/red]")
        input("\nPress Enter to return...")
        return
        
    try:
        subprocess.run(["bash", "-c", script_path], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]Script exited with error code {e.returncode}[/red]")
    input("\nPress Enter to return...")

def master_menu():
    while True:
        clear()
        config = get_config()
        
        # Build Status Table
        table = Table(title="ViClaw System Status Diagnostics", show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Status / Value", style="white")

        table.add_row("Daemon Service", check_service_status())
        table.add_row("Main Model", f"{config.get('model', 'Unknown')} ({config.get('provider', 'Unknown')})")
        
        if config.get('provider') == 'ollama':
            url = config.get('ollama_url', 'http://localhost:11434')
            table.add_row("Ollama API", check_ollama_status(url))
            
        table.add_row("Memory DB Footprint", get_db_size())
        
        console.print(table)
        
        console.print("\n[bold yellow]Diagnostics & Lifecycle Menu[/bold yellow]")
        console.print("[1] View Background Daemon Logs (journalctl)")
        console.print("[2] Update Configuration (Runs Wizard & Restarts)")
        console.print("[3] Reinstall Agent Dependencies")
        console.print("[4] Uninstall Agent (Destructive)")
        console.print("[5] Refresh Status")
        console.print("[0] Exit Menu")
        
        choice = Prompt.ask("\nChoose an option", choices=["0", "1", "2", "3", "4", "5"], default="5")
        
        if choice == "0":
            break
        elif choice == "1":
            view_logs()
        elif choice == "2":
            run_script("update_config.sh")
        elif choice == "3":
            run_script("reinstall.sh")
        elif choice == "4":
            run_script("uninstall.sh")
            # If they actually uninstalled, the loop should probably exit
            if not os.path.exists("data/config.json"):
                break
        elif choice == "5":
            continue

if __name__ == "__main__":
    master_menu()
