import os
from skills.manager import BaseSkill

class FileIOSkill(BaseSkill):
    name = "FileIO"
    description = "Allows the agent to read, write, and create files and directories on the local file system. Crucial for building applications."

    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Writes content to a file. Overwrites the file if it exists, creates it if it doesn't.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {"type": "string", "description": "Absolute or relative path to the file"},
                            "content": {"type": "string", "description": "The textual content to write"}
                        },
                        "required": ["filepath", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Reads the text content of a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {"type": "string", "description": "Path to the file to read"}
                        },
                        "required": ["filepath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_directory",
                    "description": "Creates a new directory (and its parents if necessary).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dirpath": {"type": "string", "description": "Path of the directory to create"}
                        },
                        "required": ["dirpath"]
                    }
                }
            }
        ]

    def write_file(self, filepath, content):
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {filepath}"
        except Exception as e:
            return f"Error writing file {filepath}: {str(e)}"

    def read_file(self, filepath):
        try:
            if not os.path.exists(filepath):
                return f"Error: File {filepath} does not exist."
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {filepath}: {str(e)}"

    def create_directory(self, dirpath):
        try:
            os.makedirs(dirpath, exist_ok=True)
            return f"Successfully ensured directory exists: {dirpath}"
        except Exception as e:
            return f"Error creating directory {dirpath}: {str(e)}"
