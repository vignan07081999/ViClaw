"""
skills/manager.py — ViClaw Skill Manager

Improvements in this version:
  - Delta loading: _load_new_skills() only imports modules not already loaded,
    preventing duplicate instantiation and unnecessary state resets on ClawHub installs
  - _load_all_skills() remains for initial full load at startup
  - importlib.reload() used to pick up code changes in already-imported modules
"""

import os
import importlib
import importlib.util
import inspect
import logging

SKILLS_DIR = os.path.dirname(__file__)


class BaseSkill:
    """Base class for all ViClaw / ClawHub skills."""
    name = "BaseSkill"
    description = "A standard skill."

    def get_tools(self) -> list:
        """Return a list of OpenAI-style tool dicts for this skill."""
        return []

    def execute(self, tool_name: str, kwargs: dict):
        """Route a tool call to the matching method."""
        method = getattr(self, tool_name, None)
        if method and callable(method):
            return method(**kwargs)
        raise NotImplementedError(f"Tool '{tool_name}' not implemented in {self.name}")


class SkillManager:
    def __init__(self):
        self.skills: dict = {}        # name -> instance
        self.tools_schema: list = []  # flat list of all tool dicts
        self._loaded_modules: set = set()   # track which .py files we've processed
        self._load_all_skills()

    # ------------------------------------------------------------------
    # Full load (used at startup)
    # ------------------------------------------------------------------

    def _load_all_skills(self):
        """Discover and load every skill in the skills/ directory."""
        logging.info("Loading skills...")
        self.skills.clear()
        self.tools_schema.clear()
        self._loaded_modules.clear()

        _SKIP = {"__init__.py", "manager.py", "clawhub_client.py"}
        for filename in sorted(os.listdir(SKILLS_DIR)):
            if filename.endswith(".py") and filename not in _SKIP:
                self._import_skill_file(filename)

    # ------------------------------------------------------------------
    # Delta load (used after ClawHub installs a new skill at runtime)
    # ------------------------------------------------------------------

    def _load_new_skills(self):
        """
        Only load skill files that have not been processed yet.
        Existing skills are left untouched so their state is preserved.
        """
        _SKIP = {"__init__.py", "manager.py", "clawhub_client.py"}
        new_files = [
            f for f in sorted(os.listdir(SKILLS_DIR))
            if f.endswith(".py") and f not in _SKIP and f not in self._loaded_modules
        ]
        if not new_files:
            logging.info("No new skill files detected.")
            return
        for filename in new_files:
            logging.info(f"Delta-loading new skill: {filename}")
            self._import_skill_file(filename)

    # ------------------------------------------------------------------
    # Internal: import one skill file and register its BaseSkill subclasses
    # ------------------------------------------------------------------

    def _import_skill_file(self, filename: str):
        module_name = filename[:-3]
        try:
            full_module = f"skills.{module_name}"
            if full_module in dir(importlib.util):
                module = importlib.reload(importlib.import_module(full_module))
            else:
                module = importlib.import_module(full_module)

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                    instance = obj()
                    # Avoid re-registering a skill with the same name
                    if instance.name not in self.skills:
                        self.skills[instance.name] = instance
                        self.tools_schema.extend(instance.get_tools())
                        logging.info(f"Loaded skill: {instance.name}")
                    else:
                        logging.debug(f"Skill '{instance.name}' already registered — skipping duplicate.")

            self._loaded_modules.add(filename)
        except Exception as e:
            logging.error(f"Failed to load skill module '{module_name}': {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_loaded_skills_info(self) -> list:
        return [{"name": s.name, "description": s.description} for s in self.skills.values()]

    def get_all_tools(self) -> list:
        return self.tools_schema

    def execute_tool(self, tool_name: str, arguments: dict):
        """Route a tool call to the owning skill."""
        for skill in self.skills.values():
            for tool in skill.get_tools():
                if tool.get("function", {}).get("name") == tool_name:
                    return skill.execute(tool_name, arguments)
        return f"Error: Tool '{tool_name}' not found in any loaded skills."
