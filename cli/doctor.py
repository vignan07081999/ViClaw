import subprocess
import sys
import os
from rich.console import Console
import subprocess
import sys
import os
import requests
import pkg_resources
from rich.console import Console
from rich.markdown import Markdown

# Auto-enforce virtual environment from subdirectory
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(root_dir, ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

sys.path.insert(0, root_dir)
from core.models import LLMRouter
from core.config import get_config

console = Console()


def run_doctor():
    console.clear()
    console.print("[bold cyan]ViClaw Automated Doctor[/bold cyan]\n")
    
    # --- Auto-Fix Directory Structure ---
    console.print("[yellow]Verifying directory structure...[/yellow]")
    dirs_to_check = ["data", "data/dropzone", "data/tts", "data/screenshots"]
    fixed_dirs = 0
    for d in dirs_to_check:
        dpath = os.path.join(root_dir, d)
        if not os.path.exists(dpath):
            os.makedirs(dpath, exist_ok=True)
            fixed_dirs += 1
    if fixed_dirs > 0:
        console.print(f"[green]✓ Auto-created {fixed_dirs} missing directories.[/green]")
    else:
        console.print("[green]✓ Directory structure intact.[/green]")
        
    # --- Check ClawHub Status ---
    console.print("\n[yellow]Checking ClawHub Registry online status...[/yellow]")
    try:
        from core.config import get_config
        hub_url = get_config().get("skills", {}).get("clawhub_url", "https://clawhub.viclaw.ai")
        # Just ping a known public endpoint or the base repo domain
        # Since ClawHub is a hypothetical github repo or api, we just do a simple timeout HEAD
        # If it's github raw we ping github.com
        if "github" in hub_url:
            res = requests.head("https://github.com", timeout=3)
        else:
            res = requests.head(hub_url, timeout=3)
            
        if res.status_code < 500:
            console.print("[green]✓ ClawHub is reachable.[/green]")
        else:
            console.print(f"[red]✗ ClawHub returned status {res.status_code}. Skill downloads may fail.[/red]")
    except Exception as e:
        console.print(f"[red]✗ ClawHub unreachable: {e}[/red]")

    # --- Proceed to log checking ---
    console.print("\nScan daemon logs for recent errors?", style="dim")
    ans = input("Press Enter to scan or 'q' to quit: ")
    if ans.lower().strip() == 'q': return
    
    console.print("\nScanning background daemon logs for recent errors...", style="dim")
    
    try:
        # Pull the last 300 lines of the daemon
        res = subprocess.run(
            ["journalctl", "-u", "viclaw", "-n", "300", "--no-pager"], 
            capture_output=True, text=True
        )
        logs = res.stdout
        
        # Filter for clear error indicators
        error_lines = []
        for line in logs.split('\n'):
            line_lower = line.lower()
            if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower or "failed" in line_lower:
                error_lines.append(line)
        
        if not error_lines:
            console.print("[green]No obvious errors found in the recent daemon logs! The agent looks healthy.[/green]")
            input("\nPress Enter to return...")
            return

        console.print(f"[yellow]Found {len(error_lines)} potential error events. Analyzing with local LLM...[/yellow]\n")
        
        # Take the last 20 errors to avoid blowing up the context window for small models
        error_context = "\n".join(error_lines[-20:]) 

        sys_prompt = (
            "You are the ViClaw Automated Doctor. Review these recent error logs from the agent's daemon process. "
            "Identify the root cause of the crash or failure, and provide clear, step-by-step instructions on how the user can fix the issue. "
            "Suggest bash commands if they need to change file permissions, install a missing dependency, or restart a service. "
            "Format your output in clean Markdown."
        )
        
        with console.status("[bold cyan]Doctor is diagnosing the issue...[/bold cyan]", spinner="dots"):
            router = LLMRouter()
            response = router.generate(
                f"Please analyze these errors:\n\n{error_context}", 
                system_prompt=sys_prompt, 
                context=[]
            )
        
        if response["content"]:
            console.print(Markdown(response["content"]))
        else:
            console.print("[red]The LLM didn't return an analysis. Check if the model is online via Diagnostics.[/red]")

    except Exception as e:
        console.print(f"[red]Doctor encountered a fatal error reading logs: {e}[/red]")
        
    input("\nPress Enter to return...")

if __name__ == "__main__":
    run_doctor()
