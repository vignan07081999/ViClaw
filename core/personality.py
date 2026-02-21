from datetime import datetime

class PersonalityProfile:
    def __init__(self, memory_module):
        self.memory = memory_module
        
        # Default OpenClaw archetype
        self.base_instructions = (
            "You are OpenClaw, an autonomous, proactive AI agent running locally on the user's "
            "machine. You are highly capable, direct, and concise. Your goal is to help the user "
            "achieve their tasks quickly by running tools, searching for information, and managing "
            "their environment safely."
        )

    def construct_system_prompt(self, current_query=None):
        """
        Assembles the system prompt including base traits, current temporal facts,
        and injected semantic memories based on the current query.
        """
        prompt = self.base_instructions + "\n\n"
        
        # Inject Temporal Facts
        current_time = datetime.now()
        prompt += f"System Time: {current_time.isoformat()}\n"
        prompt += f"Operating System: Linux/Unix\n\n"

        # Inject Long-Term Memories relevant to the query
        if current_query:
            relevant_memories = self.memory.search_long_term(current_query)
            if relevant_memories:
                prompt += "Relevant Historical Context from Long-Term Memory:\n"
                for mem in relevant_memories:
                    prompt += f"- {mem}\n"
                prompt += "\n"

        prompt += (
            "Instructions:\n"
            "- Always act autonomously when possible using your available tools.\n"
            "- If a task needs multiple steps, perform the first logical step immediately.\n"
            "- If you learn a new preference or important fact about the user, use the `save_memory` tool to remember it.\n"
            "- Be concise. Your output goes directly to messaging platforms (Telegram/CLI).\n"
        )
        
        return prompt
