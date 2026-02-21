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
        console.print("[2] 📊 System Diagnostics & Health")
        console.print("[3] 🩺 Agent Doctor (Troubleshoot & Fix)")
        console.print("[4] ⚙️  Update Configuration")
        console.print("[5] 🔄 Reinstall ViClaw")
        console.print("[6] 🗑️  Uninstall ViClaw")
        console.print("[0] 🚪 Exit")
        
        choice = Prompt.ask("\nSelect an option", choices=["0", "1", "2", "3", "4", "5", "6"], default="1")
        
        if choice == "0":
            break
        elif choice == "1":
            subprocess.run(["python", "chat.py"])
        elif choice == "2":
            subprocess.run(["python", "diagnostics.py"])
        elif choice == "3":
            subprocess.run(["python", "doctor.py"])
        elif choice == "4":
            subprocess.run(["bash", "scripts/update_config.sh"])
        elif choice == "5":
            subprocess.run(["bash", "scripts/reinstall.sh"])
        elif choice == "6":
            subprocess.run(["bash", "scripts/uninstall.sh"])
            if not os.path.exists("data/config.json"):
                break

if __name__ == "__main__":
    main()
