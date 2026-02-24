#!/usr/bin/env python3
# ViClaw Entry Point v31.5 (Zero-Auth Overhaul)
import os
import sys

def main():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    venv_python = os.path.join(dir_path, ".venv", "bin", "python3")
    
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment not found at {venv_python}")
        print("Please run ./install.sh first to build the environment.")
        sys.exit(1)
        
    cmd = "viclaw"
    args = []
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h", "help"]:
            print("ViClaw CLI Wrapper")
            print("\nUsage:")
            print("  viclaw chat          - Interactive chat with the agent")
            print("  viclaw acp           - Start the NDJSON IDE bridge in stdio")
            print("  viclaw diagnostics   - Check system status and logs")
            print("  viclaw doctor        - Automated troubleshooting")
            print("  viclaw usage         - Show token usage stats")
            print("  viclaw usage --clear - Wipe usage history")
            print("  viclaw main          - Run the core agent loop")
            print("  viclaw launcher      - Open the cross-platform GUI")
            print("\nGlobal command: viclaw [subcommand] [args...]")
            sys.exit(0)
        cmd = sys.argv[1]
        args = sys.argv[2:]
        
    script_map = {
        "chat": "cli/chat.py",
        "acp": "cli/acp.py",
        "diagnostics": "cli/diagnostics.py",
        "doctor": "cli/doctor.py",
        "usage": "cli/usage_cmd.py",
        "main": "main.py",
        "launcher": "launcher.py",
        "viclaw": "viclaw.py"
    }
    
    target_script = script_map.get(cmd)
    
    # Intercept --help passed to any subcommand
    if "--help" in args or "-h" in args:
        print(f"ViClaw CLI Wrapper — Help for '{cmd}'")
        if cmd == "chat":
            print("Usage: viclaw chat")
            print("Starts an interactive terminal chat session with the ViClaw agent.")
        elif cmd == "acp":
            print("Usage: viclaw acp")
            print("Starts the NDJSON standard I/O bridge for IDE integration (e.g. Cursor, Zed).")
        elif cmd == "diagnostics":
            print("Usage: viclaw diagnostics")
            print("Runs a system health check of CPU, memory, database, and Ollama registry.")
        elif cmd == "doctor":
            print("Usage: viclaw doctor")
            print("Runs automated self-healing diagnostics to fix missing folders or dependencies.")
        elif cmd == "usage":
            print("Usage: viclaw usage [--clear]")
            print("Shows token usage telemetry. Use --clear to wipe the history.")
        elif cmd == "main":
            print("Usage: viclaw main")
            print("Starts the core headless background daemon manually.")
        elif cmd == "launcher":
            print("Usage: viclaw launcher [start|stop|restart]")
            print("Manages the daemon lifecycle and opens the cross-platform GUI launcher.")
        else:
            print(f"No specific help available for '{cmd}'.")
        sys.exit(0)
    
    if not target_script:
        # Fallback to viclaw.py if the command is unrecognizable (like an argument)
        target_script = "viclaw.py"
        args = [cmd] + args
        
    target_path = os.path.join(dir_path, target_script)
    
    if not os.path.exists(target_path):
        print(f"Error: Target script {target_path} does not exist.")
        sys.exit(1)
        
    os.execv(venv_python, [venv_python, target_path] + args)

if __name__ == "__main__":
    main()
