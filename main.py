import os
import sys
import logging
import time
import threading

# Ensure we're running from the root of OpenClawClone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import OpenClawAgent
import schedule
from integrations.messaging import PlatformManager
from integrations.telegram import TelegramConnector
from integrations.whatsapp import WhatsAppConnector
from integrations.discord import DiscordConnector
from core.updater import UpdaterEngine
from core.config import APP_CONFIG, setup_logging, get_config
from core.skill_manager import SkillManager
from webui.app import start_webui

setup_logging()

def run_ota_auto_updater():
    """Background thread that periodically checks for updates and auto-applies them if configured."""
    
    while True:
        try:
            config = get_config()
            updater_config = config.get("updater", {})
            if updater_config.get("auto_update", False):
                freq_str = updater_config.get("frequency", "Daily")
                
                # Determine sleep interval
                if freq_str == "Every hour":
                    sleep_time = 3600
                elif freq_str == "Weekly":
                    sleep_time = 604800
                else: # Daily
                    sleep_time = 86400
                    
                updater = UpdaterEngine()
                has_update, _, _, _ = updater.check_for_updates()
                if has_update:
                    logging.info("OTA Auto-updater detected new Github commits. Pulling update...")
                    success, msg = updater.trigger_pull()
                    if success:
                        logging.warning(f"OTA Auto-Update successful. Restarting daemon. {msg}")
                        # Cleanly terminate the Python daemon so systemd or launcher.py restarts us
                        os._exit(0) 
                    else:
                        logging.error(f"OTA Auto-Update failed: {msg}")
                        
            # If auto-update is off or we just checked, wait an hour before checking config again
            time.sleep(3600 if 'sleep_time' not in locals() else sleep_time)
            
        except Exception as e:
            logging.error(f"Auto-updater thread crashed: {e}")
            time.sleep(3600) # Wait an hour on crash

def main():
    config = get_config()
    logging.info("Starting OpenClawClone Daemon...")

    print("==================================================")
    print("              OpenClaw Agent Core                 ")
    print("==================================================")

    if not APP_CONFIG:
        logging.warning("App config is empty. Please run install.sh or install.py first.")

    # Start auto-updater heartbeat thread
    t_ota = threading.Thread(target=run_ota_auto_updater, daemon=True)
    t_ota.start()

    # Load skills
    skill_manager = SkillManager()

    # Initialize Managers
    is_daemon = "--daemon" in sys.argv
    platform_manager = PlatformManager(is_daemon=is_daemon)
    
    # Initialize Core Agent
    agent = OpenClawAgent(platform_manager, skill_manager) # Pass skill_manager to agent
    
    # Start the WebUI (if enabled)
    start_webui(agent)

    # Start the messaging platforms listening
    platform_manager.start_all(agent.handle_message)
    
    # Start the agent heartbeat for background async tasks
    agent.start_heartbeat()
    
    logging.info("OpenClaw is running. Press Ctrl+C to terminate.")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down OpenClaw...")

if __name__ == "__main__":
    main()
