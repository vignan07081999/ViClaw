import logging
from skills.manager import AgentSkill

class SessionsSkill(AgentSkill):
    name = "sessions"
    description = "Delegate complex sub-tasks to a parallel Agent LLM session. Use this to break down large problems into smaller chunks without clogging your own memory."
    
    def get_tool_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "sessions_send",
                "description": "Send a task and context to a new parallel sub-agent session. Use this to offload complex research or coding logic that can be isolated.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "The exact instruction or task for the sub-agent."
                        },
                        "context_payload": {
                            "type": "string",
                            "description": "Any data, text, or context the sub-agent needs to complete the task."
                        }
                    },
                    "required": ["task_description"]
                }
            }
        }

    def sessions_send(self, task_description: str, context_payload: str = "") -> str:
        try:
            from core.models import LLMRouter
            import copy
            
            router = LLMRouter()
            
            # Sub-agent takes the complex fallback route assuming it was delegated because it's hard
            router.default_model = router.complex_model["model"]
            
            sys_prompt = "You are a sub-agent spawned by the main ViClaw core. Focus entirely on the isolated task you have been given and return only a final report or solution back to the prime intelligence."
            
            prompt = task_description
            if context_payload:
                prompt += f"\n\nContext payload:\n{context_payload}"
                
            logging.info(f"[Sessions] Delegating task to sub-agent: {task_description[:50]}...")
            
            # Exclude tools so it doesn't get distracted by MCP operations
            response = router.generate(prompt, system_prompt=sys_prompt, context=None, tools=[])
            
            res_content = response.get("content", "").strip()
            
            if not res_content:
                return "The sub-agent returned an empty response."
                
            return f"Sub-Agent Report:\n{res_content}"
            
        except Exception as e:
            return f"Sub-agent session failed: {str(e)}"
