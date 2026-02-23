import time
import logging
import json
import re
import os
import subprocess
import threading

from core.models import LLMRouter
from core.memory import AgentMemory
from core.personality import PersonalityProfile
from core.scheduler import TaskScheduler
from core.swarm import SwarmOrchestrator
from skills.manager import SkillManager
from skills.clawhub_client import ClawHubClient
from skills.clawhub_bridge import get_installed_skills_context
from core.config import APP_CONFIG

class ViClawAgent:
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

        self.scheduler = TaskScheduler(self)
        self.scheduler.start()
        
        self.swarm = SwarmOrchestrator(self)
        
        from core.hooks import HookManager
        self.hooks = HookManager(self)
        self.hooks.start()

        self.running = False

    def switch_session(self, session_id: str):
        """Hot-swaps the active memory session."""
        self.memory = AgentMemory(session_id=session_id)
        logging.info(f"Switched session to: {session_id}")
        return f"Switched to session '{session_id}'. Previous context cleared from window."

    def _process_slash_command(self, command_text):
        cmd = command_text.strip()
        parts = cmd.split()
        base_cmd = parts[0].lower()

        if base_cmd == "/reset":
            self.memory.clear_short_term()
            return f"Session '{self.memory.session_id}' reset. Short-term memory cleared."
        elif base_cmd == "/new":
            session_id = parts[1] if len(parts) > 1 else "default"
            if session_id == "default":
                self.memory.clear_short_term("default")
            return self.switch_session(session_id)
        elif base_cmd == "/status":
            num_msgs = len(self.memory.short_term_context)
            fast_mod = getattr(self.router, 'fast_model', None)
            comp_mod = getattr(self.router, 'complex_model', None)
            fm_name = fast_mod['model'] if fast_mod else 'None'
            cm_name = comp_mod['model'] if comp_mod else 'None'
            return f"🟢 Agent Online\n- Fast Model: {fm_name}\n- Complex Model: {cm_name}\n- Short-term messages: {num_msgs}"
        elif base_cmd == "/think":
            level = parts[1] if len(parts) > 1 else "default"
            self.memory.add_short_term("system", f"Reasoning level set to {level}")
            return f"Reasoning level set to {level}."
        elif base_cmd == "/compact":
            self.memory.summarize_and_compress()
            return "Context compacted."
        else:
            return f"Unknown command: {base_cmd}"

    def handle_message(self, platform_name, user_id, message_text):
        """
        Callback invoked by the messaging platforms when a user sends a message.
        """
        logging.info(f"Received from {platform_name} user {user_id}: {message_text}")
        
        # Intercept commands
        if message_text.strip().startswith("/"):
            response_text = self._process_slash_command(message_text)
            self.platform_manager.send(platform_name, user_id, response_text)
            return
            
        # Add to short term memory
        self.memory.add_short_term("user", message_text)
        
        # Construct dynamic prompt
        system_prompt = self.personality.construct_system_prompt(current_query=message_text)
        context = self.memory.get_short_term_context()[:-1] # Exclude the user message we just added
        
        # Get tools and construct XML prompt
        tools = self.skill_manager.get_all_tools()
        tools_xml_prompt = "\n\nAVAILABLE TOOLS:\nYou have access to the following tools. To use a tool, you MUST output an XML block like this: <tool name=\"tool_name\">{\"arg_name\": \"arg_value\"}</tool>. Do NOT output any raw JSON outside of the XML block. If you do not need a tool, just answer normally.\nTools available:\n"
        import json
        for t in tools:
            tools_xml_prompt += f"- {t['function']['name']}: {t['function'].get('description', '')}\n  Schema: {json.dumps(t['function'].get('parameters', {}))}\n"
        
        system_prompt += tools_xml_prompt
        
        # Inject ClawHub SKILL.md context (makes SKILL.md-based skills active)
        clawhub_context = get_installed_skills_context()
        if clawhub_context:
            system_prompt += clawhub_context

        # Inject RAG Vector Memory Context
        related_memories = self.memory.search_long_term(message_text, top_k=3, router=self.router)
        if related_memories:
            system_prompt += "\n\n[RELEVANT LONG-TERM MEMORIES (RAG)]:\n"
            for i, r in enumerate(related_memories):
                system_prompt += f"{i+1}. {r}\n"
        
        # Query Model (no native tools parameter)
        response = self.router.generate(message_text, system_prompt=system_prompt, context=context)
        
        # Add assistant response to short term
        if response["content"]:
            self.memory.add_short_term("assistant", response["content"])
            self.platform_manager.send(platform_name, user_id, response["content"])
        
        # Handle autonomous tool calls in a batched execution pass
        if response["tool_calls"]:
            executed_results = []
            for tc in response["tool_calls"]:
                tool_name = tc.get("function", {}).get("name")
                tool_args = tc.get("function", {}).get("arguments", {})
                
                # Fast type enforcement for hallucinated empty string parameters dicts
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args) if tool_args.strip() else {}
                    except (json.JSONDecodeError, ValueError):
                        tool_args = {}
                elif not isinstance(tool_args, dict):
                    tool_args = {}
                    
                logging.info(f"Agent requested tool: {tool_name} with {tool_args}")
                
                try:
                    tool_result = self.skill_manager.execute_tool(tool_name, tool_args)
                    executed_results.append(f"[TOOL EXECUTION RESULT: {tool_name}]\n{tool_result}")
                except Exception as e:
                    logging.error(f"Error executing tool {tool_name}: {e}")
                    executed_results.append(f"[TOOL EXECUTION ERROR: {tool_name}]\n{e}")
            
            # Combine all results into single memory block
            combined_results = "\n\n".join(executed_results)
            self.memory.add_short_term("user", combined_results)
            
            # Single reasoning pass for all batched tool executions
            try:
                sys_prompt_pass2 = "You successfully executed one or more tools. Summarize the results conversationally for the user. Do NOT output raw JSON, internal tool dictionaries, or any <tool> tags. Provide a human readable response."
                final_res = self.router.generate("Review the compiled tool results and provide the final answer conversationally.", system_prompt=sys_prompt_pass2, context=self.memory.get_short_term_context())
                if final_res.get("content"):
                    self.platform_manager.send(platform_name, user_id, final_res["content"])
                    self.memory.add_short_term("assistant", final_res["content"])
            except Exception as e:
                logging.error(f"Error formulating summary pass: {e}")
                self.platform_manager.send(platform_name, user_id, "I executed the operations successfully, but encountered an error translating the logs.")

    def process_immediate_message(self, platform_name, user_id, message_text, images=None):
        """
        Processes a message synchronously and returns the string response. 
        Used by the local WebUI and CLI chat script.
        """
        logging.info(f"Sync Request from {platform_name} user {user_id}: {message_text}")
        
        if message_text.strip().startswith("/"):
            return self._process_slash_command(message_text)
            
        # *** Check for Pending Autonomous Actions ***
        last_msg = self.memory.short_term[-1] if self.memory.short_term else None
        if last_msg and last_msg["role"] == "system" and "[PENDING_ACTION]" in last_msg["content"]:
            pending_action = last_msg["content"]
            import re
            act_type = re.search(r"type:(.*?)\s", pending_action).group(1)
            target = re.search(r"target:(.*?)\s", pending_action).group(1)
            original_msg = re.search(r"original_msg:(.*)", pending_action).group(1)
            
            # User approval
            if message_text.lower().strip() in ["yes", "y", "sure", "do it", "ok", "okay"]:
                # Execute the dependency installation safely
                import subprocess
                self.memory.add_short_term("system", f"User approved installation of {target}.")
                try:
                    if act_type == "pip_install":
                        import sys
                        result = subprocess.run([sys.executable, "-m", "pip", "install", target], capture_output=True, text=True)
                    elif act_type == "apt_install":
                        # Attempt to use sudo if available
                        result = subprocess.run(f"sudo apt-get install -y {target}", shell=True, capture_output=True, text=True)
                    elif act_type == "clawhub_skill":
                        self.memory.add_short_term("system", f"Fetching {target} from ClawHub...")
                        
                        # 1. Fetch available skills from index
                        from webui.app import browse_clawhub
                        index = browse_clawhub()
                        skill_info = next((s for s in index.get("skills", []) if s["id"] == target or s["name"].lower() == target.lower()), None)
                        
                        if not skill_info:
                            # Try fuzzy match
                            skill_info = next((s for s in index.get("skills", []) if target.lower() in s["name"].lower()), None)

                        if skill_info:
                            client = ClawHubClient()
                            result = client.install_skill(skill_info["slug"] if "slug" in skill_info else skill_info.get("id", target))
                            if result.get("success"):
                                self.skill_manager._load_new_skills()
                                self.memory.add_short_term("system", f"Skill {skill_info.get('displayName', skill_info.get('name', target))} installed dynamically. Retrying prompt: '{original_msg}'")
                                message_text = original_msg
                                result = type('obj', (object,), {'returncode': 0})()
                            else:
                                self.memory.add_short_term("system", f"Failed to install skill: {result.get('message', 'unknown error')}")
                                return f"I tried to install `{target}` but the download failed. Check my logs.", []
                        else:
                            self.memory.add_short_term("system", f"Could not locate {target} in ClawHub.")
                            return f"I searched the ClawHub marketplace but could not find a skill matching `{target}`. Would you like to check the marketplace manualy in the dashboard?", []

                    
                    if act_type in ["pip_install", "apt_install"]:
                        if result.returncode == 0:
                            self.memory.add_short_term("system", f"Installation of {target} succeeded. Automatically retrying the original prompt: '{original_msg}'")
                            # Clear the pending flag by re-injecting the original message to resume the flow organically
                            message_text = original_msg
                        else:
                            self.memory.add_short_term("system", f"Failed to install {target}. Error: {result.stderr}")
                            return f"I tried to install `{target}` but it failed. You may need to install it manually. Error:\n```\n{result.stderr}\n```", []
                except Exception as e:
                    return f"Critical error during installation of {target}: {str(e)}", []
            else:
                self.memory.add_short_term("system", "User denied the pending installation.")
                return f"Okay, I've cancelled the automatic installation of `{target}`. Let me know what else I can do.", []
                
        self.memory.add_short_term("user", message_text)
        
        system_prompt = self.personality.construct_system_prompt(current_query=message_text)
        
        # Feature 7: Link Understanding
        from core.links import extract_and_fetch_links
        link_context = extract_and_fetch_links(message_text)
        if link_context:
            system_prompt += link_context
            
        context = self.memory.get_short_term_context()[:-1] 
        tools = self.skill_manager.get_all_tools()
        tools_xml_prompt = "\n\nAVAILABLE TOOLS:\nYou have access to the following tools. To use a tool, you MUST output an XML block like this: <tool name=\"tool_name\">{\"arg_name\": \"arg_value\"}</tool>. Do NOT output any raw JSON outside of the XML block. If you do not need a tool, just answer normally.\nTools available:\n"
        for t in tools:
            tools_xml_prompt += f"- {t['function']['name']}: {t['function'].get('description', '')}\n  Schema: {json.dumps(t['function'].get('parameters', {}))}\n"
        
        system_prompt += tools_xml_prompt
        
        # Inject ClawHub SKILL.md context (makes SKILL.md-based skills active)
        clawhub_context = get_installed_skills_context()
        if clawhub_context:
            system_prompt += clawhub_context

        # Inject RAG Vector Memory Context
        related_memories = self.memory.search_long_term(message_text, top_k=3, router=self.router)
        if related_memories:
            system_prompt += "\n\n[RELEVANT LONG-TERM MEMORIES (RAG)]:\n"
            for i, r in enumerate(related_memories):
                system_prompt += f"{i+1}. {r}\n"
        
        response = self.router.generate(message_text, system_prompt=system_prompt, context=context, images=images)
        
        final_reply = response.get("content", "") or ""
        raw_tools = []
        
        if ("install" in message_text.lower() or "add" in message_text.lower() or "download" in message_text.lower()) and "skill" in message_text.lower():
            # Try to catch "install the Web Search skill"
            match = re.search(r"(?:install|add|download)(?:\s+the)?\s+(.*?)\s+skill", message_text, re.IGNORECASE)
            if not match:
                # Try "install skill Web Search"
                match = re.search(r"(?:install|add|download)\s+skill\s+(.*)", message_text, re.IGNORECASE)
            
            if match:
                target_skill = match.group(1).strip()
                self.memory.add_short_term("system", f"[PENDING_ACTION] type:clawhub_skill target:{target_skill} original_msg:{message_text}")
                return f"I see you want to install a new capability. Should I search ClawHub for the `{target_skill}` skill and install it?", []

        final_reply = response.get("content", "") or ""
        raw_tools = []
        
        # *** DYNAMIC SKILL RESOLVER ***
        if "I need the" in final_reply and "skill" in final_reply.lower() and "?" in final_reply:
            match = re.search(r"I need the (.*?) skill", final_reply, re.IGNORECASE)
            if match:
                missing_skill = match.group(1).strip()
                self.memory.add_short_term("system", f"[PENDING_ACTION] type:clawhub_skill target:{missing_skill} original_msg:{message_text}")
                final_reply = f"To accomplish this, I need the `{missing_skill}` skill from ClawHub. May I dynamically download and install it now?"
                return final_reply, []
        
        if response.get("content"):
            self.memory.add_short_term("assistant", response["content"])
            
        if response.get("tool_calls"):
            raw_tools = response["tool_calls"]
            executed_results = []
            
            for tc in response["tool_calls"]:
                tool_name = tc.get("function", {}).get("name")
                tool_args = tc.get("function", {}).get("arguments", {})
                
                # Type enforcement
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args) if tool_args.strip() else {}
                    except (json.JSONDecodeError, ValueError):
                        tool_args = {}
                elif not isinstance(tool_args, dict):
                    tool_args = {}
                    
                try:
                    tool_result = self.skill_manager.execute_tool(tool_name, tool_args)
                    executed_results.append(f"[TOOL EXECUTION RESULT: {tool_name}]\n{tool_result}")
                except Exception as e:
                    err_str = str(e)
                    err_msg = f"I encountered an error running {tool_name}: {err_str}"
                    logging.error(e)
                    
                    # *** AUTONOMOUS DEPENDENCY RESOLVER ***
                    if "ModuleNotFoundError" in err_str or "No module named" in err_str:
                        match = re.search(r"No module named '(.*?)'", err_str)
                        missing_mod = match.group(1) if match else "unknown_module"
                        
                        prompt = f"The tool '{tool_name}' failed because the Python module '{missing_mod}' is missing. May I automatically run `pip install {missing_mod}` for you and retry?"
                        
                        # Set a flag in memory so the next user input "yes" triggers the install
                        self.memory.add_short_term("system", f"[PENDING_ACTION] type:pip_install target:{missing_mod} original_msg:{message_text}")
                        return prompt, raw_tools
                        
                    elif "command not found" in err_str.lower():
                        match = re.search(r"(.*): command not found", err_str)
                        missing_cmd = match.group(1).strip().split()[-1] if match else "unknown_command"
                        prompt = f"The shell command failed because '{missing_cmd}' is not installed on this Linux system. May I automatically try to install it using `apt install {missing_cmd}` and retry?"
                        
                        self.memory.add_short_term("system", f"[PENDING_ACTION] type:apt_install target:{missing_cmd} original_msg:{message_text}")
                        return prompt, raw_tools
                    else:
                        executed_results.append(err_msg)
            
            # Combine all batched results into memory
            combined_results = "\n\n".join(executed_results)
            self.memory.add_short_term("user", combined_results)
            
            # Run exactly ONE secondary context inference pass matching the GUI
            try:
                sys_prompt_pass2 = "You successfully executed one or more tools. Summarize the results conversationally for the user. Do NOT output raw JSON, internal tool dictionaries, or any <tool> tags. Provide a human readable response."
                final_res = self.router.generate("Review the structured tool outputs and provide the final answer conversationally.", system_prompt=sys_prompt_pass2, context=self.memory.get_short_term_context())
                
                if final_res.get("content"):
                    curr_reply = final_res['content']
                    if final_reply and not final_reply.isspace():
                        final_reply += f"\n\n{curr_reply}"
                    else:
                        final_reply = curr_reply
                        
                    self.memory.add_short_term("assistant", curr_reply)
            except Exception as e:
                logging.error(f"Failed to generate composite summary: {e}")
                    
        return final_reply, raw_tools

    def start_heartbeat(self):
        """
        A background loop that allows the agent to act proactively on schedule or monitor state.
        Triggers spontaneous action if idle.
        """
        self.running = True
        logging.info("Starting ViClaw Proactive Heartbeat...")
        
        def loop():
            last_action_time = time.time()
            idle_threshold = 300 # 5 minutes
            
            while self.running:
                time.sleep(60) 
                
                # If idle for a while, trigger a proactive reasoning cycle
                if time.time() - last_action_time > idle_threshold:
                    logging.info("Heartbeat: Agent is idle. Triggering proactive inference.")
                    last_action_time = time.time()
                    
                    sys_prompt = self.personality.construct_system_prompt()
                    sys_prompt += "\n\n[SYSTEM EVENT]: You have been idle. Do you have any pending reminders or tasks to execute? If yes, use a tool or send a proactive message. If no, output strictly empty text."
                    
                    # Inject persistent reminders if they exist
                    reminders_file = "data/reminders.json"
                    if os.path.exists(reminders_file):
                        try:
                            with open(reminders_file, "r") as f:
                                reminders_data = json.load(f)
                                if reminders_data:
                                    sys_prompt += "\n\nActive Persistent Reminders:\n"
                                    for r in reminders_data:
                                        sys_prompt += f"- {r['topic']}: {r['instruction']}\n"
                        except Exception:
                            pass
                    
                    context = self.memory.get_short_term_context()
                    tools = self.skill_manager.get_all_tools()
                    
                    try:
                        response = self.router.generate("[Heartbeat Check]", system_prompt=sys_prompt, context=context, tools=tools)
                        
                        if response["content"] and response["content"].strip():
                            # Broadcast proactive message to all enabled platforms
                            self.memory.add_short_term("assistant", response["content"])
                            for platform_name, connector in self.platform_manager.connectors.items():
                                if getattr(connector, 'enabled', False):
                                    self.platform_manager.send(platform_name, "local_user", response["content"])

                        if response["tool_calls"]:
                            for tc in response["tool_calls"]:
                                tool_name = tc.get("function", {}).get("name")
                                tool_args = tc.get("function", {}).get("arguments", {})
                                logging.info(f"Heartbeat requested tool: {tool_name} with {tool_args}")
                                tool_result = self.skill_manager.execute_tool(tool_name, tool_args)

                                sys_prompt_pass2 = "You executed a proactive tool. If the user needs to know this result immediately, generate a message. Otherwise remain silent."
                                final_res = self.router.generate(f"Tool Result: {tool_result}", system_prompt=sys_prompt_pass2, context=self.memory.get_short_term_context())

                                if final_res["content"] and final_res["content"].strip():
                                    self.memory.add_short_term("assistant", final_res["content"])
                                    for platform_name, connector in self.platform_manager.connectors.items():
                                        if getattr(connector, 'enabled', False):
                                            self.platform_manager.send(platform_name, "local_user", final_res["content"])
                                    
                    except Exception as e:
                        logging.error(f"Heartbeat proactive loop error: {e}")
                
        t = threading.Thread(target=loop, daemon=True)
        t.start()
