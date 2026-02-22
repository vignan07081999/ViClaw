"""
skills/clawhub_bridge.py — ClawHub SKILL.md Context Bridge

This module bridges the gap between ClawHub's SKILL.md-based skills and
ViClaw's Python-based skill system.

How ClawHub skills work (OpenClaw native):
  - Each skill ships a SKILL.md file that describes what the agent can do
  - The LLM reads SKILL.md content as part of its system prompt
  - The agent follows the instructions in SKILL.md to use shell scripts,
    call APIs, or run any bundled scripts

This bridge:
  1. Scans all installed ClawHub skill directories for SKILL.md files
  2. Aggregates the content into a compact system-prompt block
  3. Returns it for injection into the ViClaw agent's system prompt
  4. Also registers any bundled shell scripts as callable tool-wrappers
"""

import os
import json
import logging

SKILLS_DIR = os.path.dirname(__file__)


def get_installed_skills_context() -> str:
    """
    Scan all ClawHub skill subdirectories for SKILL.md files.
    Returns an aggregated string block ready for system prompt injection.
    Returns an empty string if no SKILL.md-based skills are installed.
    """
    context_blocks = []

    for item in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, item)

        # Only look at directories with a .clawhub_meta.json marker
        meta_path = os.path.join(skill_dir, ".clawhub_meta.json")
        if not os.path.isdir(skill_dir) or not os.path.exists(meta_path):
            continue

        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
        except Exception:
            meta = {}

        slug = meta.get("slug", item)

        # Find SKILL.md (case-insensitive, supports nested locations)
        skill_md_path = _find_skill_md(skill_dir)
        if not skill_md_path:
            logging.debug(f"[ClawHubBridge] No SKILL.md found in '{slug}' — skipping context injection.")
            continue

        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception as e:
            logging.warning(f"[ClawHubBridge] Could not read SKILL.md for '{slug}': {e}")
            continue

        if not content:
            continue

        # Truncate very long SKILL.md files to keep the prompt manageable
        # (~2000 chars per skill = ~500 tokens; most SKILL.md files are well under this)
        MAX_CHARS = 2500
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + f"\n...[truncated — see {skill_dir}/SKILL.md for full details]"

        # Detect if there are runnable scripts bundled with this skill
        scripts_note = _get_scripts_note(skill_dir, slug)

        block = (
            f"--- INSTALLED CLAWHUB SKILL: {slug} ---\n"
            f"{content}"
        )
        if scripts_note:
            block += f"\n\n{scripts_note}"

        context_blocks.append(block)
        logging.info(f"[ClawHubBridge] Injecting SKILL.md context for: {slug}")

    if not context_blocks:
        return ""

    header = (
        "\n\n=== CLAWHUB INSTALLED SKILLS ===\n"
        "The following skills have been installed from clawhub.ai. "
        "Read their descriptions carefully and follow their instructions when relevant.\n\n"
    )
    return header + "\n\n".join(context_blocks) + "\n=== END CLAWHUB SKILLS ==="


def _find_skill_md(skill_dir: str) -> str | None:
    """
    Recursively search for a SKILL.md file in skill_dir.
    Returns the full path to the first match, or None.
    """
    for root, dirs, files in os.walk(skill_dir):
        # Skip hidden dirs and node_modules
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for fname in files:
            if fname.upper() == "SKILL.MD":
                return os.path.join(root, fname)
    return None


def _get_scripts_note(skill_dir: str, slug: str) -> str:
    """
    Look for runnable scripts (.sh, .py, .js, .ts) in the skill directory.
    Returns a short note so the LLM knows they can be executed via the shell.
    """
    script_extensions = {".sh", ".py", ".js", ".ts"}
    # Exclude metadata and __init__ files
    exclude_names = {"__init__.py", "setup.py", "install.sh", "postinstall.js"}

    scripts = []
    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for fname in files:
            if fname in exclude_names:
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in script_extensions:
                rel_path = os.path.relpath(os.path.join(root, fname), SKILLS_DIR)
                scripts.append(rel_path)

    if not scripts:
        return ""

    note = f"Bundled scripts (use shell_execute tool to run these):\n"
    for s in scripts[:8]:  # Cap at 8 to keep prompt tidy
        note += f"  - skills/{s}\n"
    return note.rstrip()


def get_installed_skill_list() -> list:
    """
    Returns a list of dicts for all installed ClawHub skills.
    Used for diagnostics and dashboard reporting.
    """
    installed = []
    for item in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, item)
        meta_path = os.path.join(skill_dir, ".clawhub_meta.json")
        if not os.path.isdir(skill_dir) or not os.path.exists(meta_path):
            continue
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            has_skill_md = _find_skill_md(skill_dir) is not None
            meta["has_skill_md"] = has_skill_md
            meta["skill_dir"] = skill_dir
            installed.append(meta)
        except Exception:
            pass
    return installed
