import os
import requests
import zipfile
import io
import logging

SKILLS_DIR = os.path.dirname(__file__)

class ClawHubClient:
    """
    Client to interact with ClawHub or arbitrary GitHub registries to download
    and install AgentSkills.
    """
    def __init__(self):
        self.api_base = "https://api.github.com/repos" # Using GitHub as mock ClawHub for clone

    def download_and_install(self, repo_url):
        """
        Downloads a skill from a given URL (e.g. github zipball) and extracts it.
        For this clone, we simulate fetching a standard skill structure and writing it to skills/
        """
        logging.info(f"Connecting to ClawHub to install skill from {repo_url}...")
        try:
            # Simulated zip download for the clone
            if "github.com" in repo_url:
                zip_url = repo_url.rstrip('/') + "/archive/refs/heads/main.zip"
                response = requests.get(zip_url)
                if response.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                        # Extract directly to skills dir (flattening if needed, but keeping simple for demo)
                        z.extractall(SKILLS_DIR)
                    logging.info("Skill downloaded successfully.")
                    return True
            else:
                logging.error("Unsupported ClawHub URL format.")
                return False
        except Exception as e:
            logging.error(f"Failed to download skill: {e}")
            return False

    def install_default_skills(self):
        """
        Instead of downloading, we just create a few default local skills inline 
        for the sake of the clone setup.
        """
        logging.info("Installing ClawHub default skills...")
        
        system_skill_path = os.path.join(SKILLS_DIR, "system_info.py")
        if not os.path.exists(system_skill_path):
            with open(system_skill_path, "w") as f:
                f.write('''
from skills.manager import BaseSkill
import os
import platform

class SystemInfoSkill(BaseSkill):
    name = "SystemInfo"
    description = "Provides information about the host system."

    def get_tools(self):
        return [{
            "type": "function",
            "function": {
                "name": "get_system_info",
                "description": "Returns basic OS platform info for context",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }]

    def get_system_info(self):
        return f"OS: {platform.system()} {platform.release()}, Arch: {platform.machine()}"
''')
        logging.info("Default skills installed successfully.")
