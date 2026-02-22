import os
import sys

# Auto-enforce virtual environment
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import logging
import time
import threading

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import OpenClawAgent
from integrations.messaging import PlatformManager
from core.updater import UpdaterEngine
from core.config import APP_CONFIG, setup_logging, get_config
from webui.app import start_webui

setup_logging()

_FREQ_TO_SECONDS = {
    "Every hour": 3600,
    "Weekly": 604800,
    "Daily": 86400,
}

def run_ota_auto_updater():
    """Background thread that periodically checks for updates and auto-applies them."""
    while True:
        try:
            config = get_config()
            updater_config = config.get("updater", {})
            if updater_config.get("auto_update", False):
                freq_str = updater_config.get("frequency", "Daily")
                sleep_time = _FREQ_TO_SECONDS.get(freq_str, 86400)

                updater = UpdaterEngine()
                has_update, _, _, _ = updater.check_for_updates()
                if has_update:
                    logging.info("OTA: New commits detected. Pulling update...")
                    success, msg = updater.trigger_pull()
                    if success:
                        logging.warning(f"OTA update successful. Restarting daemon. {msg}")
                        os._exit(0)
                    else:
                        logging.error(f"OTA update failed: {msg}")
                time.sleep(sleep_time)
            else:
                time.sleep(3600)
        except Exception as e:
            logging.error(f"Auto-updater thread crashed: {e}")
            time.sleep(3600)

def main():
    logging.info("Starting ViClaw Daemon...")

    print("==================================================")
    print("              ViClaw Agent Core                   ")
    print("==================================================")

    if not APP_CONFIG:
        logging.warning("Config is empty. Please run ./install.sh first.")

    # Start OTA updater background thread
    threading.Thread(target=run_ota_auto_updater, daemon=True).start()

    is_daemon = "--daemon" in sys.argv
    platform_manager = PlatformManager(is_daemon=is_daemon)

    # Initialize Core Agent
    agent = OpenClawAgent(platform_manager)

    # Start the WebUI (if enabled in config)
    start_webui(agent)

    # Start messaging platform listeners
    platform_manager.start_all(agent.handle_message)

    # Start proactive heartbeat
    agent.start_heartbeat()

    logging.info("ViClaw is running. Press Ctrl+C to terminate.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down ViClaw...")

if __name__ == "__main__":
    main()
