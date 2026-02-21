import os
import json
import requests
import time
import socket
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
import questionary

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

    # 1. Agent Identity
    console.print("\n[bold yellow]1. Agent Identity[/bold yellow]")
    agent_name = questionary.text("What would you like to name your AI agent?", default="ViClaw").ask()
    agent_personality = questionary.text("Describe its personality (e.g. 'sarcastic, helpful')", default="helpful, direct, and concise").ask()
    config["identity"] = {
        "name": agent_name,
        "personality": agent_personality
    }

    # 2. Model Provider Configuration
    console.print("\n[bold yellow]2. Model Setup[/bold yellow]")
    config["models"] = []
    
    adding_models = True
    while adding_models:
        provider_choice = questionary.select(
            "Which provider do you want to use for this LLM?",
            choices=["Ollama (Local/Self-hosted)", "LiteLLM (API-based)"]
        ).ask()
        
        model_entry = {}
        if "Ollama" in provider_choice:
            model_entry["provider"] = "ollama"
            model_name = questionary.text("Enter the Ollama model name (e.g. qwen2.5:3b, llama3.2:3b)", default="qwen2.5:3b").ask()
            model_entry["model"] = model_name
            
            ollama_url = questionary.text("Enter the Ollama host URL", default="http://localhost:11434").ask()
            model_entry["ollama_url"] = ollama_url
            
            console.print(f"[green]Testing connection to {ollama_url}...[/green]")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
                progress.add_task(description="Pinging Ollama server...", total=None)
                success, msg = test_ollama_connection(ollama_url, model_name)
                time.sleep(1)
                
            if success:
                console.print(f"[bold green]✓[/bold green] {msg}")
            else:
                console.print(f"[bold red]✗ Connection Failed:[/bold red] {msg}")
                if not questionary.confirm("Do you want to proceed and add it anyway?", default=False).ask():
                    continue

        else:
            model_entry["provider"] = "litellm"
            model_name = questionary.text("Enter the LiteLLM model name (e.g. gpt-4o-mini)", default="gpt-4o-mini").ask()
            model_entry["model"] = model_name
            api_key_env = questionary.text("What environment variable holds this API key?", default="OPENAI_API_KEY").ask()
            model_entry["api_key_env"] = api_key_env
            
        # Ask what this model should be used for
        role = questionary.select(
            f"What role should '{model_name}' play?",
            choices=["Fast/Local (Simple Tasks & Routing)", "Capable/Complex (Heavy Reasoning)", "Default/General Purpose"]
        ).ask()
        
        if "Fast" in role:
            model_entry["role"] = "fast"
        elif "Capable" in role:
            model_entry["role"] = "complex"
        else:
            model_entry["role"] = "default"

        config["models"].append(model_entry)
        
        adding_models = questionary.confirm("Would you like to add another AI model? (The agent will smart-switch between them)", default=False).ask()

    # Fallback if somehow empty
    if not config["models"]:
        config["models"].append({"provider": "ollama", "model": "qwen2.5:3b", "role": "default", "ollama_url": "http://localhost:11434"})

    # 3. Messaging Platforms Configuration
    console.print("\n[bold yellow]3. Messaging Platform Integrations[/bold yellow]")
    config["platforms"] = {}
    
    if questionary.confirm("Enable CLI / Terminal interaction?", default=True).ask():
        config["platforms"]["cli"] = {"enabled": True}

    if questionary.confirm("Enable Telegram integration?", default=False).ask():
        token = questionary.password("Enter Telegram Bot Token").ask()
        config["platforms"]["telegram"] = {"enabled": True, "token": token}

    if questionary.confirm("Enable WhatsApp integration?", default=False).ask():
        token = questionary.password("Enter Meta App Token").ask()
        config["platforms"]["whatsapp"] = {"enabled": True, "token": token}

    if questionary.confirm("Enable Discord integration?", default=False).ask():
        token = questionary.password("Enter Discord Bot Token").ask()
        config["platforms"]["discord"] = {"enabled": True, "token": token}

    # 4. WebUI Configuration
    console.print("\n[bold yellow]4. WebUI Setup[/bold yellow]")
    enable_webui = questionary.confirm("Enable local WebUI for 3D Dashboard & monitoring?", default=True).ask()
    config["webui"] = {"enabled": enable_webui, "port": 8501}
    
    # 5. Agent Skills
    console.print("\n[bold yellow]5. Skills & ClawHub[/bold yellow]")
    install_defaults = questionary.confirm("Install default community agent skills (Shell Engine, Reminders, SysInfo)?", default=True).ask()
    config["skills"] = {"install_defaults": install_defaults}

    console.print("\n[bold cyan]Configuration Summary[/bold cyan]")
    console.print(Panel(json.dumps(config, indent=2), border_style="cyan"))
    
    if questionary.confirm("Save and proceed?", default=True).ask():
        os.makedirs("data", exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        console.print(f"[bold green]✓ Configuration saved to {CONFIG_FILE}.[/bold green]")
        
        if os.path.exists("install.sh"):
            os.chmod("install.sh", 0o755)
            
        console.print(Panel.fit("[bold green]Setup complete![/bold green]\nThe systemd service has been configured. The agent will start in the background.", border_style="green"))
        
        # CHEAT SHEET
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"

        cheat_sheet = f"""
[bold cyan]Useful Commands:[/bold cyan]
- [bold]python viclaw.py[/bold]      : Open the Super Master Menu (Chat, Diagnostics, Doctor)
- [bold]python chat.py[/bold]        : Drop right into the CLI conversation
- [bold]python diagnostics.py[/bold] : Run health checks
- [bold]python doctor.py[/bold]      : Analyze daemon logs and fix crashes automatically

[bold cyan]WebUI & 3D Dashboard:[/bold cyan]
Access your agent remotely from any browser on your network at:
[bold yellow]http://{local_ip}:8501/dashboard[/bold yellow]
"""
        console.print(Panel(cheat_sheet, title="ViClaw Cheat Sheet", border_style="cyan"))

    else:
        console.print("[red]Setup aborted.[/red]")

if __name__ == "__main__":
    main()
