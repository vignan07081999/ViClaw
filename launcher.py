import os
import sys
import subprocess
import time
import signal
from rich.console import Console
from rich import print as rprint

console = Console()

PID_FILE = "data/viclaw.pid"
LOG_FILE = "data/viclaw.log"

def is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def start_daemon():
    os.makedirs("data", exist_ok=True)
    
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
        if is_running(old_pid):
            console.print(f"[bold yellow]ViClaw Daemon is already running (PID {old_pid}).[/bold yellow]")
            return
        else:
            # Stale PID file
            os.remove(PID_FILE)

    console.print("[cyan]Starting ViClaw background daemon...[/cyan]")
    
    # Open log file to redirect stdout/stderr
    with open(LOG_FILE, "a") as log:
        # Cross-platform background process launch
        if sys.platform == "win32":
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            proc = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=log,
                stderr=log,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=log,
                stderr=log,
                preexec_fn=os.setpgrp
            )

    # Save PID so we can stop it later
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))

    time.sleep(1) # Give it a second to fail
    if proc.poll() is None:
        console.print(f"[bold green]✓ Daemon successfully started (PID {proc.pid}).[/bold green]")
        console.print(f"Logs are being written to [yellow]{LOG_FILE}[/yellow]")
    else:
        console.print("[bold red]✗ Failed to start daemon. Check the logs.[/bold red]")

def stop_daemon():
    if not os.path.exists(PID_FILE):
        console.print("[yellow]Daemon config not found. Is it running?[/yellow]")
        return
        
    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())
        
    if not is_running(pid):
        console.print("[yellow]Daemon is not running (stale PID). Cleaning up.[/yellow]")
        os.remove(PID_FILE)
        return
        
    console.print(f"[cyan]Stopping daemon (PID {pid})...[/cyan]")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)])
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            
        time.sleep(2)
        if is_running(pid):
            if sys.platform != "win32":
                os.killpg(os.getpgid(pid), signal.SIGKILL)
                
        console.print("[bold green]✓ Daemon stopped.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to stop daemon: {e}[/bold red]")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

def status_daemon():
    if not os.path.exists(PID_FILE):
        console.print("[bold red]Daemon is OFFLINE.[/bold red]")
        return False
        
    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())
        
    if is_running(pid):
        console.print(f"[bold green]Daemon is ONLINE and active (PID {pid}).[/bold green]")
        return True
    else:
        console.print("[bold red]Daemon is OFFLINE (Crashed).[/bold red]")
        os.remove(PID_FILE)
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ViClaw cross-platform background daemon launcher.")
    parser.add_argument("action", choices=["start", "stop", "status", "restart"], help="Action to perform.")
    args = parser.parse_args()
    
    if args.action == "start":
        start_daemon()
    elif args.action == "stop":
        stop_daemon()
    elif args.action == "status":
        status_daemon()
    elif args.action == "restart":
        stop_daemon()
        time.sleep(1)
        start_daemon()
