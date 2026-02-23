"""
core/config.py — ViClaw Configuration Manager

Improvements in this version:
  - ConfigManager class with live reload() instead of a bare module-level singleton
  - APP_CONFIG is kept for backward compatibility (points to the manager's dict)
  - Accessor functions delegate to the manager so they always see current values
  - setup_logging() is idempotent (checks handler count before adding)
"""

import os
import json
import logging
import threading
from logging.handlers import RotatingFileHandler

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "config.json")

_DEFAULT_CONFIG = {
    "provider": "ollama",
    "model": "qwen2.5:3b",
    "ollama_url": "http://localhost:11434",
    "platforms": {"cli": {"enabled": True}},
    "webui": {"enabled": False, "port": 8501},
    "skills": {"install_defaults": True},
}


def setup_logging():
    """Configure rotating file + console logging. Safe to call multiple times."""
    os.makedirs("data", exist_ok=True)
    logger = logging.getLogger()
    if logger.handlers:
        return  # Already configured — don't add duplicate handlers
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = RotatingFileHandler("data/viclaw.log", maxBytes=5 * 1024 * 1024, backupCount=2)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


class ConfigManager:
    """
    Thread-safe configuration manager that supports live reload.

    Usage:
        config_mgr = ConfigManager()
        value = config_mgr.get("webui", {}).get("port", 8501)
        config_mgr.reload()   # Re-reads config.json from disk without restarting
    """

    def __init__(self, path: str = CONFIG_PATH):
        self._path = path
        self._lock = threading.RLock()
        self._data: dict = {}
        self.reload()

    # ------------------------------------------------------------------
    # Core load / reload
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-read config.json from disk. Thread-safe."""
        with self._lock:
            if not os.path.exists(self._path):
                logging.warning(f"Config not found at {self._path}. Using defaults.")
                self._data = dict(_DEFAULT_CONFIG)
                return
            try:
                with open(self._path, "r") as f:
                    self._data = json.load(f)
                logging.info("Config reloaded from disk.")
            except json.JSONDecodeError:
                logging.error(f"Failed to parse {self._path}. Keeping previous config.")
            
            # Auto-generate local_api_key - REMOVED for Zero-Auth Overhaul
            pass

    def save(self, data: dict) -> None:
        """Persist a new config dict to disk and update in-memory state."""
        with self._lock:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2)
            self._data = data
            logging.info("Config saved to disk.")

    # ------------------------------------------------------------------
    # Dict-like helpers so callers can do config_mgr.get(...)
    # ------------------------------------------------------------------

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def __getitem__(self, key):
        with self._lock:
            return self._data[key]

    def __contains__(self, key):
        with self._lock:
            return key in self._data

    def as_dict(self) -> dict:
        """Return a shallow copy of the current config."""
        with self._lock:
            return dict(self._data)


# -----------------------------------------------------------------------
# Module-level singleton — everything in the codebase imports this
# -----------------------------------------------------------------------
_manager = ConfigManager()

# Backward-compatible alias: callers that do `from core.config import APP_CONFIG`
# get a live reference to the manager itself (supports .get(), [] etc.)
APP_CONFIG = _manager


def get_config() -> ConfigManager:
    """Return the live ConfigManager instance."""
    return _manager


def reload_config() -> None:
    """Reload config from disk. Call after the installer wizard saves new settings."""
    _manager.reload()


# ------------------------------------------------------------------
# Convenience accessors (unchanged API surface)
# ------------------------------------------------------------------

def get_models() -> list:
    d = _manager.as_dict()
    if "models" in d:
        return d["models"]
    return [{
        "provider": d.get("provider", "ollama"),
        "model": d.get("model", "qwen2.5:3b"),
        "ollama_url": d.get("ollama_url", "http://localhost:11434"),
        "api_key_env": d.get("api_key_env", "OPENAI_API_KEY"),
        "role": "default",
    }]


def get_provider() -> str:
    return _manager.get("provider", "ollama")


def get_model() -> str:
    return _manager.get("model", "qwen2.5:3b")


def get_ollama_url() -> str:
    return _manager.get("ollama_url", "http://localhost:11434")


def get_api_key_env() -> str:
    return _manager.get("api_key_env", "OPENAI_API_KEY")


def is_platform_enabled(platform_name: str) -> bool:
    platforms = _manager.get("platforms", {})
    return platforms.get(platform_name, {}).get("enabled", False)


def get_platform_token(platform_name: str):
    platforms = _manager.get("platforms", {})
    return platforms.get(platform_name, {}).get("token", None)


def is_webui_enabled() -> bool:
    return _manager.get("webui", {}).get("enabled", False)


def get_webui_port() -> int:
    return _manager.get("webui", {}).get("port", 8501)



# Zero-Auth: get_local_api_key removed.
