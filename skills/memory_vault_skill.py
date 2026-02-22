import logging

def get_tool_schema():
    return {
        "type": "function",
        "function": {
            "name": "store_long_term_memory",
            "description": "Permanently stores a fact, document, or user preference into the RAG Vector Vault. Use this when the user asks you to 'remember' something or when you learn an important persistent fact about the user or system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The information to permanently memorize."
                    },
                    "topic": {
                        "type": "string",
                        "description": "A short 1-2 word topic categorization for this memory (e.g., 'preferences', 'work', 'project_x')."
                    },
                    "importance": {
                        "type": "integer",
                        "description": "A score from 1-10 on how critical this information is to remember. User preferences are usually 10. Random facts are 1-3."
                    }
                },
                "required": ["content", "topic", "importance"]
            }
        }
    }

def execute(args):
    content = args.get("content")
    topic = args.get("topic")
    importance = args.get("importance")
    
    if not content or not topic or not importance:
        return "Failed: Missing required parameters."
        
    try:
        from webui.app import agent_instance
        if not agent_instance or not hasattr(agent_instance, 'memory'):
            return "Failed: Global Memory context is offline."
            
        agent_instance.memory.add_long_term(content, topic=topic, importance=importance)
        return f"Successfully embedded and saved to Long-Term Memory Vault under topic '{topic}'."
        
    except Exception as e:
        logging.error(f"Memory Vault Skill Error: {e}")
        return f"Failed to store memory: {e}"
