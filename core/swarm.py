import logging
from core.models import LLMRouter

class SwarmAgent:
    def __init__(self, name, role, instruction, tools=None):
        self.name = name
        self.role = role
        self.instruction = instruction
        self.tools = tools or []
        self.router = LLMRouter()
        self.history = []

    def execute_task(self, task_description, context=None):
        logging.info(f"[SWARM] {self.name} ({self.role}) is starting task: {task_description[:50]}...")
        
        system_prompt = f"You are a specialized Swarm Agent named {self.name}. Your role is: {self.role}.\n\nCORE INSTRUCTION:\n{self.instruction}\n\n"
        
        if self.tools:
            system_prompt += "You have access to the following tools via XML execution:\n"
            import json
            for t in self.tools:
                system_prompt += f"- {t['function']['name']}: {t['function'].get('description', '')}\n  Schema: {json.dumps(t['function'].get('parameters', {}))}\n"
                
        system_prompt += "\nRespond systematically and thoroughly. When you have completed your task or encountered an unsolvable error, output a final summary for the orchestrator."
        
        # In a full recursive swarm, we would map the child agent to the skill manager here.
        # For MVP, the child agent purely reasons and outputs a plan/code block back to the main agent.
        messages = context or []
        
        try:
            response = self.router.generate(task_description, system_prompt=system_prompt, context=messages)
            result = response.get("content", "Agent failed to generate a response.")
            self.history.append({"task": task_description, "result": result})
            return result
        except Exception as e:
            logging.error(f"[SWARM] {self.name} failed: {e}")
            return f"Error executing sub-task: {e}"

class SwarmOrchestrator:
    def __init__(self, parent_agent):
        self.parent = parent_agent
        self.active_agents = {}
        
    def spawn_agent(self, name, role, instruction, tools_list=None):
        """
        Creates a specialized sub-agent.
        """
        # Filter available tools based on requested list
        assigned_tools = []
        if tools_list:
            all_hooks = self.parent.skill_manager.get_all_tools()
            for h in all_hooks:
                if h["function"]["name"] in tools_list:
                    assigned_tools.append(h)
                    
        agent = SwarmAgent(name, role, instruction, assigned_tools)
        self.active_agents[name] = agent
        logging.info(f"[SWARM ORCHESTRATOR] Spawned new agent: {name}")
        return agent
        
    def delegate(self, agent_name, task_text, context=None):
        """
        Passes a task to a specific sub-agent. Sync operation.
        """
        if agent_name not in self.active_agents:
            return f"Error: Agent '{agent_name}' does not exist in the swarm."
            
        agent = self.active_agents[agent_name]
        return agent.execute_task(task_text, context=context)
