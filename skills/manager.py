import os
import importlib
import inspect
import logging

SKILLS_DIR = os.path.dirname(__file__)

class BaseSkill:
    """
    All ClawHub skills should inherit from this class.
    """
    name = "BaseSkill"
    description = "A standard skill."
    
    def get_tools(self):
        """
        Returns a list of dicts formatted for OpenAI/LiteLLM tool calls.
        Override this to provide callable tools to the agent.
        """
        return []

    def execute(self, tool_name, kwargs):
        """
        Executes the requested tool.
        """
        method = getattr(self, tool_name, None)
        if method and callable(method):
            return method(**kwargs)
        raise NotImplementedError(f"Tool {tool_name} not implemented in {self.name}")

class SkillManager:
    def __init__(self):
        self.skills = {}
        self.tools_schema = []
        self._load_all_skills()

    def _load_all_skills(self):
        logging.info("Loading skills...")
        for filename in os.listdir(SKILLS_DIR):
            if filename.endswith(".py") and filename not in ["__init__.py", "manager.py", "clawhub_client.py"]:
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f"skills.{module_name}")
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BaseSkill) and obj is not BaseSkill:
                            skill_instance = obj()
                            self.skills[skill_instance.name] = skill_instance
                            self.tools_schema.extend(skill_instance.get_tools())
                            logging.info(f"Loaded skill: {skill_instance.name}")
                except Exception as e:
                    logging.error(f"Failed to load skill module {module_name}: {e}")

    def get_loaded_skills_info(self):
        return [{"name": s.name, "description": s.description} for s in self.skills.values()]

    def get_all_tools(self):
        return self.tools_schema

    def execute_tool(self, tool_name, arguments):
        """
        Routes the tool execution to the appropriate skill.
        This assumes tool_name is unique across all loaded skills.
        """
        for skill in self.skills.values():
            # Check if this skill owns the tool
            for tool in skill.get_tools():
                if tool.get("function", {}).get("name") == tool_name:
                    return skill.execute(tool_name, arguments)
        
        return f"Error: Tool '{tool_name}' not found in any loaded skills."
