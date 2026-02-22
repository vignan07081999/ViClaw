import os
import sys
import json
import requests
import time
import socket
import subprocess

# Auto-enforce virtual environment
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

# Ensure we can import core modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import setup_logging
setup_logging()

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import questionary

CONFIG_FILE = "data/config.json"
console = Console()

def test_ollama_connection(url, model):
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

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def conf_identity(config):
    console.print("\n[bold yellow]--- 1. Agent Identity ---[/bold yellow]")
    current = config.get("identity", {})
    name = questionary.text("What would you like to name your AI agent?", default=current.get("name", "ViClaw")).ask()
    personality = questionary.text("Describe its personality:", default=current.get("personality", "helpful, direct, and concise")).ask()
    config["identity"] = {"name": name, "personality": personality}

def conf_models(config):
    console.print("\n[bold yellow]--- 2. Complete AI Model Setup ---[/bold yellow]")
    if "models" not in config:
        config["models"] = []
        
    # Auto-Install Ollama Path
    has_ollama = subprocess.run(["command", "-v", "ollama"], shell=True, capture_output=True).returncode == 0
    
    if has_ollama:
        try:
            requests.get("http://localhost:11434", timeout=2)
        except:
            console.print("[yellow]Ollama is installed but the service isn't running. Attempting to start 'ollama serve'...[/yellow]")
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            
    existing_models = []
    if has_ollama:
        try:
            res = requests.get("http://localhost:11434/api/tags", timeout=2)
            if res.status_code == 200:
                existing_models = [m["name"] for m in res.json().get("models", [])]
        except:
            pass
            
    if not has_ollama:
        console.print("[dim]Ollama engine is not installed on this system.[/dim]")
        if questionary.confirm("Would you like ViClaw to automatically download and install Ollama natively now?", default=True).ask():
            console.print("[yellow]Deploying Ollama Native Runtime...[/yellow]")
            try:
                subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
                has_ollama = True
                console.print("[bold green]✓ Ollama natively installed.[/bold green]")
                time.sleep(2)
            except Exception as e:
                console.print(f"[bold red]Failed to deploy Ollama: {e}[/bold red]")
                
    config["models"] = [] # Reset models on reconfiguration to avoid clutter
    adding_models = True
    while adding_models:
        provider_choices = ["External Ollama (Remote API)", "LiteLLM (OpenAI API/Anthropic)"]
        if has_ollama:
            provider_choices.insert(0, "Local AI Models (Requires Local Ollama)")
            
        provider_choice = questionary.select("Which AI provider architecture do you want to configure?", choices=provider_choices).ask()
        model_entry = {}
        
        if "Local AI Models" in provider_choice or "External Ollama" in provider_choice:
            model_entry["provider"] = "ollama"
            if "Local AI Models" in provider_choice:
                model_entry["ollama_url"] = "http://localhost:11434"
                
                ram_gb = 8.0
                try:
                    ram_gb = (os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')) / (1024.**3)
                except:
                    pass
                    
                preset_models = {}
                preset_models["General/Fast (qwen2.5:3b) - Recommended for any system"] = "qwen2.5:3b"
                if ram_gb < 7.0:
                    console.print(f"\n[bold yellow]Hardware Alert:[/bold yellow] Your system has {ram_gb:.1f}GB of total RAM. Running 8B parameter models may cause out-of-memory crashes.")
                    preset_models["Heavy Reasoning (llama3.1:8b) ⚠️ CAUTION: Requires 8GB+ RAM"] = "llama3.1:8b"
                else:
                    preset_models["Heavy Reasoning (llama3.1:8b) - Safe for your hardware"] = "llama3.1:8b"
                
                preset_models["Advanced Reasoning (llama3.2:3b) - Safe for your hardware"] = "llama3.2:3b"
                preset_models["Coding / DevOps (qwen2.5-coder) - Recommended for scripting"] = "qwen2.5-coder"
                
                choices = []
                if existing_models:
                    choices.append(questionary.Separator("--- Already Installed Models ---"))
                    choices.extend([f"Use Installed: {m}" for m in existing_models])
                    choices.append(questionary.Separator("--- Download New Models ---"))
                choices.extend(list(preset_models.keys()))
                choices.append("Custom Model Name")
                
                selection = questionary.select("Select an AI model to use for this role:", choices=choices).ask()
                
                if not selection or str(selection).startswith("---"):
                    selection = "Custom Model Name"
                
                if str(selection).startswith("Use Installed: "):
                    model_name = str(selection).replace("Use Installed: ", "")
                elif selection == "Custom Model Name":
                    model_name = questionary.text("Enter exact Ollama registry tag (e.g. deepseek-r1:7b):").ask()
                else:
                    model_name = preset_models[selection]
                
                if model_name not in existing_models:
                    console.print(f"\n[cyan]Downloading and initializing {model_name}...[/cyan]")
                    try:
                        subprocess.run(["ollama", "pull", model_name], check=True)
                        console.print(f"[bold green]✓ {model_name} successfully provisioned![/bold green]")
                        existing_models.append(model_name)
                    except subprocess.CalledProcessError as e:
                        console.print(f"[bold red]Failed to pull {model_name}: {e}[/bold red]")
                        if not questionary.confirm("Proceed anyway?", default=False).ask():
                            continue
                            
                success, msg = test_ollama_connection(model_entry["ollama_url"], model_name)
                if not success:
                    console.print(f"[bold red]Warning: {msg}[/bold red]")
                model_entry["model"] = model_name
                
            else:
                model_name = questionary.text("Enter Ollama model name (e.g. qwen2.5:3b):", default="qwen2.5:3b").ask()
                model_entry["model"] = model_name
                ollama_url = questionary.text("Enter external Ollama host URL:", default="http://192.168.1.100:11434").ask()
                model_entry["ollama_url"] = ollama_url
                
                console.print(f"[green]Testing connection...[/green]")
                success, msg = test_ollama_connection(ollama_url, model_name)
                if success:
                    console.print(f"[bold green]✓[/bold green] {msg}")
                else:
                    console.print(f"[bold red]✗ Connection Failed:[/bold red] {msg}")
                    if not questionary.confirm("Proceed anyway?", default=False).ask():
                        continue
        else:
            model_entry["provider"] = "litellm"
            model_entry["model"] = questionary.text("LiteLLM model name (e.g. gpt-4o-mini):").ask()
            model_entry["api_key_env"] = questionary.text("Environment variable holding API key:", default="OPENAI_API_KEY").ask()
            
        role = questionary.select(
            f"What role should '{model_entry['model']}' handle?",
            choices=["Fast/Local (Simple Tasks & Routing)", "Capable/Complex (Heavy Reasoning)", "Coding (Software Dev & Scripting)", "Default/General Purpose"]
        ).ask()
        
        if "Fast" in role: model_entry["role"] = "fast"
        elif "Capable" in role: model_entry["role"] = "complex"
        elif "Coding" in role: model_entry["role"] = "coding"
        else: model_entry["role"] = "default"

        config["models"].append(model_entry)
        adding_models = questionary.confirm("Add another AI model? (ViClaw routes between them)", default=False).ask()

def conf_platforms(config):
    console.print("\n[bold yellow]--- 3. Messaging Integration Setup ---[/bold yellow]")
    if "platforms" not in config: config["platforms"] = {}
    
    config["platforms"]["cli"] = {"enabled": questionary.confirm("Enable CLI Terminal interaction?", default=True).ask()}
    
    if questionary.confirm("Enable Telegram?", default=False).ask():
        config["platforms"]["telegram"] = {"enabled": True, "token": questionary.password("Telegram Bot Token:").ask()}
    else:
        config["platforms"].pop("telegram", None)
        
    if questionary.confirm("Enable WhatsApp?", default=False).ask():
        config["platforms"]["whatsapp"] = {"enabled": True, "token": questionary.password("Meta App Token:").ask()}
    else:
        config["platforms"].pop("whatsapp", None)
        
    if questionary.confirm("Enable Discord?", default=False).ask():
        config["platforms"]["discord"] = {"enabled": True, "token": questionary.password("Discord Bot Token:").ask()}
    else:
         config["platforms"].pop("discord", None)

def conf_webui(config):
    console.print("\n[bold yellow]--- 4. WebUI & Kiosk Dashboard ---[/bold yellow]")

    enable_webui = questionary.confirm("Enable local WebUI for 3D Dashboard & monitoring?", default=True).ask()
    webui_port = config.get("webui", {}).get("port", 8501)

    if enable_webui:
        console.print("[dim]Scanning for an available port to prevent collisions...[/dim]")
        for port in range(8501, 8550):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    webui_port = port
                    break
        console.print(f"[green]✓ Assigned WebUI to port {webui_port}[/green]")

        # ---- WebUI credential setup ------------------------------------------
        console.print("\n[bold red]⚠ Security:[/bold red] Set a username and password for WebUI access.")
        console.print("[dim]These replace the old hardcoded defaults. Store them safely.[/dim]")
        existing_creds = config.get("webui", {}).get("credentials", {})
        webui_user = questionary.text(
            "WebUI Admin Username:",
            default=existing_creds.get("username", "admin")
        ).ask()
        # Password with confirmation loop
        while True:
            webui_pass = questionary.password("WebUI Password (min 6 chars):").ask()
            if not webui_pass or len(webui_pass) < 6:
                console.print("[red]Password must be at least 6 characters. Try again.[/red]")
                continue
            webui_pass_confirm = questionary.password("Confirm password:").ask()
            if webui_pass == webui_pass_confirm:
                break
            console.print("[red]Passwords do not match. Try again.[/red]")
        # ---------------------------------------------------------------------

        config["webui"] = {
            "enabled": True,
            "port": webui_port,
            "credentials": {"username": webui_user, "password": webui_pass},
        }
        console.print(f"[green]✓ WebUI credentials saved for user '{webui_user}'.[/green]")
    else:
        config["webui"] = {"enabled": False, "port": webui_port}

    console.print("\n[bold yellow]Stream Deck Kiosk Desktop[/bold yellow]")
    console.print("[dim]Glassmorphic dashboard with HomeAssistant iframes and an animated 3D Deskbot.[/dim]")
    config["kiosk"] = {"enabled": questionary.confirm("Enable Kiosk Interface?", default=True).ask()}

def conf_skills(config):
    console.print("\n[bold yellow]--- 5. Skills & Network Discovery ---[/bold yellow]")
    if "skills" not in config: config["skills"] = {}
    config["skills"]["install_defaults"] = questionary.confirm("Install default community agent skills (SysInfo, Reminders)?", default=True).ask()
    
    console.print("\n[bold yellow]AI Local Network Discovery[/bold yellow]")
    if questionary.confirm("Scan local network for smart devices (e.g. Home Assistant, Proxmox)?", default=True).ask():
        from core.scanner import quick_scan
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            progress.add_task(description="Scanning local subnet...", total=None)
            discovered_devices = quick_scan()
            
        if not discovered_devices:
            console.print("[dim]No recognizable smart devices or servers found.[/dim]")
        else:
            console.print(f"[bold green]Discovered {len(discovered_devices)} active hosts![/bold green]")
            if questionary.confirm("Integrate discovered devices?", default=True).ask():
                config["skills"]["auto_integrations"] = discovered_devices
                if "api_keys" not in config: config["api_keys"] = {}
                if "ssh_hosts" not in config: config["ssh_hosts"] = {}
                
                for ip, info in discovered_devices.items():
                    svc_str = ", ".join(info["services"])
                    hostname = info.get("hostname", ip)
                    if "Home Assistant" in info["services"] and questionary.confirm(f"Provide Home Assistant API Token for {ip} '{hostname}'?", default=False).ask():
                        config["api_keys"]["home_assistant"] = {"ip": ip, "token": questionary.password("HA Token:").ask()}
                    if "Proxmox VE" in info["services"] and questionary.confirm(f"Provide Proxmox API Token for {ip} '{hostname}'?", default=False).ask():
                        config["api_keys"]["proxmox"] = {
                            "ip": ip, 
                            "token_id": questionary.text("Token ID (root@pam!viclaw):").ask(), 
                            "secret": questionary.password("Secret UUID:").ask()
                        }
                    if questionary.confirm(f"Setup SSH access for {ip} ({svc_str})?", default=False).ask():
                        config["ssh_hosts"][ip] = {
                            "username": questionary.text(f"SSH Username for {ip}:", default="root").ask(),
                            "password": questionary.password("SSH Password:").ask()
                        }

def conf_advanced(config):
    console.print("\n[bold yellow]--- 6. Advanced AGI Modules ---[/bold yellow]")
    if "updater" not in config: config["updater"] = {}
    config["updater"]["repo_url"] = questionary.text("Git repository URL:", default=config.get("updater", {}).get("repo_url", "https://github.com/vignan07081999/ViClaw.git")).ask()
    auto_update = questionary.confirm("Enable background OTA Auto-Updates?", default=config.get("updater", {}).get("auto_update", False)).ask()
    config["updater"]["auto_update"] = auto_update
    if auto_update:
        config["updater"]["frequency"] = questionary.select("Frequency:", choices=["Every hour", "Daily", "Weekly"]).ask()

    console.print("\n[bold yellow]Hardware-Intensive Feature Gates[/bold yellow]")
    
    if "advanced_modules" not in config: config["advanced_modules"] = {}
    ram_gb = 8.0
    try: ram_gb = (os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')) / (1024.**3)
    except: pass
    
    console.print(f"[cyan]Detected System RAM:[/cyan] [bold]{ram_gb:.1f} GB[/bold]")
    
    # Vision Module
    if ram_gb < 7.0:
        console.print("[bold yellow]Hardware Alert:[/bold yellow] Your system has <8GB RAM. Loading multimodal vision models causes heavy VRAM usage.")
        config["advanced_modules"]["vision"] = questionary.confirm("Enable Vision capabilities anyway?", default=config.get("advanced_modules", {}).get("vision", False)).ask()
    else:
        config["advanced_modules"]["vision"] = questionary.confirm("Enable Vision/Image Attachment capabilities?", default=True).ask()
        
    # Swarm Orchestrator
    if ram_gb < 7.0:
        console.print("[bold yellow]Hardware Alert:[/bold yellow] Spawning parallel Swarm Sub-Agents bloats the context window natively.")
        config["advanced_modules"]["swarm"] = questionary.confirm("Enable Multi-Agent Swarm Orchestrator anyway?", default=config.get("advanced_modules", {}).get("swarm", False)).ask()
    else:
        config["advanced_modules"]["swarm"] = questionary.confirm("Enable Multi-Agent Swarm Orchestrator?", default=True).ask()
        
    console.print("\n[dim]--- Roadmap Pre-configurations ---[/dim]")
    if ram_gb < 15.0:
        console.print("[bold yellow]Hardware Alert:[/bold yellow] <16GB RAM. Local Edge Audio (Whisper/Speech) requires massive multithreading.")
        config["advanced_modules"]["local_edge_audio"] = questionary.confirm("Pre-configure for Local Edge Audio anyway?", default=False).ask()
    else:
        config["advanced_modules"]["local_edge_audio"] = questionary.confirm("Pre-configure for Local Edge Audio?", default=True).ask()

    if ram_gb < 7.0:
        console.print("[bold yellow]Hardware Alert:[/bold yellow] Playwright headless tabs draw 500MB-1GB of RAM each.")
        config["advanced_modules"]["playwright_agents"] = questionary.confirm("Pre-configure Playwright Computer-Use agents anyway?", default=False).ask()
    else:
         config["advanced_modules"]["playwright_agents"] = questionary.confirm("Pre-configure Playwright Computer-Use agents?", default=True).ask()

def print_summary(config):
    summary_text = f"⚙️  [bold yellow]Agent Identity:[/bold yellow]\n"
    summary_text += f" - Name: {config.get('identity', {}).get('name', 'Unset')}\n"
    summary_text += f" - Personality: {config.get('identity', {}).get('personality', 'Unset')}\n\n"
    
    summary_text += f"🧠 [bold yellow]AI Resource Allocation:[/bold yellow]\n"
    if "models" in config and config["models"]:
        for m in config.get("models", []):
            summary_text += f" - Provider: [{m.get('provider').upper()}] | Model: {m.get('model')} | Role: {m.get('role')}\n"
    else:
        summary_text += f" - [red]No models configured![/red]\n"
        
    summary_text += f"\n📡 [bold yellow]Platform I/O:[/bold yellow]\n"
    summary_text += f" - CLI Terminal: {'Running' if config.get('platforms', {}).get('cli', {}).get('enabled', False) else 'Disabled'}\n"
    summary_text += f" - Telegram: {'Online' if config.get('platforms', {}).get('telegram', {}).get('enabled', False) else 'Disabled'}\n"
    
    summary_text += f"\n🌐 [bold yellow]WebUI & Desktop Kiosk:[/bold yellow]\n"
    summary_text += f" - Port: {config.get('webui', {}).get('port', 'Unset')} ({'Enabled' if config.get('webui', {}).get('enabled', False) else 'Disabled'})\n"
    
    summary_text += f"\n⚙️  [bold yellow]Advanced Toggles:[/bold yellow]\n"
    summary_text += f" - Vision API: {'Enabled' if config.get('advanced_modules', {}).get('vision', False) else 'Opt-Out'}\n"
    summary_text += f" - Multi-Agent Swarm: {'Enabled' if config.get('advanced_modules', {}).get('swarm', False) else 'Opt-Out'}\n"
    
    console.print(Panel(summary_text, title="[bold cyan]Current Blueprint[/bold cyan]", border_style="cyan"))

def run_installation_core(config):
    save_config(config)
    console.print(f"[bold green]✓ Configuration saved recursively![/bold green]")
    
    if os.path.exists("install.sh"):
        os.chmod("install.sh", 0o755)
        
    console.print(Panel.fit("[bold green]Setup finalized![/bold green]\nStarting background daemon to digest the structural mapping...", border_style="green"))
    
    try:
        subprocess.Popen([sys.executable, "launcher.py", "restart"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
    except Exception as e:
        console.print(f"[red]Failed to auto-start daemon: {e}[/red]")
        
    if config.get("webui", {}).get("enabled"):
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            progress.add_task(description="Waiting for WebUI daemon mapping on 0.0.0.0...", total=None)
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
            console.print("[bold green]✓ WebUI Dashboard is online and binding to IP arrays![/bold green]")
        else:
            console.print("[yellow]WebUI took too long to respond. The system daemon may be compiling models.[/yellow]")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"

    cheat_sheet = f"""
[bold cyan]Useful Commands:[/bold cyan]
- [bold]viclaw[/bold]             : Open the Super Master Menu (Interactive Hub)
- [bold]viclaw chat[/bold]        : Drop right into the CLI conversation
- [bold]viclaw diagnostics[/bold] : Run health checks & system debuggers
- [bold]viclaw restart[/bold]     : Reboots the underlying systemd background service

[bold cyan]WebUI & 3D Dashboard:[/bold cyan]
Access your agent remotely from any browser natively attached to this Subnet:
[bold yellow]http://{local_ip}:{config.get('webui', {}).get('port', 8501)}/dashboard[/bold yellow]
"""
    console.print(Panel(cheat_sheet, title="ViClaw System Array Activated", border_style="cyan"))

def main():
    console.clear()
    console.print(Panel.fit("[bold cyan]ViClaw Autonomous Engine Setup[/bold cyan]\n[dim]Interactive Configuration UI[/dim]", border_style="cyan"))
    config = load_config()
    
    # If starting fresh, force them to set up at least identity & models
    if "identity" not in config:
        conf_identity(config)
    if "models" not in config:
        conf_models(config)
        conf_platforms(config)
        conf_webui(config)
        
    while True:
        console.clear()
        print_summary(config)
        
        choice = questionary.select(
            "ViClaw Configuration Hub - Select a module to configure:",
            choices=[
                "1. Agent Identity",
                "2. AI Models & Providers",
                "3. Messaging Integrations (CLI/Telegram)",
                "4. WebUI & Port Mapping",
                "5. Skill Injection & Subnet Discovery",
                "6. Advanced (Hardware Limiters & OTA Swarms)",
                "---",
                "Review & Finalize Deployment",
                "Exit without saving"
            ]
        ).ask()
        
        if not choice:
            break
        elif "Agent Identity" in choice:
            conf_identity(config)
        elif "AI Models" in choice:
            conf_models(config)
        elif "Messaging Integrations" in choice:
            conf_platforms(config)
        elif "WebUI" in choice:
            conf_webui(config)
        elif "Skill Injection" in choice:
            conf_skills(config)
        elif "Advanced" in choice:
            conf_advanced(config)
        elif "Review & Finalize" in choice:
            run_installation_core(config)
            break
        elif "Exit" in choice:
            console.print("[dim]Aborted.[/dim]")
            sys.exit(0)

if __name__ == "__main__":
    main()
