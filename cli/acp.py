import sys
import json
import logging
import asyncio

# Disable standard logging to stdout so we don't pollute the NDJSON stream
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

from core.agent import ViClawAgent

def main():
    agent = ViClawAgent(platform_manager=None) # No chat platforms needed for ACP
    
    # We write an init exact format that some IDEs might expect or just a welcome
    sys.stdout.write(json.dumps({"type": "status", "status": "ACP Bridge Ready"}) + "\\n")
    sys.stdout.flush()

    for line in sys.stdin:
        if not line.strip():
            continue
            
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"error": "Invalid JSON"}) + "\\n")
            sys.stdout.flush()
            continue

        req_type = req.get("type", "chat")
        
        if req_type == "ping":
            sys.stdout.write(json.dumps({"type": "pong"}) + "\\n")
            sys.stdout.flush()
            continue
            
        if req_type == "chat":
            message = req.get("message", "")
            user_id = req.get("user_id", "ide_user")
            
            # Use synchronous processing for simplicity in this bridge
            try:
                # Add to memory
                agent.memory.add_short_term(user_id, message)
                
                # Build MCP schema correctly
                context = agent.memory.get_short_term_context()
                sys_prompt = agent.personality.construct_system_prompt(current_query=message) # Assuming 'message' is the current query
                
                response = agent.router.generate(message, system_prompt=sys_prompt, context=context)
                reply = response.get("content", "")
                
                agent.memory.add_short_term("assistant", reply)
                
                res = {
                    "type": "response",
                    "content": reply,
                    "usage": response.get("usage", {})
                }
                sys.stdout.write(json.dumps(res) + "\\n")
                sys.stdout.flush()
            except Exception as e:
                sys.stdout.write(json.dumps({"error": str(e)}) + "\\n")
                sys.stdout.flush()

if __name__ == "__main__":
    main()
