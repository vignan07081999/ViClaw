"""
skills/clawhub_client.py — Native ClawHub Marketplace Client

ClawHub is a fast skill registry for AI agents at https://clawhub.ai
This client interacts with the official ClawHub API to search, fetch,
download, install, and hot-load skills directly into the ViClaw runtime.

API Base: https://wry-manatee-359.convex.site/api/v1
  GET /skills             — List all skills (paginated, nextCursor)
  GET /search?q=<query>   — Vector search for skills
  GET /download?slug=<s>  — Download skill zip
"""

import os
import io
import re
import json
import logging
import requests
import zipfile

SKILLS_DIR = os.path.dirname(__file__)

CLAWHUB_API_BASE = "https://wry-manatee-359.convex.site/api/v1"
CLAWHUB_SITE_BASE = "https://clawhub.ai"


class ClawHubClient:
    """
    Native client for the ClawHub skill marketplace at clawhub.ai.
    Handles search, browse, download, install, and hot-load of agent skills.
    """

    def __init__(self):
        self.api_base = CLAWHUB_API_BASE
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ViClaw/31.6 (github.com/vignan07081999/ViClaw)"
        })

    # ─────────────────────────────────────────────
    # SEARCH & BROWSE
    # ─────────────────────────────────────────────

    def search(self, query: str) -> list:
        """
        Vector-search ClawHub for skills matching the query.
        Returns a list of skill dicts: slug, displayName, summary, version, score.
        """
        try:
            res = self.session.get(f"{self.api_base}/search", params={"q": query}, timeout=10)
            res.raise_for_status()
            return res.json().get("results", [])
        except Exception as e:
            logging.error(f"[ClawHub] Search failed for '{query}': {e}")
            return []

    def list_skills(self, cursor: str = None, limit: int = 20) -> dict:
        """
        List skills from ClawHub with pagination.
        Returns {"items": [...], "nextCursor": "..."}
        """
        try:
            params = {}
            if cursor:
                params["cursor"] = cursor
            if limit:
                params["limit"] = limit
            res = self.session.get(f"{self.api_base}/skills", params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            return {
                "items": data.get("items", []),
                "nextCursor": data.get("nextCursor")
            }
        except Exception as e:
            logging.error(f"[ClawHub] List skills failed: {e}")
            return {"items": [], "nextCursor": None}

    def get_skill_info(self, slug: str) -> dict:
        """
        Fetch detailed info for a single skill by slug.
        Returns the skill dict or None if not found.
        """
        # Search for the specific slug to get its details
        results = self.search(slug)
        for r in results:
            if r.get("slug") == slug:
                return r
        # Fallback: list and find
        page = self.list_skills()
        for item in page.get("items", []):
            if item.get("slug") == slug:
                return item
        return None

    # ─────────────────────────────────────────────
    # DOWNLOAD & INSTALL
    # ─────────────────────────────────────────────

    def download_skill_zip(self, slug: str) -> bytes:
        """
        Download the zip archive for a given skill slug.
        Returns raw zip bytes or None on failure.
        """
        try:
            url = f"{self.api_base}/download"
            logging.info(f"[ClawHub] Downloading skill '{slug}' from {url}")
            res = self.session.get(url, params={"slug": slug}, timeout=30)
            res.raise_for_status()
            return res.content
        except Exception as e:
            logging.error(f"[ClawHub] Download failed for slug '{slug}': {e}")
            return None

    def install_skill(self, slug: str) -> dict:
        """
        Full install pipeline for a ClawHub skill:
        1. Download zip from ClawHub
        2. Extract skill files into skills/ directory
        3. Return {"success": bool, "message": str, "installed_files": [...]}
        """
        logging.info(f"[ClawHub] Starting install for: {slug}")
        zip_bytes = self.download_skill_zip(slug)

        if not zip_bytes:
            return {"success": False, "message": f"Failed to download '{slug}'. Check your connection."}

        installed_files = []
        skill_dir = None

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                file_list = zf.namelist()
                logging.info(f"[ClawHub] Archive contents: {file_list}")

                # Detect if there's a top-level folder wrapper
                first = file_list[0] if file_list else ""
                prefix = first.split("/")[0] if "/" in first else ""

                # Create a skill sub-directory inside skills/
                safe_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
                skill_dir = os.path.join(SKILLS_DIR, safe_slug)
                os.makedirs(skill_dir, exist_ok=True)

                for item in file_list:
                    # Strip top-level folder wrapper if present
                    target_name = item[len(prefix) + 1:] if prefix and item.startswith(prefix + "/") else item

                    if not target_name or target_name.endswith("/"):
                        continue  # Skip directories

                    target_path = os.path.join(skill_dir, target_name)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)

                    with zf.open(item) as src, open(target_path, "wb") as dst:
                        dst.write(src.read())
                    installed_files.append(target_path)

        except zipfile.BadZipFile:
            # Some skills are single .py or .md files, not zips
            # Try to treat the content as a Python file
            try:
                content = zip_bytes.decode("utf-8")
                safe_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
                # Detect class name for file naming
                match = re.search(r"class\s+([A-Za-z0-9_]+)", content)
                file_name = (match.group(1).lower() + ".py") if match else (safe_slug + ".py")
                target_path = os.path.join(SKILLS_DIR, file_name)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                installed_files.append(target_path)
            except Exception as e:
                return {"success": False, "message": f"Invalid archive for '{slug}': {e}"}
        except Exception as e:
            return {"success": False, "message": f"Extraction failed for '{slug}': {e}"}

        # Write a metadata marker so we can track installed ClawHub skills
        if skill_dir:
            meta = {
                "slug": slug,
                "source": "clawhub.ai",
                "installed_files": [os.path.relpath(f, SKILLS_DIR) for f in installed_files]
            }
            with open(os.path.join(skill_dir, ".clawhub_meta.json"), "w") as f:
                json.dump(meta, f, indent=2)

        logging.info(f"[ClawHub] Install complete for '{slug}'. Files: {installed_files}")
        return {
            "success": True,
            "message": f"Skill '{slug}' installed successfully ({len(installed_files)} files).",
            "installed_files": installed_files,
            "skill_dir": skill_dir
        }

    def download_and_install(self, url_or_slug: str) -> bool:
        """
        Legacy compatibility shim: accepts either a URL (for backward compat)
        or a slug and routes to the correct install path.
        """
        # If it looks like a GitHub raw URL, install directly
        if url_or_slug.startswith("http") and "github" in url_or_slug:
            try:
                if "github.com" in url_or_slug and "/blob/" in url_or_slug:
                    url_or_slug = url_or_slug.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                response = requests.get(url_or_slug, timeout=15)
                if response.status_code == 200:
                    content = response.text
                    file_name = url_or_slug.split("/")[-1]
                    if not file_name.endswith(".py"):
                        match = re.search(r"class\s+([A-Za-z0-9_]+)", content)
                        file_name = (match.group(1).lower() + ".py") if match else "custom_skill.py"
                    target_path = os.path.join(SKILLS_DIR, file_name)
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logging.info(f"[ClawHub] Installed from URL: {target_path}")
                    return True
                logging.error(f"[ClawHub] URL returned {response.status_code}")
                return False
            except Exception as e:
                logging.error(f"[ClawHub] URL install failed: {e}")
                return False

        # Otherwise treat as a ClawHub slug
        result = self.install_skill(url_or_slug)
        return result.get("success", False)

    # ─────────────────────────────────────────────
    # INSTALLED SKILL TRACKER
    # ─────────────────────────────────────────────

    def get_installed_clawhub_skills(self) -> list:
        """
        Returns a list of installed ClawHub skills by scanning for .clawhub_meta.json files.
        """
        installed = []
        for item in os.listdir(SKILLS_DIR):
            meta_path = os.path.join(SKILLS_DIR, item, ".clawhub_meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        installed.append(json.load(f))
                except Exception:
                    pass
        return installed

    def uninstall_skill(self, slug: str) -> dict:
        """Remove an installed ClawHub skill by slug."""
        import shutil
        safe_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
        skill_dir = os.path.join(SKILLS_DIR, safe_slug)
        if os.path.isdir(skill_dir):
            shutil.rmtree(skill_dir)
            return {"success": True, "message": f"Skill '{slug}' uninstalled."}
        return {"success": False, "message": f"Skill '{slug}' not found in installed directory."}

    # ─────────────────────────────────────────────
    # DEFAULT SKILLS BOOTSTRAP (keeps backward compat)
    # ─────────────────────────────────────────────

    def install_default_skills(self):
        """
        Bootstrap default skills inline for initial install.
        (Preserves backward compatibility with existing startup code.)
        """
        logging.info("[ClawHub] Installing default bundled skills...")
        system_skill_path = os.path.join(SKILLS_DIR, "system_info.py")
        if not os.path.exists(system_skill_path):
            with open(system_skill_path, "w") as f:
                f.write('''
from skills.manager import BaseSkill
import os
import platform

class SystemInfoSkill(BaseSkill):
    name = "SystemInfo"
    description = "Provides information about the host system."

    def get_tools(self):
        return [{
            "type": "function",
            "function": {
                "name": "get_system_info",
                "description": "Returns basic OS platform info for context",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }]

    def get_system_info(self, **kwargs):
        return f"OS: {platform.system()} {platform.release()}, Arch: {platform.machine()}"
''')
        logging.info("[ClawHub] Default skills installed successfully.")
