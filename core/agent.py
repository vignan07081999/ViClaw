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

    def _process_slash_command(self, command_text):
        cmd = command_text.strip().lower()
        parts = cmd.split()
        base_cmd = parts[0]
        
        if base_cmd in ["/reset", "/new"]:
            self.memory.short_term = []
            return "Session reset. Short-term memory cleared."
        elif base_cmd == "/status":
            num_msgs = len(self.memory.short_term)
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
                        import json
                        tool_args = json.loads(tool_args) if tool_args.strip() else {}
                    except:
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

    def process_immediate_message(self, platform_name, user_id, message_text):
        """
        Processes a message synchronously and returns the string response. 
        Used by the local WebUI and CLI chat script.
        """
        logging.info(f"Sync Request from {platform_name} user {user_id}: {message_text}")
        
        if message_text.strip().startswith("/"):
            return self._process_slash_command(message_text)
            
        self.memory.add_short_term("user", message_text)
        system_prompt = self.personality.construct_system_prompt(current_query=message_text)
        context = self.memory.get_short_term_context()[:-1] 
        tools = self.skill_manager.get_all_tools()
        tools_xml_prompt = "\n\nAVAILABLE TOOLS:\nYou have access to the following tools. To use a tool, you MUST output an XML block like this: <tool name=\"tool_name\">{\"arg_name\": \"arg_value\"}</tool>. Do NOT output any raw JSON outside of the XML block. If you do not need a tool, just answer normally.\nTools available:\n"
        import json
        for t in tools:
            tools_xml_prompt += f"- {t['function']['name']}: {t['function'].get('description', '')}\n  Schema: {json.dumps(t['function'].get('parameters', {}))}\n"
        
        system_prompt += tools_xml_prompt
        
        response = self.router.generate(message_text, system_prompt=system_prompt, context=context)
        
        final_reply = response.get("content", "") or ""
        raw_tools = []
        
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
                        import json
                        tool_args = json.loads(tool_args) if tool_args.strip() else {}
                    except:
                        tool_args = {}
                elif not isinstance(tool_args, dict):
                    tool_args = {}
                    
                try:
                    tool_result = self.skill_manager.execute_tool(tool_name, tool_args)
                    executed_results.append(f"[TOOL EXECUTION RESULT: {tool_name}]\n{tool_result}")
                except Exception as e:
                    err_msg = f"I encountered an error running {tool_name}: {e}"
                    executed_results.append(err_msg)
                    logging.error(e)
            
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
                                import json
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
                            # Spontaneous message
                            self.memory.add_short_term("assistant", response["content"])
                            self.platform_manager.send("cli", "local_user", response["content"])
                            
                        if response["tool_calls"]:
                            for tc in response["tool_calls"]:
                                tool_name = tc.get("function", {}).get("name")
                                tool_args = tc.get("function", {}).get("arguments", {})
                                logging.info(f"Heartbeat requested tool: {tool_name} with {tool_args}")
                                tool_result = self.skill_manager.execute_tool(tool_name, tool_args)
                                
                                # Process tool result proactively
                                sys_prompt_pass2 = "You executed a proactive tool. If the user needs to know this result immediately, generate a message. Otherwise remain silent."
                                final_res = self.router.generate(f"Tool Result: {tool_result}", system_prompt=sys_prompt_pass2, context=self.memory.get_short_term_context())
                                
                                if final_res["content"] and final_res["content"].strip():
                                    self.platform_manager.send("cli", "local_user", final_res["content"])
                                    self.memory.add_short_term("assistant", final_res["content"])
                                    
                    except Exception as e:
                        logging.error(f"Heartbeat proactive loop error: {e}")
                
        t = threading.Thread(target=loop, daemon=True)
        t.start()
