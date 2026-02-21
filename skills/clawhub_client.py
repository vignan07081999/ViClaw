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
        Downloads a skill. For the clone, we support direct GitHub Raw URLs
        or we automatically convert standard GitHub blob URLs to raw content.
        """
        logging.info(f"Connecting to ClawHub to install skill from {repo_url}...")
        try:
            # Convert standard github link to raw link if necessary
            if "github.com" in repo_url and "/blob/" in repo_url:
                repo_url = repo_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            
            # Fetch the skill block
            response = requests.get(repo_url, timeout=10)
            if response.status_code == 200:
                content = response.text
                
                # Try to extract a class name for the file name, or fallback to URL suffix
                file_name = repo_url.split("/")[-1]
                if not file_name.endswith(".py"):
                    # Attempt crude parsing if not specified
                    import re
                    match = re.search(r'class\s+([A-Za-z0-9_]+)', content)
                    if match:
                        file_name = match.group(1).lower() + ".py"
                    else:
                        file_name = "custom_skill.py"
                        
                target_path = os.path.join(SKILLS_DIR, file_name)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                logging.info(f"Skill compiled and installed to {target_path}.")
                return True
            else:
                logging.error(f"Failed to fetch. Server returned {response.status_code}")
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
