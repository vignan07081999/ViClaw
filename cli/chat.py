import os
import sys

# Auto-enforce virtual environment from subdirectory
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(root_dir, ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import time
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from core.config import get_webui_port

console = Console()

def main():
    port = get_webui_port()
    base_url = f"http://localhost:{port}"

    console.clear()
    console.print(Panel.fit("[bold magenta]ViClaw Interactive Local Client[/bold magenta]", border_style="magenta"))
    console.print("[dim]Connecting to background daemon...[/dim]")
    
    # Wait for daemon
    connected = False
    for _ in range(5):
        try:
            res = requests.get(f"{base_url}/api/memory")
            if res.status_code == 200:
                connected = True
                break
        except requests.exceptions.ConnectionError:
            time.sleep(1)

    if not connected:
        console.print("[bold red]Could not connect. Is the ViClaw daemon running?[/bold red]")
        console.print("Try running: [cyan]sudo systemctl start viclaw[/cyan]")
        return
        
    console.print("[green]Connected to ViClaw Background Service![/green]")
    console.print("Type your message below. Type [bold red]'exit'[/bold red] to quit.\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
            if user_input.lower().strip() == "exit":
                break
            
            if not user_input.strip():
                continue
                
            # Send to daemon via WebUI API
            with console.status("[bold cyan]ViClaw is thinking...[/bold cyan]", spinner="dots"):
                try:
                    res = requests.post(
                        f"{base_url}/api/chat",
                        json={"message": user_input}
                    )
                    if res.status_code == 200:
                        data = res.json()
                        reply = data.get("reply", "")
                        console.print(Panel(Markdown(reply), title="[bold magenta]ViClaw[/bold magenta]", title_align="left", border_style="magenta"))
                    else:
                        console.print(f"[red]Error from daemon: {res.status_code}[/red]")
                except Exception as e:
                    console.print(f"[red]Connection error: {e}[/red]")
                    
        except KeyboardInterrupt:
            console.print("\n[dim]Exiting chat...[/dim]")
            break
        except EOFError:
            break

if __name__ == "__main__":
    main()
