import logging
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import threading

from core.config import is_webui_enabled, get_webui_port

app = FastAPI(title="OpenClaw Clone WebUI")

# Global reference to the agent instance to fetch status (set by main.py)
agent_instance = None

class ChatMessage(BaseModel):
    message: str

class SkillInstallRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
def index():
    html_content = """
    <html>
        <head>
            <title>ViClaw Dashboard</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f9; color: #333; }
                h1 { color: #2c3e50; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .status-on { color: green; font-weight: bold; }
                #chat-box { height: 300px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; border-radius: 4px; background: #fafafa;}
                .msg-user { color: blue; margin-bottom: 10px; }
                .msg-bot { color: purple; margin-bottom: 10px; }
                input[type="text"] { width: 80%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
                button { padding: 10px 20px; background-color: #2c3e50; color: white; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background-color: #1a252f; }
            </style>
        </head>
        <body>
            <h1>ViClaw Dashboard</h1>
            
            <div class="card" style="display: flex; justify-content: space-between; gap: 20px;">
                <div style="flex: 1;">
                    <h2>Agent Status: <span class="status-on">Running</span></h2>
                    <p>Background daemon active.</p>
                    <a href="/dashboard" style="display: inline-block; padding: 10px 15px; background: #0ea5e9; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-bottom: 20px;">Open 3D Dashboard →</a>
                    
                    <h3>ClawHub Setup</h3>
                    <form id="clawhub-form" onsubmit="installSkill(event)" style="margin-bottom: 20px;">
                        <input type="text" id="skill-url" placeholder="Enter ClawHub/GitHub URL..." required style="width: 60%;" />
                        <button type="submit" id="install-btn">Install</button>
                        <div id="install-msg" style="margin-top: 5px; font-size: 0.9em;"></div>
                    </form>

                    <h3>Loaded Skills</h3>
                    <ul id="skills-list">Loading...</ul>
                </div>
                
                <div style="flex: 2;">
                    <h2>Chat Interface</h2>
                    <div id="chat-box"></div>
                    <form id="chat-form" onsubmit="sendMessage(event)">
                        <input type="text" id="chat-input" placeholder="Type a message to ViClaw..." required />
                        <button type="submit">Send</button>
                    </form>
                </div>
            </div>

            <div class="card">
                <h2>System Diagnostics</h2>
                <button onclick="loadDiagnostics()" style="margin-bottom: 10px;">Run Health Check</button>
                <div id="diag-results" style="display: flex; gap: 20px; flex-wrap: wrap;">
                    <!-- Diagnostics inserted here -->
                </div>
                <h3 style="margin-top:20px;">Recent Daemon Logs</h3>
                <button onclick="loadLogs()" style="margin-bottom: 10px; background-color: #7f8c8d;">Fetch Logs</button>
                <button onclick="window.location.href='/api/download_logs'" style="margin-bottom: 10px; background-color: #e67e22;">Download Complete Logs Archive (ZIP)</button>
                <pre id="log-box" style="background:#2c3e50; color:#ecf0f1; padding:10px; border-radius:4px; max-height:200px; overflow-y:scroll; font-size:12px;">Waiting for logs...</pre>
                
                <h3 style="margin-top:20px;">Agent Action History & Raw Chat Data</h3>
                <button onclick="loadHistory()" style="margin-bottom: 10px; background-color: #8e44ad;">Load Agent Memory DB</button>
                <div id="history-box" style="background:#f9ebf9; color:#333; padding:10px; border: 1px solid #dcdde1; border-radius:4px; max-height:300px; overflow-y:scroll; font-size:13px;">
                    <i>Click 'Load Agent Memory DB' to view the raw cognitive loops and action history...</i>
                </div>
            </div>
            
            <script>
                // Load Skills
                function loadSkills() {
                    fetch('/api/skills')
                        .then(response => response.json())
                        .then(data => {
                            const list = document.getElementById('skills-list');
                            list.innerHTML = '';
                            if (data.skills.length === 0) {
                                list.innerHTML = '<li>No skills loaded.</li>';
                            } else {
                                data.skills.forEach(skill => {
                                    const li = document.createElement('li');
                                    li.innerHTML = '<strong>' + skill.name + '</strong>: ' + skill.description;
                                    list.appendChild(li);
                                });
                            }
                        });
                }
                
                loadSkills();

                function installSkill(event) {
                    event.preventDefault();
                    const urlInput = document.getElementById('skill-url');
                    const msgDiv = document.getElementById('install-msg');
                    const btn = document.getElementById('install-btn');
                    
                    const url = urlInput.value;
                    if(!url) return;
                    
                    btn.innerText = "Installing...";
                    btn.disabled = true;
                    msgDiv.innerHTML = "<span style='color:blue;'>Downloading from ClawHub...</span>";
                    
                    fetch('/api/install_skill', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: url })
                    })
                    .then(res => res.json())
                    .then(data => {
                        btn.innerText = "Install";
                        btn.disabled = false;
                        if(data.success) {
                            msgDiv.innerHTML = "<span style='color:green;'>Skill installed successfully! Reloading...</span>";
                            urlInput.value = '';
                            loadSkills();
                        } else {
                            msgDiv.innerHTML = "<span style='color:red;'>" + data.message + "</span>";
                        }
                    });
                }

                // Load Diagnostics
                function loadDiagnostics() {
                    const resDiv = document.getElementById('diag-results');
                    resDiv.innerHTML = '<p>Running checks...</p>';
                    fetch('/api/diagnostics')
                        .then(res => res.json())
                        .then(data => {
                            resDiv.innerHTML = `
                                <div style="flex: 1; min-width:200px; background:#e8f4f8; padding:15px; border-radius:8px;">
                                    <b>Daemon Status:</b><br>${data.daemon_status}
                                </div>
                                <div style="flex: 1; min-width:200px; background:#e8f8f5; padding:15px; border-radius:8px;">
                                    <b>Memory DB Size:</b><br>${data.db_size}
                                </div>
                                <div style="flex: 1; min-width:200px; background:#fef9e7; padding:15px; border-radius:8px;">
                                    <b>Ollama Link:</b><br>${data.ollama_status}
                                </div>
                                <div style="flex: 1; min-width:200px; background:#f8d7da; padding:15px; border-radius:8px;">
                                    <b>Main Model:</b><br>${data.model}
                                </div>
                            `;
                        });
                }

                // Load Logs
                function loadLogs() {
                    const logBox = document.getElementById('log-box');
                    logBox.innerHTML = 'Fetching...';
                    fetch('/api/logs')
                        .then(res => res.json())
                        .then(data => {
                            logBox.innerHTML = data.logs;
                            logBox.scrollTop = logBox.scrollHeight;
                        });
                }
                
                // Load Memory History
                function loadHistory() {
                    const histBox = document.getElementById('history-box');
                    histBox.innerHTML = 'Fetching Memory DB Context...';
                    fetch('/api/history')
                        .then(res => res.json())
                        .then(data => {
                            if (!data.history || data.history.length === 0) {
                                histBox.innerHTML = 'No history recorded yet.';
                                return;
                            }
                            let html = '';
                            data.history.forEach(entry => {
                                let role = entry.role.toUpperCase();
                                let color = "black";
                                if (role === "USER") color = "blue";
                                if (role === "ASSISTANT") color = "purple";
                                if (role === "SYSTEM") color = "#e67e22"; // Orange for internal action logs
                                
                                // Format line breaks for html
                                let content = entry.content.replace(/\\n/g, "<br>");
                                html += `<div style="margin-bottom: 15px; border-bottom: 1px dotted #ccc; padding-bottom: 5px;">
                                    <strong style="color: ${color};">[${role}]</strong> 
                                    <span style="white-space: pre-wrap;">${content}</span>
                                </div>`;
                            });
                            histBox.innerHTML = html;
                            histBox.scrollTop = histBox.scrollHeight;
                        });
                }

                // Initial loads
                loadDiagnostics();

                // Handle Chat
                function sendMessage(event) {
                    event.preventDefault();
                    const input = document.getElementById('chat-input');
                    const message = input.value;
                    input.value = '';
                    
                    const chatBox = document.getElementById('chat-box');
                    chatBox.innerHTML += '<div class="msg-user"><b>You:</b> ' + message + '</div>';
                    chatBox.scrollTop = chatBox.scrollHeight;
                    
                    // Show typing indicator
                    const typingId = 'typing-' + Date.now();
                    chatBox.innerHTML += '<div class="msg-bot" id="' + typingId + '"><i>ViClaw is typing...</i></div>';
                    chatBox.scrollTop = chatBox.scrollHeight;
                    
                    fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message })
                    })
                    .then(response => response.json())
                    .then(data => {
                        const typingEl = document.getElementById(typingId);
                        if(typingEl) typingEl.remove();
                        
                        chatBox.innerHTML += '<div class="msg-bot"><b>ViClaw:</b> ' + data.reply + '</div>';
                        chatBox.scrollTop = chatBox.scrollHeight;
                    });
                }
            </script>
        </body>
    </html>
    """
    return html_content

@app.post("/api/chat")
def handle_chat(payload: ChatMessage):
    if agent_instance:
        # Pushing this via the local API so it routes properly through agent state memory
        # We need a synchronous response for HTTP, wait for agent logic.
        
        reply, raw_content = agent_instance.process_immediate_message("web", "local_web_user", payload.message)
        return {"reply": reply, "raw_content": raw_content}
    return {"reply": "Agent is offline.", "raw_content": None}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    import os
    dash_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dash_path):
        with open(dash_path, "r") as f:
            return f.read()
    return "Dashboard HTML missing"

@app.get("/api/skills")
def get_skills():
    if agent_instance and hasattr(agent_instance, 'skill_manager'):
        skills = agent_instance.skill_manager.get_loaded_skills_info()
        return {"skills": skills}
    return {"skills": []}

@app.post("/api/install_skill")
def install_skill(payload: SkillInstallRequest):
    if not agent_instance:
        return {"success": False, "message": "Agent offline."}
    
    from skills.clawhub_client import ClawHubClient
    client = ClawHubClient()
    success = client.download_and_install(payload.url)
    if success:
        # Reload skills
        agent_instance.skill_manager._load_all_skills()
        return {"success": True, "message": "Installed perfectly."}
    return {"success": False, "message": "Failed to install. Check daemon logs."}

@app.get("/api/memory")
def get_memory():
    if agent_instance and hasattr(agent_instance, 'memory'):
        return {"short_term": agent_instance.memory.get_short_term_context()}
    return {"short_term": []}

@app.get("/api/check_update")
def check_update():
    from core.updater import UpdaterEngine
    try:
        updater = UpdaterEngine()
        has_update, loc, rem, msg = updater.check_for_updates()
        return {
            "has_update": has_update,
            "local_hash": loc,
            "remote_hash": rem,
            "message": msg
        }
    except Exception as e:
        return {"has_update": False, "message": str(e)}

@app.post("/api/trigger_update")
def trigger_update():
    from core.updater import UpdaterEngine
    try:
        updater = UpdaterEngine()
        success, log = updater.trigger_pull()
        return {"success": success, "message": log}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/diagnostics")
def get_diagnostics():
    import os
    import subprocess
    import requests
    from core.config import get_config
    
    config = get_config()
    db_size = "Unknown"
    if os.path.exists("data/memory.db"):
        db_size = f"{os.path.getsize('data/memory.db') / (1024 * 1024):.2f} MB"
        
    ollama_status = "Not Using Ollama"
    if config.get("provider") == "ollama":
        url = config.get("ollama_url", "http://localhost:11434")
        try:
            res = requests.get(f"{url.rstrip('/')}/api/tags", timeout=3)
            ollama_status = "Online" if res.status_code == 200 else f"Offline ({res.status_code})"
        except Exception:
            ollama_status = "Unreachable"

    daemon_status = "Unknown"
    try:
        res = subprocess.run(["systemctl", "is-active", "viclaw"], capture_output=True, text=True)
        daemon_status = res.stdout.strip()
    except Exception:
        daemon_status = "Not running as systemd service"

    return {
        "model": config.get("model", "Unknown"),
        "provider": config.get("provider", "Unknown"),
        "db_size": db_size,
        "ollama_status": ollama_status,
        "daemon_status": daemon_status
    }

@app.get("/api/logs")
def get_logs():
    import subprocess
    import os
    
    # Try fetching from systemd first
    try:
        res = subprocess.run(["journalctl", "-u", "viclaw", "-n", "30", "--no-pager"], capture_output=True, text=True)
        if res.stdout.strip():
            return {"logs": res.stdout}
    except Exception:
        pass
        
    # Fallback to local file if systemd journal is empty or errors
    try:
        if os.path.exists("data/viclaw.log"):
            with open("data/viclaw.log", "r") as f:
                lines = f.readlines()
                return {"logs": "".join(lines[-30:])}
        return {"logs": "Log file not found."}
    except Exception as e:
        return {"logs": f"Error fetching logs: {str(e)}"}

@app.get("/api/download_logs", response_class=FileResponse)
def download_logs():
    import os
    import zipfile
    
    zip_path = "data/viclaw_logs_archive.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists("data/viclaw.log"):
            zipf.write("data/viclaw.log", arcname="viclaw.log")
        if os.path.exists("data/memory.db"):
            zipf.write("data/memory.db", arcname="memory.db")
            
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename="viclaw_logs_archive.zip", media_type="application/zip")
    return HTMLResponse("No log files generated yet.", status_code=404)

@app.get("/api/history")
def get_history():
    if agent_instance and hasattr(agent_instance, 'memory'):
        return {"history": agent_instance.memory.short_term}
    return {"history": []}

def start_webui(agent):
    global agent_instance
    agent_instance = agent
    
    if not is_webui_enabled():
        return
        
    port = get_webui_port()
    logging.info(f"Starting WebUI on port {port} accessible externally at 0.0.0.0...")
    
    def run_server():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
        
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

