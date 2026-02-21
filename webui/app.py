import logging
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
import uvicorn
import threading

from core.config import is_webui_enabled, get_webui_port

app = FastAPI(title="OpenClaw Clone WebUI")

# Global reference to the agent instance to fetch status (set by main.py)
agent_instance = None

class ChatMessage(BaseModel):
    message: str

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
                <pre id="log-box" style="background:#2c3e50; color:#ecf0f1; padding:10px; border-radius:4px; max-height:200px; overflow-y:scroll; font-size:12px;">Waiting for logs...</pre>
            </div>
            
            <script>
                // Load Skills
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
        
        reply = agent_instance.process_immediate_message("web", "local_web_user", payload.message)
        return {"reply": reply}
    return {"reply": "Agent is offline."}

@app.get("/api/skills")
def get_skills():
    if agent_instance and hasattr(agent_instance, 'skill_manager'):
        skills = agent_instance.skill_manager.get_loaded_skills_info()
        return {"skills": skills}
    return {"skills": []}

@app.get("/api/memory")
def get_memory():
    if agent_instance and hasattr(agent_instance, 'memory'):
        return {"short_term": agent_instance.memory.get_short_term_context()}
    return {"short_term": []}

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
    try:
        res = subprocess.run(["journalctl", "-u", "viclaw", "-n", "20", "--no-pager"], capture_output=True, text=True)
        return {"logs": res.stdout}
    except Exception as e:
        return {"logs": f"Error fetching logs: {str(e)}"}

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

