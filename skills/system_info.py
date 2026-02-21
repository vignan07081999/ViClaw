
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

    def get_system_info(self, **kwargs):
        return f"OS: {platform.system()} {platform.release()}, Arch: {platform.machine()}"
