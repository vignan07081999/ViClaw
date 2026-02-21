import os
import subprocess
import logging
import json

CONFIG_FILE = "data/config.json"

class UpdaterEngine:
    def __init__(self):
        self.repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config = self._load_config()
        self.repo_url = self.config.get("updater", {}).get("repo_url", "https://github.com/vignan07081999/ViClaw.git")
        self.auto_update = self.config.get("updater", {}).get("auto_update", False)
        
    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Updater could not load config: {e}")
        return {}

    def is_git_repo(self):
        """Validates if the current directory is a valid git repository."""
        return os.path.isdir(os.path.join(self.repo_dir, ".git"))

    def check_for_updates(self):
        """
        Fetches the remote origin and compares the local HEAD to the remote main branch.
        Returns (has_update, local_hash, remote_hash, commit_message).
        """
        if not self.is_git_repo():
            return False, None, None, "Not a Git repository."

        try:
            # Fetch latest remote references
            subprocess.run(["git", "fetch", "origin", "main"], cwd=self.repo_dir, check=True, capture_output=True)
            
            # Get local hash
            local_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            local_hash = local_proc.stdout.strip()
            
            # Get remote hash
            remote_proc = subprocess.run(["git", "rev-parse", "origin/main"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            remote_hash = remote_proc.stdout.strip()
            
            if local_hash != remote_hash:
                # Get the latest commit message
                log_proc = subprocess.run(["git", "log", "-1", "--pretty=format:%s", "origin/main"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
                msg = log_proc.stdout.strip()
                return True, local_hash[:7], remote_hash[:7], msg
            else:
                return False, local_hash[:7], remote_hash[:7], "Up to date."
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Git check failed: {e.stderr}")
            return False, None, None, f"Git error: {e.stderr}"
        except Exception as e:
            logging.error(f"Updater check failed: {e}")
            return False, None, None, str(e)

    def trigger_pull(self):
        """
        Safely executes a git pull. 
        It deliberately avoids overwriting tracking of the `data/` folder and dynamically restarts the daemon.
        """
        if not self.is_git_repo():
            return False, "Not a Git repository."

        try:
            # Stash any local modifications outside of data/ (which should be gitignored anyway)
            subprocess.run(["git", "stash"], cwd=self.repo_dir, capture_output=True)
            
            # Pull latest changes
            pull_proc = subprocess.run(["git", "pull", "origin", "main"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            
            # Pop stash if necessary (we ignore errors if stash was empty)
            subprocess.run(["git", "stash", "pop"], cwd=self.repo_dir, capture_output=True)
            
            # Execute dependencies update if requirements.txt changed
            if "requirements.txt" in pull_proc.stdout:
                if os.path.exists(os.path.join(self.repo_dir, ".venv")):
                    subprocess.run([".venv/bin/pip", "install", "-r", "requirements.txt"], cwd=self.repo_dir)
            
            return True, "Update applied successfully."
        except subprocess.CalledProcessError as e:
            logging.error(f"Git pull failed: {e.stderr}")
            return False, f"Git pull failed: {e.stderr}"
        except Exception as e:
            logging.error(f"Updater pull failed: {e}")
            return False, str(e)
