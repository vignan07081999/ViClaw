import os
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def main():
    while True:
        console.clear()
        console.print(Panel.fit("[bold magenta]ViClaw Super Menu[/bold magenta]", border_style="magenta"))
        console.print("[1] 💬 Interactive CLI Chat")
        console.print("[2] 🚀 Start/Restart Background Daemon (Enables WebUI)")
        console.print("[3] 🛑 Stop Background Daemon")
        console.print("[4] 📊 System Diagnostics & Health")
        console.print("[5] 🩺 Agent Doctor (Troubleshoot & Fix)")
        console.print("[6] ⚙️  Update Configuration")
        console.print("[7] 🔄 Reinstall ViClaw")
        console.print("[8] 🗑️  Uninstall ViClaw")
        console.print("[0] 🚪 Exit")
        
        choice = Prompt.ask("\nSelect an option", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="1")
        
        if choice == "0":
            break
        elif choice == "1":
            subprocess.run(["python", "cli/chat.py"])
        elif choice == "2":
            subprocess.run(["python", "launcher.py", "restart"])
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "3":
            subprocess.run(["python", "launcher.py", "stop"])
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "4":
            subprocess.run(["python", "cli/diagnostics.py"])
        elif choice == "5":
            subprocess.run(["python", "cli/doctor.py"])
        elif choice == "6":
            subprocess.run(["bash", "scripts/update_config.sh"])
        elif choice == "7":
            subprocess.run(["bash", "scripts/reinstall.sh"])
        elif choice == "8":
            subprocess.run(["bash", "scripts/uninstall.sh"])
            if not os.path.exists("data/config.json"):
                break

if __name__ == "__main__":
    main()
