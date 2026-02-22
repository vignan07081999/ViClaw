import logging

# We need a reference to the global agent instance specifically for the scheduler. 
# Skills normally don't have this, but native internal skills can fetch it via the webui's global or a singleton accessor
# To keep this clean and modular, we'll import it from app.py where the daemon mounts it.
# In a real microservice architecture, this would go through an RPC local API.

def get_tool_schema():
    return {
        "type": "function",
        "function": {
            "name": "schedule_cron_task",
            "description": "Registers a recurring background task. Use this when the user asks you to do something periodically (e.g., 'every 5 minutes', 'every hour'). This will trigger a completely new autonomous reasoning loop in the background at the specified interval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "The exact prompt you want your future self to execute. E.g., 'Summarize the latest news from HackerNews' or 'Check if my website is up'."
                    },
                    "interval_seconds": {
                        "type": "integer",
                        "description": "The interval in seconds between executions. E.g., 300 for 5 minutes, 3600 for 1 hour."
                    }
                },
                "required": ["instruction", "interval_seconds"]
            }
        }
    }

def execute(args):
    instruction = args.get("instruction")
    interval = args.get("interval_seconds")
    
    if not instruction or not interval:
        return "Failed: Missing instruction or interval_seconds."
        
    try:
        from webui.app import agent_instance
        if not agent_instance or not hasattr(agent_instance, 'scheduler'):
            return "Failed: Global Scheduler Daemon is offline."
            
        agent_instance.scheduler.add_cron_task(instruction, interval)
        return f"Successfully registered background cron. Instruction: '{instruction}' will execute every {interval} seconds."
        
    except Exception as e:
        logging.error(f"Cron Skill Error: {e}")
        return f"Failed to register native cron: {e}"
