import logging
import os
import subprocess
import zipfile
import asyncio
import requests
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response, Cookie
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import APIKeyCookie
from pydantic import BaseModel
from typing import Optional, List
import uuid
import time
import uvicorn
import threading

from core.config import is_webui_enabled, get_webui_port

app = FastAPI(title="ViClaw Agent WebUI")

# Global reference to the agent instance (set by main.py)
agent_instance = None

# In-memory session store mapping SessionToken -> {user_id, expires}
ACTIVE_SESSIONS: dict = {}
cookie_scheme = APIKeyCookie(name="viclaw_session", auto_error=False)


def _evict_expired_sessions():
    """Background task: remove sessions past their expiry every hour."""
    while True:
        now = time.time()
        expired = [k for k, v in list(ACTIVE_SESSIONS.items()) if now > v["expires"]]
        for k in expired:
            ACTIVE_SESSIONS.pop(k, None)
        if expired:
            logging.info(f"Session cleanup: evicted {len(expired)} expired session(s).")
        time.sleep(3600)

def get_current_user(viclaw_session: str = Depends(cookie_scheme)):
    if not viclaw_session or viclaw_session not in ACTIVE_SESSIONS:
        # For API routes we can raise 401. For HTML routes we'd redirect.
        return None
    
    session = ACTIVE_SESSIONS[viclaw_session]
    if time.time() > session["expires"]:
        del ACTIVE_SESSIONS[viclaw_session]
        return None
        
    return session["user_id"]

class ChatMessage(BaseModel):
    message: str
    images: Optional[List[str]] = None

class SkillInstallRequest(BaseModel):
    url: str

class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/", response_class=HTMLResponse)
def index_login(request: Request, viclaw_session: str = Cookie(None)):
    if viclaw_session and viclaw_session in ACTIVE_SESSIONS and time.time() < ACTIVE_SESSIONS[viclaw_session]["expires"]:
        dash_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
        if os.path.exists(dash_path):
            with open(dash_path, "r") as f:
                return f.read()
                
    # Serve Login Page
    html_content = """
    <html>
        <head>
            <title>ViClaw Login</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background-color: #0f172a; color: #f8fafc; display:flex; justify-content:center; align-items:center; height:100vh; }
                .login-box { background: #1e293b; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 350px; text-align: center; border: 1px solid #334155;}
                h1 { color: #38bdf8; margin-top:0;}
                input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #334155; border-radius: 6px; background: #0f172a; color:white; box-sizing: border-box; }
                button { width: 100%; padding: 12px; background-color: #38bdf8; color: #0f172a; border: none; border-radius: 6px; cursor: pointer; font-weight:bold; margin-top:15px; }
                button:hover { background-color: #0ea5e9; }
                #error-msg { color: #ef4444; margin-top: 10px; font-size: 0.9em; height: 20px;}
            </style>
        </head>
        <body>
            <div class="login-box">
                <h1>ViClaw Agent Gateway</h1>
                <p style="opacity:0.7; font-size:14px; margin-bottom:20px;">Secure Swarm System Authentication</p>
                <form id="login-form" onsubmit="doLogin(event)">
                    <input type="text" id="username" placeholder="Username (Default: admin)" required autofocus />
                    <input type="password" id="password" placeholder="Password (Default: claw)" required />
                    <button type="submit">Initialize Session</button>
                    <div id="error-msg"></div>
                </form>
            </div>
            
            <script>
                function doLogin(e) {
                    e.preventDefault();
                    const u = document.getElementById('username').value;
                    const p = document.getElementById('password').value;
                    
                    fetch('/api/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({username: u, password: p})
                    }).then(res => res.json()).then(data => {
                        if(data.success) {
                            window.location.reload(); // Reloads root logic (which now serves dashboard due to cookie)
                        } else {
                            document.getElementById('error-msg').innerText = "Access Denied.";
                        }
                    });
                }
            </script>
        </body>
    </html>
    """
    return html_content

@app.post("/api/login")
def login(payload: LoginRequest, response: Response):
    """
    Authenticate against credentials stored in data/config.json.
    Falls back to a one-time random token printed to the daemon log on first boot
    if no credentials have been configured via the install wizard.
    """
    from core.config import get_config
    cfg = get_config()
    creds = cfg.get("webui", {}).get("credentials", {})
    admin_user = creds.get("username", "admin")
    admin_pass = creds.get("password", "")

    # If no password was ever set, block login and log a warning
    if not admin_pass:
        logging.warning("WebUI login attempted but no password is configured. Run ./install.sh to set credentials.")
        return {"success": False, "error": "No credentials configured. Run the install wizard first."}

    if payload.username == admin_user and payload.password == admin_pass:
        session_id = str(uuid.uuid4())
        ACTIVE_SESSIONS[session_id] = {
            "user_id": payload.username,
            "expires": time.time() + (24 * 3600),  # 24-hour session
        }
        response.set_cookie(
            key="viclaw_session", value=session_id,
            httponly=True, samesite="lax", max_age=86400
        )
        logging.info(f"WebUI login: user '{payload.username}' authenticated.")
        return {"success": True}

    logging.warning(f"WebUI login: failed attempt for username '{payload.username}'.")
    return {"success": False, "error": "Invalid credentials."}

@app.post("/api/chat")
def handle_chat(payload: ChatMessage, user_id: str = Depends(get_current_user)):
    if not user_id:
        return {"reply": "Unauthorized. Please refresh and log back in.", "raw_content": None}
        
    if agent_instance:
        # Bind the specific authenticated user to the agent processing pipeline
        reply, raw_content = agent_instance.process_immediate_message("web", user_id, payload.message, images=payload.images)
        return {"reply": reply, "raw_content": raw_content}
    return {"reply": "Agent is offline.", "raw_content": None}

class WebhookPayload(BaseModel):
    source: str
    event: str
    data: dict

@app.post("/api/webhook")
def handle_webhook(payload: WebhookPayload):
    """
    Generic webhook ingestor for external system events (Home Assistant, Frigate, Node-RED).
    """
    if not agent_instance:
        return {"success": False, "message": "Agent offline."}
        
    # Synthesize the event into a system memory chunk
    msg = f"[EXTERNAL WEBHOOK EVENT] Source: {payload.source} | Event: {payload.event} | Data: {json.dumps(payload.data)}"
    agent_instance.memory.add_short_term("system", msg)
    logging.info(f"Webhook Ingested: {msg}")
    
    # Trigger a silent background inference pass to let the Agent react to the webhook
    def process_webhook():
        try:
            agent_instance.process_immediate_message("webhook", payload.source, f"New system event received: {payload.event}. Check memory for details. If this requires immediate attention, use a tool or send a proactive message. Otherwise, remain silent.")
        except Exception as e:
            logging.error(f"Webhook background reasoning error: {e}")
            
    threading.Thread(target=process_webhook, daemon=True).start()
    
    return {"success": True, "message": "Event ingested and agent notified."}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    import os
    dash_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dash_path):
        with open(dash_path, "r") as f:
            return f.read()
    return "Dashboard HTML missing"

@app.get("/kiosk", response_class=HTMLResponse)
def kiosk():
    from core.config import get_config
    if not get_config().get("kiosk", {}).get("enabled", True):
        return HTMLResponse("<h1>Kiosk Dashboard is Disabled in Config</h1><p>Enable it in your data/config.json.</p>")
    kiosk_path = os.path.join(os.path.dirname(__file__), "kiosk.html")
    if os.path.exists(kiosk_path):
        with open(kiosk_path, "r") as f:
            return f.read()
    return "Kiosk HTML missing"

@app.get("/wiki", response_class=HTMLResponse)
def wiki():
    wiki_path = os.path.join(os.path.dirname(__file__), "wiki.html")
    if os.path.exists(wiki_path):
        with open(wiki_path, "r") as f:
            return f.read()
    return "Wiki HTML missing"

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
        # Delta-load: only import the newly added skill file(s), preserving existing skill state
        agent_instance.skill_manager._load_new_skills()
        return {"success": True, "message": "Skill installed and hot-loaded."}
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
        return {"history": agent_instance.memory.short_term_context}
    return {"history": []}

def start_webui(agent):
    global agent_instance
    agent_instance = agent

    if not is_webui_enabled():
        return

    port = get_webui_port()
    logging.info(f"Starting WebUI on port {port} bound to 0.0.0.0...")

    # Start session cleanup background thread
    threading.Thread(target=_evict_expired_sessions, daemon=True).start()

    def run_server():
        # Use uvicorn.Server + isolated asyncio loop so signal handlers
        # don't crash when running inside a daemon thread.
        cfg = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(cfg)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    threading.Thread(target=run_server, daemon=True).start()

