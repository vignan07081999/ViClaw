import subprocess
from rich.console import Console
from rich.markdown import Markdown

# Ensure we can import core components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.models import LLMRouter
from core.config import get_config

console = Console()

def run_doctor():
    console.clear()
    console.print("[bold cyan]ViClaw Automated Doctor[/bold cyan]")
    console.print("Scanning background daemon logs for recent errors...", style="dim")
    
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
