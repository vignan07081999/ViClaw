import os
import time
import logging
import threading
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DROPZONE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "dropzone")
os.makedirs(DROPZONE_DIR, exist_ok=True)

class AgentFileHandler(FileSystemEventHandler):
    def __init__(self, agent):
        self.agent = agent
        super().__init__()

    def on_created(self, event):
        if event.is_directory:
            return
            
        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        # Give the filesystem a moment to finish writing
        time.sleep(0.5)
        
        try:
            with open(filepath, 'r') as f:
                content = f.read().strip()
                
            logging.info(f"File Hook triggered by {filename}")
            
            # If it's JSON, parse it as a structured payload
            try:
                data = json.loads(content)
                source = data.get("source", "file_hook")
                event_name = data.get("event", "file_dropped")
                payload = data.get("data", {})
                
                msg = f"[FILE HOOK EVENT] File: {filename} | Source: {source} | Event: {event_name} | Data: {json.dumps(payload)}"
                prompt = f"New file event received from {source} ({event_name}). Check memory for data. If this requires action, execute it. Otherwise remain silent."
                
            except json.JSONDecodeError:
                # Raw text
                msg = f"[FILE HOOK EVENT] File: {filename} | Content:\n{content}"
                prompt = f"A new text file ({filename}) was dropped into the dropzone. Content is in memory. React if necessary."

            self.agent.memory.add_short_term("system", msg)
            
            # Trigger background reasoning
            def process_file_hook():
                try:
                    self.agent.process_immediate_message("file_hook", filename, prompt)
                except Exception as e:
                    logging.error(f"File hook background reasoning error: {e}")
                    
            threading.Thread(target=process_file_hook, daemon=True).start()
            
            # Optionally delete the file after processing
            # os.remove(filepath)
            
        except Exception as e:
            logging.error(f"Error processing file hook {filename}: {e}")


class HookManager:
    """Manages system hooks (file watchers, etc) for the agent."""
    def __init__(self, agent):
        self.agent = agent
        self.observer = None

    def start(self):
        logging.info(f"Starting file hook watcher on {DROPZONE_DIR}")
        event_handler = AgentFileHandler(self.agent)
        self.observer = Observer()
        self.observer.schedule(event_handler, DROPZONE_DIR, recursive=False)
        self.observer.start()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logging.info("File hook watcher stopped.")
