import os
import json
import requests
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

CONFIG_FILE = "data/config.json"
console = Console()

def test_ollama_connection(url, model):
    """Pings the Ollama API to ensure it's reachable and the model exists."""
    try:
        response = requests.get(f"{url.rstrip('/')}/api/tags", timeout=5)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            if any(model in m for m in models):
                return True, "Connection successful and model found."
            else:
                return True, f"Connection successful, but model '{model}' not found in list. It may need to be pulled."
        return False, f"Server returned status {response.status_code}"
    except Exception as e:
        return False, str(e)

def main():
    console.clear()
    console.print(Panel.fit("[bold cyan]Welcome to ViClaw (OpenClaw Clone) Setup Wizard[/bold cyan]", border_style="cyan"))
    config = {}

    # 1. Model Provider Configuration
    console.print("\n[bold yellow]1. Model Setup[/bold yellow]")
    provider_choice = Prompt.ask(
        "Which provider do you want to use for the main LLM?",
        choices=["1", "2"],
        default="1",
        show_choices=False
    )
    # choices map: 1 -> ollama, 2 -> litellm
    if provider_choice == "1":
        config["provider"] = "ollama"
        model = Prompt.ask("Enter the [cyan]Ollama model name[/cyan] to use", default="qwen2.5:3b")
        config["model"] = model
        
        ollama_url = Prompt.ask("Enter the [cyan]Ollama host URL[/cyan] (leave empty for local)", default="http://localhost:11434")
        config["ollama_url"] = ollama_url
        
        console.print(f"[green]Testing connection to {ollama_url}...[/green]")
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            progress.add_task(description="Pinging Ollama server...", total=None)
            success, msg = test_ollama_connection(ollama_url, model)
            time.sleep(1) # brief pause for visual effect

        if success:
            console.print(f"[bold green]✓[/bold green] {msg}")
        else:
            console.print(f"[bold red]✗ Connection Failed:[/bold red] {msg}")
            if not Confirm.ask("Do you want to proceed anyway?", default=False):
                console.print("[red]Setup aborted.[/red]")
                return

    else:
        config["provider"] = "litellm"
        model = Prompt.ask("Enter the [cyan]LiteLLM model name[/cyan] (e.g. gpt-4o)", default="gpt-4o-mini")
        config["model"] = model
        api_key_env = Prompt.ask("What environment variable holds this API key?", default="OPENAI_API_KEY")
        config["api_key_env"] = api_key_env

    # 2. Messaging Platforms Configuration
    console.print("\n[bold yellow]2. Messaging Platform Integrations[/bold yellow]")
    config["platforms"] = {}
    
    if Confirm.ask("Enable [bold]CLI / Terminal[/bold] interaction?", default=True):
        config["platforms"]["cli"] = {"enabled": True}

    if Confirm.ask("Enable [bold]Telegram[/bold] integration?", default=False):
        token = Prompt.ask("Enter Telegram Bot Token")
        config["platforms"]["telegram"] = {"enabled": True, "token": token}

    if Confirm.ask("Enable [bold]WhatsApp[/bold] integration?", default=False):
        token = Prompt.ask("Enter Meta App Token")
        config["platforms"]["whatsapp"] = {"enabled": True, "token": token}

    if Confirm.ask("Enable [bold]Discord[/bold] integration?", default=False):
        token = Prompt.ask("Enter Discord Bot Token")
        config["platforms"]["discord"] = {"enabled": True, "token": token}

    # 3. WebUI Configuration
    console.print("\n[bold yellow]3. WebUI Setup[/bold yellow]")
    enable_webui = Confirm.ask("Enable local [bold]WebUI[/bold] for monitoring memories and skills?", default=True)
    config["webui"] = {"enabled": enable_webui, "port": 8501}
    
    # 4. Agent Skills
    console.print("\n[bold yellow]4. Skills & ClawHub[/bold yellow]")
    install_defaults = Confirm.ask("Install default community agent skills (Calendar, Weather, System Info)?", default=True)
    config["skills"] = {"install_defaults": install_defaults}

    console.print("\n[bold cyan]Configuration Summary[/bold cyan]")
    console.print(Panel(json.dumps(config, indent=2), border_style="cyan"))
    
    if Confirm.ask("Save and proceed?", default=True):
        os.makedirs("data", exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        console.print(f"[bold green]✓ Configuration saved to {CONFIG_FILE}.[/bold green]")
        
        if os.path.exists("install.sh"):
            os.chmod("install.sh", 0o755)
            
        console.print(Panel.fit("[bold green]Setup complete![/bold green]\nThe systemd service has been configured. The agent will start in the background.", border_style="green"))
    else:
        console.print("[red]Setup aborted.[/red]")

if __name__ == "__main__":
    main()
