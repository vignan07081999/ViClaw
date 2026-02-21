import subprocess
from skills.manager import BaseSkill

class ShellEngineSkill(BaseSkill):
    name = "shell_engine"
    description = "Execute local bash commands directly on the host machine. Gives the agent full MCP control over the OS."
    
    def get_tool_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "execute_shell",
                "description": "Execute a bash shell command locally on the Linux machine. Use this for system management, file I/O, networking, and running scripts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The exact bash command to execute."
                        }
                    },
                    "required": ["command"]
                }
            }
        }

    def execute_shell(self, command: str) -> str:
        try:
            # We add a 60 second timeout to prevent the agent from hanging on interactive prompts (like ssh without keys)
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                out = result.stdout.strip()
                return out if out else f"Command '{command}' executed successfully with no output."
            else:
                return f"Error (Exit Code {result.returncode}): {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "Execution failed: Command timed out after 60 seconds. Do not run interactive commands."
        except Exception as e:
            return f"Execution failed: {str(e)}"
