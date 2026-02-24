#!/usr/bin/env python3
"""
cli/usage.py — viclaw usage command (Feature 6)

Usage:
  viclaw usage              Show usage stats for this session and all-time
  viclaw usage --clear      Wipe all usage history
  viclaw usage --json       Output raw JSON stats
"""
import sys
import os

# Ensure project root is on the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(root_dir, ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

sys.path.insert(0, root_dir)

from rich.console import Console

console = Console()

def main():
    args = sys.argv[1:]

    from core.usage import UsageTracker
    tracker = UsageTracker.instance()

    if "--clear" in args:
        if input("Clear all usage history? (y/N) ").strip().lower() == "y":
            tracker.clear_history()
            console.print("[green]✓ Usage history cleared.[/green]")
        else:
            console.print("[dim]Cancelled.[/dim]")
        return

    if "--json" in args:
        import json
        print(json.dumps(tracker.get_stats(), indent=2))
        return

    # Default: pretty report
    report = tracker.format_report()
    console.print(report)

if __name__ == "__main__":
    main()
