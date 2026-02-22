import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from skills.manager import BaseSkill
from core.config import APP_CONFIG

class HomeLabSkill(BaseSkill):
    name = "HomeLab"
    description = "Provides native API integration for HomeLab services like Home Assistant, Proxmox, Radarr, Sonarr, and Jellyfin."

    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_home_assistant",
                    "description": "Get the state of a specific entity in Home Assistant (e.g., light.living_room).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string", "description": "The exact ID of the HA entity."}
                        },
                        "required": ["entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "control_home_assistant",
                    "description": "Call a service in Home Assistant (e.g. turning a light on or off).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "description": "The HA domain (e.g., 'light', 'switch')."},
                            "service": {"type": "string", "description": "The service to call (e.g., 'turn_on', 'turn_off')."},
                            "entity_id": {"type": "string", "description": "The target entity ID."}
                        },
                        "required": ["domain", "service", "entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_arr_service",
                    "description": "Query Sonarr or Radarr to search for TV shows or Movies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "description": "Either 'sonarr' or 'radarr'."},
                            "search_term": {"type": "string", "description": "The movie or TV show name to look up."}
                        },
                        "required": ["service", "search_term"]
                    }
                }
            }
        ]

    def _get_api_config(self, service_name):
        keys = APP_CONFIG.get("api_keys", {})
        if service_name not in keys:
            return None
        return keys[service_name]

    def query_home_assistant(self, entity_id):
        ha_config = self._get_api_config("home_assistant")
        if not ha_config:
            return "Error: Home Assistant API token not configured in ViClaw."
        
        url = f"http://{ha_config['ip']}:8123/api/states/{entity_id}"
        headers = {
            "Authorization": f"Bearer {ha_config['token']}",
            "Content-Type": "application/json",
        }
        
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                return f"Entity {entity_id} is currently '{data.get('state')}'. Attributes: {data.get('attributes')}"
            return f"HA returned an error: {res.status_code} - {res.text}"
        except Exception as e:
            return f"Failed to connect to Home Assistant: {e}"

    def control_home_assistant(self, domain, service, entity_id):
        ha_config = self._get_api_config("home_assistant")
        if not ha_config:
            return "Error: Home Assistant API token not configured in ViClaw."
            
        url = f"http://{ha_config['ip']}:8123/api/services/{domain}/{service}"
        headers = {
            "Authorization": f"Bearer {ha_config['token']}",
            "Content-Type": "application/json",
        }
        
        try:
            res = requests.post(url, headers=headers, json={"entity_id": entity_id}, timeout=5)
            if res.status_code == 200:
                return f"Successfully called {domain}.{service} on {entity_id}."
            return f"HA returned an error: {res.status_code} - {res.text}"
        except Exception as e:
            return f"Failed to command Home Assistant: {e}"

    def query_arr_service(self, service, search_term):
        service = service.lower()
        if service not in ["sonarr", "radarr"]:
            return "Error: Service must be 'sonarr' or 'radarr'."
            
        api_config = self._get_api_config(service)
        if not api_config:
            return f"Error: {service.capitalize()} API token not configured in ViClaw."
            
        port = 8989 if service == "sonarr" else 7878
        url = f"http://{api_config['ip']}:{port}/api/v3/series/lookup" if service == "sonarr" else f"http://{api_config['ip']}:{port}/api/v3/movie/lookup"
        
        headers = {
            "X-Api-Key": api_config["token"]
        }
        
        try:
            res = requests.get(url, headers=headers, params={"term": search_term}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if not data:
                    return f"No results found for '{search_term}' on {service.capitalize()}."
                
                output = f"Top 3 Results from {service.capitalize()}:\n"
                for i, item in enumerate(data[:3]):
                    title = item.get("title", "Unknown")
                    year = item.get("year", "Unknown")
                    status = item.get("status", "Unknown")
                    output += f"{i+1}. {title} ({year}) - Status: {status}\n"
                return output
            return f"{service.capitalize()} returned an error: {res.status_code}"
        except Exception as e:
            return f"Failed to query {service.capitalize()}: {e}"
