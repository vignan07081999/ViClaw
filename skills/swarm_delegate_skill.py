import logging
import json

def get_tool_schema():
    return {
        "type": "function",
        "function": {
            "name": "delegate_to_swarm",
            "description": "Spawns a highly specialized child sub-agent and delegates a specific sub-task to it. Use this when a task is extremely complex, requires a focused persona, or when you need parallel processing. Do not loop back to this tool until the child agent returns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "A unique, descriptive name for the sub-agent (e.g., 'PythonCoder01', 'WebScraperBot')."
                    },
                    "role": {
                        "type": "string",
                        "description": "The specific persona, role, or title of the sub-agent (e.g., 'Senior Systems Engineer', 'Data Analyst')."
                    },
                    "instruction": {
                        "type": "string",
                        "description": "The custom system prompt that defines EXACTLY what the sub-agent should do. Be extremely detailed."
                    },
                    "task": {
                        "type": "string",
                        "description": "The specific task or prompt to pass to the agent to start its reasoning loop."
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "An optional list of EXACT tool names (e.g., ['python_interpreter', 'file_reader']) to give this sub-agent access to. Limit access to only what it strictly needs."
                    }
                },
                "required": ["agent_name", "role", "instruction", "task"]
            }
        }
    }

def execute(args):
    agent_name = args.get("agent_name")
    role = args.get("role")
    instruction = args.get("instruction")
    task = args.get("task")
    tools = args.get("tools", [])
    
    if not agent_name or not instruction or not task:
        return "Failed: Missing required agent generation logic."
        
    try:
        from webui.app import agent_instance
        if not agent_instance or not hasattr(agent_instance, 'swarm'):
            return "Failed: Global Swarm Orchestrator is offline. You must process this task natively."
            
        orchestrator = agent_instance.swarm
        
        # Instantiate agent if it doesn't exist
        if agent_name not in orchestrator.active_agents:
            orchestrator.spawn_agent(agent_name, role, instruction, tools)
            
        logging.info(f"Delegating task to Swarm Agent: {agent_name}")
        
        # In this synchronous architecture, we wait for the child agent inference to complete natively.
        # It blocks the parent thread while it computes.
        result = orchestrator.delegate(agent_name, task)
        
        return f"[SWARM CHILD ({agent_name}) RESULT]:\n{result}"
        
    except Exception as e:
        logging.error(f"Swarm Delegation Error: {e}")
        return f"Failed to delegate to swarm: {e}"
