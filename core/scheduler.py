import time
import threading
import logging
from datetime import datetime
from core.memory import AgentMemory
from core.personality import PersonalityProfile
from skills.manager import SkillManager
from core.models import LLMRouter

class TaskScheduler:
    def __init__(self, agent_instance):
        self.agent = agent_instance
        self.running = False
        self.tasks = [] # Dict schema: {'interval_seconds': int, 'last_run': float, 'instruction': str, 'next_run': float}
        self.lock = threading.Lock()
        
    def add_cron_task(self, instruction_text, interval_seconds):
        logging.info(f"Adding scheduled task: '{instruction_text}' every {interval_seconds}s")
        with self.lock:
            self.tasks.append({
                "instruction": instruction_text,
                "interval": interval_seconds,
                "last_run": 0.0,
                "next_run": time.time() + interval_seconds
            })
            
    def _run_scheduled_inference(self, task):
        logging.info(f"Cron execution triggering: {task['instruction']}")
        try:
            # We treat the cron execution as a 'system' event for the prompt but with standard tool schemas
            msg = f"[CRON SCHEDULED EVENT]: It is time to execute your scheduled task: {task['instruction']}"
            
            # Reconstruct the tool-equipped prompt string but heavily instruct the LLM to output proactively
            sys_prompt = self.agent.personality.construct_system_prompt()
            sys_prompt += "\n\nYou are currently waking up from a scheduled Cron daemon. Perform the requested task immediately using your tools if needed. If you find a result that the user should know, summarize it in a clean alert."
            
            context = self.agent.memory.get_short_term_context()
            tools = self.agent.skill_manager.get_all_tools()
            
            # Send to model
            response = self.agent.router.generate(msg, system_prompt=sys_prompt, context=context, tools=tools)
            
            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    tool_name = tc.get("function", {}).get("name")
                    tool_args = tc.get("function", {}).get("arguments", {})
                    logging.info(f"Cron requested tool: {tool_name} with {tool_args}")
                    
                    tool_result = self.agent.skill_manager.execute_tool(tool_name, tool_args)
                    
                    # Post-process tool result to summarize logic
                    eval_prompt = f"You ran a cron task tool ({tool_name}) and received: {tool_result}. Output a quick conversational update for the user. Do NOT output JSON tool payloads."
                    final = self.agent.router.generate("Summarize Cron Tool Result", system_prompt=eval_prompt, context=self.agent.memory.get_short_term_context())
                    
                    if final.get("content"):
                        self.agent.memory.add_short_term("assistant", f"[CRON] {final['content']}")
                        self.agent.platform_manager.send("cli", "local_user", f"⏰ Cron Alert: {final['content']}")
                        
            elif response.get("content"):
                self.agent.memory.add_short_term("assistant", f"[CRON] {response['content']}")
                self.agent.platform_manager.send("cli", "local_user", f"⏰ Cron Alert: {response['content']}")
                
        except Exception as e:
            logging.error(f"Failed to execute cron task {task['instruction']}: {e}")

    def start(self):
        if self.running:
            return
            
        self.running = True
        logging.info("Starting ViClaw Time/Cron Scheduler...")
        
        def _loop():
            while self.running:
                time.sleep(10) # check every 10 seconds to save CPU cycles
                
                now = time.time()
                tasks_to_run = []
                
                with self.lock:
                    for t in self.tasks:
                        if now >= t["next_run"]:
                            tasks_to_run.append(t)
                            t["last_run"] = now
                            t["next_run"] = now + t["interval"]
                            
                for t in tasks_to_run:
                    # Spawn a detached thread so heavy inference doesn't block other crons
                    threading.Thread(target=self._run_scheduled_inference, args=(t,), daemon=True).start()
                    
        threading.Thread(target=_loop, daemon=True).start()
