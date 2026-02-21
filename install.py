import os
import json
import sys
import shutil

CONFIG_FILE = "data/config.json"

def print_header(text):
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}\n")

def prompt_choice(question, options):
    print(question)
    for i, opt in enumerate(options, 1):
        print(f"[{i}] {opt['label']}")
    while True:
        try:
            choice = int(input("> "))
            if 1 <= choice <= len(options):
                return options[choice - 1]['value']
        except ValueError:
            pass
        print("Invalid choice, please try again.")

def prompt_yes_no(question, default="y"):
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    prompt = f"{question} [Y/n]" if default == "y" else f"{question} [y/N]"
    while True:
        sys.stdout.write(prompt + " ")
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")

def prompt_string(question, default=""):
    prompt = f"{question} [{default}]: " if default else f"{question}: "
    val = input(prompt).strip()
    return val if val else default

def main():
    print_header("Welcome to OpenClaw Configuration Wizard")
    config = {}

    # 1. Model Provider Configuration
    print_header("1. Model Setup")
    provider = prompt_choice("Which provider do you want to use for the main LLM?", [
        {"label": "Ollama (Local - Recommended for qwen2.5:3b)", "value": "ollama"},
        {"label": "LiteLLM (API for OpenAI, Anthropic, etc.)", "value": "litellm"}
    ])
    config["provider"] = provider
    
    if provider == "ollama":
        model = prompt_string("Enter the Ollama model name to use", default="qwen2.5:3b")
        config["model"] = model
        
        ollama_url = prompt_string("Enter the Ollama host URL (leave empty for local)", default="http://localhost:11434")
        config["ollama_url"] = ollama_url
        
        print(f"-> We will use '{model}' via Ollama at {ollama_url}.")
    else:
        model = prompt_string("Enter the LiteLLM model name (e.g. gpt-4o, claude-3-5-sonnet)", default="gpt-4o-mini")
        config["model"] = model
        api_key_env = prompt_string("What environment variable holds this API key?", default="OPENAI_API_KEY")
        config["api_key_env"] = api_key_env

    # 2. Messaging Platforms Configuration
    print_header("2. Messaging Platform Integrations")
    config["platforms"] = {}
    
    if prompt_yes_no("Enable CLI / Terminal interaction?", default="y"):
        config["platforms"]["cli"] = {"enabled": True}

    if prompt_yes_no("Enable Telegram integration?", default="n"):
        token = prompt_string("Enter Telegram Bot Token")
        config["platforms"]["telegram"] = {"enabled": True, "token": token}

    if prompt_yes_no("Enable WhatsApp integration?", default="n"):
        token = prompt_string("Enter Meta App Token")
        config["platforms"]["whatsapp"] = {"enabled": True, "token": token}

    if prompt_yes_no("Enable Discord integration?", default="n"):
        token = prompt_string("Enter Discord Bot Token")
        config["platforms"]["discord"] = {"enabled": True, "token": token}

    # 3. WebUI Configuration
    print_header("3. WebUI Setup")
    enable_webui = prompt_yes_no("Enable local WebUI for monitoring memories and skills?", default="y")
    config["webui"] = {"enabled": enable_webui, "port": 8501}
    
    # 4. Agent Skills
    print_header("4. Skills & ClawHub")
    install_defaults = prompt_yes_no("Install default community agent skills (Calendar, Weather, System Info)?", default="y")
    config["skills"] = {"install_defaults": install_defaults}

    print_header("Configuration Summary")
    print(json.dumps(config, indent=2))
    
    if prompt_yes_no("Save and proceed?", default="y"):
        os.makedirs("data", exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {CONFIG_FILE}.")
        
        # Make install.sh executable if we're on linux/mac
        if os.path.exists("install.sh"):
            os.chmod("install.sh", 0o755)
            
        print("Setup complete. You can now start the agent by running 'python main.py'.")
    else:
        print("Setup aborted.")

if __name__ == "__main__":
    main()
