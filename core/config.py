import os
import json
import logging

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "config.json")

def load_config():
    """
    Loads the OpenClaw Clone configuration from data/config.json.
    Returns a dictionary of the configuration. Returns a default dictionary if not found.
    """
    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Configuration file not found at {CONFIG_PATH}. Creating default config.")
        return {
            "provider": "ollama",
            "model": "qwen2.5:3b",
            "ollama_url": "http://localhost:11434",
            "platforms": {
                "cli": {"enabled": True}
            },
            "webui": {"enabled": False, "port": 8501},
            "skills": {"install_defaults": True}
        }
    
    with open(CONFIG_PATH, "r") as f:
        try:
            config = json.load(f)
            return config
        except json.JSONDecodeError:
            logging.error(f"Failed to parse configuration file at {CONFIG_PATH}. Using defaults.")
            return {}

# Singleton instance
APP_CONFIG = load_config()

def get_config():
    return APP_CONFIG

def get_models():
    # Backwards compatibility check
    if "models" in APP_CONFIG:
        return APP_CONFIG["models"]
    
    # Legacy fallback format
    return [{
        "provider": APP_CONFIG.get("provider", "ollama"),
        "model": APP_CONFIG.get("model", "qwen2.5:3b"),
        "ollama_url": APP_CONFIG.get("ollama_url", "http://localhost:11434"),
        "api_key_env": APP_CONFIG.get("api_key_env", "OPENAI_API_KEY"),
        "role": "default"
    }]

def get_provider():
    return APP_CONFIG.get("provider", "ollama")

def get_model():
    return APP_CONFIG.get("model", "qwen2.5:3b")

def get_ollama_url():
    return APP_CONFIG.get("ollama_url", "http://localhost:11434")

def get_api_key_env():
    return APP_CONFIG.get("api_key_env", "OPENAI_API_KEY")

def is_platform_enabled(platform_name):
    platforms = APP_CONFIG.get("platforms", {})
    return platforms.get(platform_name, {}).get("enabled", False)

def get_platform_token(platform_name):
    platforms = APP_CONFIG.get("platforms", {})
    return platforms.get(platform_name, {}).get("token", None)

def is_webui_enabled():
    return APP_CONFIG.get("webui", {}).get("enabled", False)

def get_webui_port():
    return APP_CONFIG.get("webui", {}).get("port", 8501)
