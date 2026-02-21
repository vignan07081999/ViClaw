import os
import json
from skills.manager import AgentSkill

class RemindersSkill(AgentSkill):
    name = "reminders"
    description = "Set reminders or background tasks that the agent should proactively evaluate during its heartbeat."
    
    def get_tool_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "set_reminder",
                "description": "Save a persistent reminder or a routine condition to check proactively in the future.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Short topic of the reminder (e.g., 'lab_server_check' or 'grocery_list')."
                        },
                        "instruction": {
                            "type": "string",
                            "description": "What the agent should remember to do or check when idle."
                        }
                    },
                    "required": ["topic", "instruction"]
                }
            }
        }

    def set_reminder(self, topic: str, instruction: str) -> str:
        reminders_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reminders.json")
        reminders = []
        if os.path.exists(reminders_file):
            with open(reminders_file, "r") as f:
                try:
                    reminders = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        reminders.append({"topic": topic, "instruction": instruction})
        
        with open(reminders_file, "w") as f:
            json.dump(reminders, f, indent=2)
            
        return f"Reminder for '{topic}' saved successfully. It will be evaluated proactively."
