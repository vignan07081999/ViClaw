import os
import sys
import logging
import time

# Ensure we're running from the root of OpenClawClone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import OpenClawAgent
from integrations.messaging import PlatformManager
from webui.app import start_webui
from core.config import APP_CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("==================================================")
    print("              OpenClaw Agent Core                 ")
    print("==================================================")

    if not APP_CONFIG:
        logging.warning("App config is empty. Please run install.sh or install.py first.")

    # Initialize Managers
    platform_manager = PlatformManager()
    
    # Initialize Core Agent
    agent = OpenClawAgent(platform_manager)
    
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
