import time
import logging
import json
import threading

from core.models import LLMRouter
from core.memory import AgentMemory
from core.personality import PersonalityProfile
from skills.manager import SkillManager
from skills.clawhub_client import ClawHubClient
from core.config import APP_CONFIG

class OpenClawAgent:
    def __init__(self, platform_manager):
        self.platform_manager = platform_manager
        self.router = LLMRouter()
        self.memory = AgentMemory()
        self.personality = PersonalityProfile(self.memory)
        self.skill_manager = SkillManager()
        
        # Load default skills if configured
        if APP_CONFIG.get("skills", {}).get("install_defaults", True):
            client = ClawHubClient()
            client.install_default_skills()
            self.skill_manager._load_all_skills()

        self.running = False

    def handle_message(self, platform_name, user_id, message_text):
        """
        Callback invoked by the messaging platforms when a user sends a message.
        """
        logging.info(f"Received from {platform_name} user {user_id}: {message_text}")
        
        # Add to short term memory
        self.memory.add_short_term("user", message_text)
        
        # Construct dynamic prompt
        system_prompt = self.personality.construct_system_prompt(current_query=message_text)
        context = self.memory.get_short_term_context()[:-1] # Exclude the user message we just added
        
        # Get tools
        tools = self.skill_manager.get_all_tools()
        
        # Query Model
        response = self.router.generate(message_text, system_prompt=system_prompt, context=context, tools=tools)
        
        # Add assistant response to short term
        if response["content"]:
            self.memory.add_short_term("assistant", response["content"])
            self.platform_manager.send(platform_name, user_id, response["content"])
        
        # Handle autonomous tool calls
        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                tool_name = tc.get("function", {}).get("name")
                tool_args = tc.get("function", {}).get("arguments", {})
                logging.info(f"Agent requested tool: {tool_name} with {tool_args}")
                
                try:
                    tool_result = self.skill_manager.execute_tool(tool_name, tool_args)
                    self.memory.add_short_term("system", f"Tool {tool_name} returned: {tool_result}")
                    
                    # Optionally, do a second reasoning pass with the tool result (if the issue is complex)
                    sys_prompt_pass2 = "You just executed a tool. Finalize your answer based on the result. Be concise."
                    final_res = self.router.generate("Review the tool results and answer.", system_prompt=sys_prompt_pass2, context=self.memory.get_short_term_context())
                    if final_res["content"]:
                        self.platform_manager.send(platform_name, user_id, final_res["content"])
                        self.memory.add_short_term("assistant", final_res["content"])
                except Exception as e:
                    logging.error(f"Error executing tool {tool_name}: {e}")
                    self.platform_manager.send(platform_name, user_id, f"I encountered an error running {tool_name}.")

    def process_immediate_message(self, platform_name, user_id, message_text):
        """
        Processes a message synchronously and returns the string response. 
        Used by the local WebUI and CLI chat script.
        """
        logging.info(f"Sync Request from {platform_name} user {user_id}: {message_text}")
        
        self.memory.add_short_term("user", message_text)
        system_prompt = self.personality.construct_system_prompt(current_query=message_text)
        context = self.memory.get_short_term_context()[:-1] 
        tools = self.skill_manager.get_all_tools()
        
        response = self.router.generate(message_text, system_prompt=system_prompt, context=context, tools=tools)
        
        final_reply = response["content"]
        
        if response["content"]:
            self.memory.add_short_term("assistant", response["content"])
            
        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                tool_name = tc.get("function", {}).get("name")
                tool_args = tc.get("function", {}).get("arguments", {})
                try:
                    tool_result = self.skill_manager.execute_tool(tool_name, tool_args)
                    self.memory.add_short_term("system", f"Tool {tool_name} returned: {tool_result}")
                    
                    sys_prompt_pass2 = "You just executed a tool. Finalize your answer based on the result. Be concise."
                    final_res = self.router.generate("Review the tool results and answer.", system_prompt=sys_prompt_pass2, context=self.memory.get_short_term_context())
                    
                    if final_res["content"]:
                        final_reply += f"\n\n{final_res['content']}"
                        self.memory.add_short_term("assistant", final_res["content"])
                except Exception as e:
                    err_msg = f"I encountered an error running {tool_name}."
                    final_reply += f"\n\n{err_msg}"
                    logging.error(e)
                    
        return final_reply

    def start_heartbeat(self):
        """
        A background loop that allows the agent to act proactively on schedule or monitor state.
        """
        self.running = True
        logging.info("Starting OpenClaw Heartbeat...")
        
        def loop():
            while self.running:
                # In a full implementation, the heartbeat evaluates timed tasks or pending jobs.
                time.sleep(60) # Wake every 60 seconds
                
        t = threading.Thread(target=loop, daemon=True)
        t.start()
