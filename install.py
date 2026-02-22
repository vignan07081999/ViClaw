import os
import sys
import json
import requests
import time
import socket

# Auto-enforce virtual environment
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

from core.models import LLMRouter
from webui.app import start_webui
from core.agent import OpenClawAgent
from core.config import setup_logging

setup_logging()
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
import questionary
import sys

# Ensure we can import core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.scanner import quick_scan
from core.models import LLMRouter

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
    console.print("\n[bold yellow]2. Complete AI Model Setup[/bold yellow]")
    config["models"] = []
    
    # Auto-Install Ollama Path
    import subprocess
    has_ollama = subprocess.run(["command", "-v", "ollama"], shell=True, capture_output=True).returncode == 0
    
    opt_install_ollama = False
    if not has_ollama:
        console.print("[dim]Ollama engine is not installed on this system.[/dim]")
        if questionary.confirm("Would you like ViClaw to automatically download and install Ollama as your default AI engine now?", default=True).ask():
            opt_install_ollama = True
            console.print("[yellow]Deploying Ollama Native Runtime...[/yellow]")
            try:
                subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
                has_ollama = True
                console.print("[bold green]✓ Ollama natively installed.[/bold green]")
                time.sleep(2)  # Give daemon time to start
            except Exception as e:
                console.print(f"[bold red]Failed to deploy Ollama: {e}[/bold red]")
    
    adding_models = True
    while adding_models:
        provider_choices = ["Ollama (Local/Self-hosted)", "LiteLLM (API-based)"]
        if has_ollama:
            provider_choices.insert(0, "ViClaw Native (Local Ollama Turnkey)")
            
        provider_choice = questionary.select(
            "Which AI provider architecture do you want to configure?",
            choices=provider_choices
        ).ask()
        
        model_entry = {}
        if "Native" in provider_choice or "Ollama" in provider_choice:
            model_entry["provider"] = "ollama"
            
            if "Native" in provider_choice:
                model_entry["ollama_url"] = "http://localhost:11434"
                
                # Guided Model Selection
                preset_models = {
                    "General/Fast (qwen2.5:3b)": "qwen2.5:3b",
                    "Advanced Reasoning (llama3.2:3b)": "llama3.2:3b",
                    "Heavy Reasoning (llama3.1:8b)": "llama3.1:8b",
                    "Coding / DevOps (qwen2.5-coder)": "qwen2.5-coder",
                    "Custom Model Name": "custom"
                }
                
                selection = questionary.select(
                    "Select a curated local model payload to pull:",
                    choices=list(preset_models.keys())
                ).ask()
                
                if selection == "Custom Model Name":
                    model_name = questionary.text("Enter the exact Ollama registry tag (e.g. deepseek-r1:7b):").ask()
                else:
                    model_name = preset_models[selection]
                
                # Auto-Pull with progress bar
                console.print(f"\n[cyan]Downloading and initializing {model_name} (This may take several minutes)...[/cyan]")
                try:
                    # Using subprocess Popen to stream output to console if we want, or just wait
                    subprocess.run(["ollama", "pull", model_name], check=True)
                    console.print(f"[bold green]✓ {model_name} successfully provisioned into local registry![/bold green]")
                    
                    # Test connection locally just to verify daemon is answering
                    success, msg = test_ollama_connection(model_entry["ollama_url"], model_name)
                    if not success:
                        console.print(f"[bold red]Warning: {msg}[/bold red]")
                        
                except subprocess.CalledProcessError as e:
                    console.print(f"[bold red]Failed to pull {model_name}: {e}[/bold red]")
                    if not questionary.confirm("Do you want to proceed anyway?", default=False).ask():
                        continue
                        
                model_entry["model"] = model_name
                
            else: # Standard Remote Ollama config
                model_name = questionary.text("Enter the Ollama model name (e.g. qwen2.5:3b):", default="qwen2.5:3b").ask()
                model_entry["model"] = model_name
                ollama_url = questionary.text("Enter the external Ollama host URL:", default="http://192.168.1.100:11434").ask()
                model_entry["ollama_url"] = ollama_url
                
                console.print(f"[green]Testing connection to {ollama_url}...[/green]")
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
                    progress.add_task(description="Pinging remote Ollama server...", total=None)
                    success, msg = test_ollama_connection(ollama_url, model_name)
                    time.sleep(1)
                    
                if success:
                    console.print(f"[bold green]✓[/bold green] {msg}")
                else:
                    console.print(f"[bold red]✗ Connection Failed:[/bold red] {msg}")
                    if not questionary.confirm("Do you want to proceed and add it anyway?", default=False).ask():
                        continue

        else: # LiteLLM
            model_entry["provider"] = "litellm"
            model_name = questionary.text("Enter the LiteLLM model name (e.g. gpt-4o-mini)", default="gpt-4o-mini").ask()
            model_entry["model"] = model_name
            api_key_env = questionary.text("What environment variable holds this API key?", default="OPENAI_API_KEY").ask()
            model_entry["api_key_env"] = api_key_env
            
        # Ask what this model should be used for
        role = questionary.select(
            f"What capability role should '{model_entry['model']}' handle within the Agent framework?",
            choices=["Fast/Local (Simple Tasks & Routing)", "Capable/Complex (Heavy Reasoning)", "Coding (Software Dev & Scripting)", "Default/General Purpose"]
        ).ask()
        
        if "Fast" in role:
            model_entry["role"] = "fast"
        elif "Capable" in role:
            model_entry["role"] = "complex"
        elif "Coding" in role:
            model_entry["role"] = "coding"
        else:
            model_entry["role"] = "default"

        config["models"].append(model_entry)
        
        console.print("[dim]Note: ViClaw automatically parses your input and will autonomously route your prompts to the right model (e.g., using the Coding model for Python, or the Fast model for simple tasks) behind the scenes.[/dim]")
        adding_models = questionary.confirm("Would you like to provision another AI model for a different capability? (ViClaw automatically routes between them)", default=False).ask()

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
    
    webui_port = 8501
    if enable_webui:
        # Detect open port to prevent CasaOS / Proxmox collisions (which often hog 8501 or 8006)
        console.print("[dim]Scanning for an available port for the WebUI dashboard...[/dim]")
        for port in range(8501, 8550):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    webui_port = port
                    break
        console.print(f"[green]✓ Assigned WebUI to port {webui_port}[/green]")
        
    config["webui"] = {"enabled": enable_webui, "port": webui_port}
    
    # 5. Agent Skills
    console.print("\n[bold yellow]5. Skills & ClawHub[/bold yellow]")
    install_defaults = questionary.confirm("Install default community agent skills (Shell Engine, Reminders, SysInfo)?", default=True).ask()
    config["skills"] = {"install_defaults": install_defaults}

    # 6. AI Network Discovery
    console.print("\n[bold yellow]6. AI Local Network Discovery[/bold yellow]")
    if questionary.confirm("Would you like ViClaw to scan your local network for discoverable smart devices and servers (e.g., Home Assistant, Proxmox, 3D Printers)?", default=True).ask():
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            progress.add_task(description="Scanning local subnet for common service signatures...", total=None)
            discovered_devices = quick_scan()
            
        if not discovered_devices:
            console.print("[dim]No recognizable smart devices or servers found on this subnet.[/dim]")
        else:
            console.print(f"[bold green]Discovered {len(discovered_devices)} active hosts![/bold green]")
            
            # Temporarily save the config so the LLMRouter can load it
            os.makedirs("data", exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
                
            try:
                # Use the AI to generate a dynamic prompt
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
                    progress.add_task(description="Asking AI to analyze scan results...", total=None)
                    import core.config
                    core.config.APP_CONFIG.clear()
                    core.config.APP_CONFIG.update(config)
                    router = LLMRouter()
                    
                    sys_prompt = "You are an installation wizard assistant. You just finished scanning the user's local network."
                    prompt = f"The scanner found these devices running on specific IPs: {json.dumps(discovered_devices)}. Write a short, friendly message identifying the most interesting devices (like Home Assistant or Proxmox or Printers). End by asking the user if they want you to automatically install the ClawHub skills required to integrate with them."
                    
                    response = router.generate(prompt, system_prompt=sys_prompt)
                    ai_message = response.get("content", "").strip()
                    
                if ai_message:
                    console.print(Panel(ai_message, title="[bold magenta]ViClaw Discovery Engine[/bold magenta]", border_style="magenta"))
                    
                    want_integration = questionary.confirm("Integrate discovered devices?", default=True).ask()
                    if want_integration:
                        config["skills"]["auto_integrations"] = discovered_devices
                        console.print("[green]Awesome! I'll auto-configure the connection parameters for these endpoints on your first boot.[/green]")
                        
                        # Add SSH Setup & API Token Interception
                        config["ssh_hosts"] = {}
                        config["api_keys"] = {}
                        
                        console.print("\n[bold yellow]Authentication & Token Setup for Local Control[/bold yellow]")
                        for ip, info in discovered_devices.items():
                            svc_str = ", ".join(info["services"])
                            hostname = info.get("hostname", ip)
                            
                            # API Key Interception for HomeLab Software
                            if "Home Assistant" in info["services"]:
                                if questionary.confirm(f"Do you want to provide a Home Assistant Long-Lived API Token for {ip} '{hostname}'?", default=False).ask():
                                    token = questionary.password(f"HA Token for {ip}:").ask()
                                    config["api_keys"]["home_assistant"] = {"ip": ip, "token": token}
                                    console.print("[green]Saved Home Assistant API context![/green]")
                            
                            if "Proxmox VE" in info["services"]:
                                if questionary.confirm(f"Do you want to provide a Proxmox API Token ID/Secret for {ip} '{hostname}'?", default=False).ask():
                                    token_id = questionary.text(f"Token ID for {ip} (e.g. root@pam!viclaw):").ask()
                                    secret = questionary.password(f"Secret UUID for {ip}:").ask()
                                    config["api_keys"]["proxmox"] = {"ip": ip, "token_id": token_id, "secret": secret}
                                    console.print("[green]Saved Proxmox VE API context![/green]")
                                    
                            if any(svc in svc_str for svc in ["Radarr", "Sonarr", "Prowlarr", "Jellyfin"]):
                                console.print(f"[cyan]Detected media servers on {ip}! ViClaw can integrate via API.[/cyan]")
                                if "Radarr" in svc_str:
                                    config["api_keys"]["radarr"] = {"ip": ip, "token": questionary.password(f"Radarr API Key for {ip}:").ask()}
                                if "Sonarr" in svc_str:
                                    config["api_keys"]["sonarr"] = {"ip": ip, "token": questionary.password(f"Sonarr API Key for {ip}:").ask()}
                                if "Prowlarr" in svc_str:
                                    config["api_keys"]["prowlarr"] = {"ip": ip, "token": questionary.password(f"Prowlarr API Key for {ip}:").ask()}
                                if "Jellyfin" in svc_str:
                                    config["api_keys"]["jellyfin"] = {"ip": ip, "token": questionary.password(f"Jellyfin API Key for {ip}:").ask()}
                            
                            # Fallback to SSH for OS-level control
                            if questionary.confirm(f"Do you want to setup fallback OS-level SSH access for {ip} '{hostname}' ({svc_str})?", default=False).ask():
                                username = questionary.text(f"SSH Username for {ip}:", default="root").ask()
                                password = questionary.password(f"SSH Password (stored locally in config.json):").ask()
                                
                                console.print(f"[yellow]Testing SSH connection to {ip}...[/yellow]")
                                import paramiko
                                try:
                                    client = paramiko.SSHClient()
                                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                                    client.connect(hostname=ip, username=username, password=password, timeout=5)
                                    client.close()
                                    console.print("[bold green]✓ SSH connection successful![/bold green]")
                                    config["ssh_hosts"][ip] = {"username": username, "password": password}
                                except Exception as e:
                                    console.print(f"[bold red]✗ SSH connection failed: {e}[/bold red]")
                                    if questionary.confirm("Do you still want to save these SSH credentials?", default=False).ask():
                                        config["ssh_hosts"][ip] = {"username": username, "password": password}
            except Exception as e:
                console.print(f"[red]Error during AI analysis: {e}[/red]")
                
    # 7. Over-The-Air (OTA) Updates
    console.print("\n[bold yellow]7. Over-The-Air (OTA) Updates[/bold yellow]")
    console.print("ViClaw can automatically fetch and install updates from GitHub without wiping your setup.")
    config["updater"] = {}
    
    repo_url = questionary.text("What is the Git repository URL for this agent?", default="https://github.com/vignan07081999/ViClaw.git").ask()
    config["updater"]["repo_url"] = repo_url
    
    auto_update = questionary.confirm("Do you want ViClaw to automatically download and install updates in the background?", default=False).ask()
    config["updater"]["auto_update"] = auto_update
    
    if auto_update:
        freq = questionary.select("How often should the background daemon check for updates?", choices=["Every hour", "Daily", "Weekly"]).ask()
        config["updater"]["frequency"] = freq
    else:
        console.print("[dim]You will be notified in the WebUI and CLI when manual updates are available.[/dim]")

    console.print("\n[bold cyan]Configuration Summary[/bold cyan]")
    console.print(Panel(json.dumps(config, indent=2), border_style="cyan"))
    
    if questionary.confirm("Save and proceed?", default=True).ask():
        os.makedirs("data", exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        console.print(f"[bold green]✓ Configuration saved to {CONFIG_FILE}.[/bold green]")
        
        if os.path.exists("install.sh"):
            os.chmod("install.sh", 0o755)
            
        console.print(Panel.fit("[bold green]Setup complete![/bold green]\nThe background daemon will now process this configuration.", border_style="green"))
        
        if config.get("webui", {}).get("enabled"):
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
                progress.add_task(description="Waiting for WebUI daemon to initialize...", total=None)
                ready = False
                for _ in range(30):
                    try:
                        res = requests.get(f"http://127.0.0.1:{config['webui']['port']}/", timeout=1)
                        if res.status_code == 200:
                            ready = True
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                
            if ready:
                console.print("[bold green]✓ WebUI Dashboard is online and ready![/bold green]")
            else:
                console.print("[yellow]WebUI took too long to respond. It may still be starting up in the background.[/yellow]")
        
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
- [bold]./viclaw[/bold]             : Open the Super Master Menu (Chat, Diagnostics, Doctor)
- [bold]./viclaw chat[/bold]        : Drop right into the CLI conversation
- [bold]./viclaw diagnostics[/bold] : Run health checks
- [bold]./viclaw doctor[/bold]      : Analyze daemon logs and fix crashes automatically

[bold cyan]WebUI & 3D Dashboard:[/bold cyan]
Access your agent remotely from any browser on your network at:
[bold yellow]http://{local_ip}:{config['webui']['port']}/dashboard[/bold yellow]
"""
        console.print(Panel(cheat_sheet, title="ViClaw Cheat Sheet", border_style="cyan"))

    else:
        console.print("[red]Setup aborted.[/red]")

if __name__ == "__main__":
    main()
