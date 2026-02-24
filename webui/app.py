import logging
import os
import subprocess
import zipfile
import asyncio
import requests
import json
import threading
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import uuid
import time
from core.config import is_webui_enabled, get_webui_port

app = FastAPI(title="ViClaw Agent WebUI")

# Global reference to the agent instance (set by main.py)
agent_instance = None
DEFAULT_USER = "local_user"

class KioskLayout(BaseModel):
    layout: List[dict]

class ClawHubInstallRequest(BaseModel):
    slug: str  # ClawHub skill slug (e.g. "web-search")
    skill_id: str = ""  # Legacy compat alias

class ClawHubUninstallRequest(BaseModel):
    slug: str

class ChatMessage(BaseModel):
    message: str
    images: Optional[List[str]] = None

class SkillInstallRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
def index_dashboard(response: Response):
    # Force-clear legacy session cookies to prevent "Unauthorized" loops
    response.delete_cookie("auth_token")
    
    import os
    dash_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dash_path):
        with open(dash_path, "r") as f:
            return f.read()
    return "Dashboard file not found."

@app.post("/api/chat")
def handle_chat(payload: ChatMessage):
    if agent_instance:
        reply, raw_content = agent_instance.process_immediate_message("web", DEFAULT_USER, payload.message, images=payload.images)
        return {"reply": reply, "raw_content": raw_content}
    return {"reply": "Agent is offline.", "raw_content": None}

from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
import threading as _threading
import queue as _queue

@app.post("/api/chat/stream")
def handle_chat_stream(payload: ChatMessage):
    """
    Server-Sent Events endpoint — streams LLM tokens in real time.

    SSE event types:
      data: <token>          — raw token text (newlines escaped as \\n)
      data: [PING]           — heartbeat (keep-alive, no visual effect)
      data: [THINKING]       — agent is executing a tool call
      data: [TOOL_START]<n>  — which tool is running
      data: [TOOL_RESULT]... — JSON tool results after execution
      data: [CHUNK]          — natural chunk boundary (paragraph/sentence end)
      data: [DONE]           — stream complete
    """
    if not agent_instance:
        def _offline():
            yield "data: Agent is offline.\n\n"
            yield "data: [DONE]\n\n"
        return FastAPIStreamingResponse(_offline(), media_type="text/event-stream")

    def _stream_generator():
        import json as _json
        import re as _re
        import time as _time

        agent = agent_instance
        message_text = payload.message
        images = payload.images or []

        # Add user message to memory
        agent.memory.add_short_term("user", message_text)

        # Build system prompt
        from skills.clawhub_bridge import get_installed_skills_context
        from core.links import extract_and_fetch_links
        
        system_prompt = agent.personality.construct_system_prompt(current_query=message_text)
        
        # Feature 7: Link Understanding
        link_context = extract_and_fetch_links(message_text)
        if link_context:
            system_prompt += link_context
            
        context = agent.memory.get_short_term_context()[:-1]

        tools = agent.skill_manager.get_all_tools()
        tools_xml = "\n\nAVAILABLE TOOLS:\nYou have access to the following tools. To use a tool, you MUST output an XML block like this: <tool name=\"tool_name\">{\"arg_name\": \"arg_value\"}</tool>. Do NOT output any raw JSON outside of the XML block. If you do not need a tool, just answer normally.\nTools available:\n"
        for t in tools:
            tools_xml += f"- {t['function']['name']}: {t['function'].get('description', '')}\n  Schema: {_json.dumps(t['function'].get('parameters', {}))}\n"
        system_prompt += tools_xml

        clawhub_ctx = get_installed_skills_context()
        if clawhub_ctx:
            system_prompt += clawhub_ctx

        related = agent.memory.search_long_term(message_text, top_k=3, router=agent.router)
        if related:
            system_prompt += "\n\n[RELEVANT LONG-TERM MEMORIES (RAG)]:\n"
            for i, r in enumerate(related):
                system_prompt += f"{i+1}. {r}\n"

        # ── Stream tokens ──────────────────────────────────────────────
        full_text = []
        chunk_buf = ""        # Accumulates text since last [CHUNK] boundary
        CHUNK_TRIGGERS = {".\n", "\n\n", "!\n", "?\n", ". ", "! ", "? "}
        CHUNK_MIN_LEN = 80   # Don't emit a chunk boundary for very short buffers

        try:
            for token in agent.router.generate_stream(
                message_text,
                system_prompt=system_prompt,
                context=context,
                images=images if images else None
            ):
                full_text.append(token)
                chunk_buf += token

                # Emit the token
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"

                # Emit [CHUNK] boundary at natural break points
                if len(chunk_buf) >= CHUNK_MIN_LEN:
                    for trigger in CHUNK_TRIGGERS:
                        if chunk_buf.endswith(trigger):
                            yield "data: [CHUNK]\n\n"
                            chunk_buf = ""
                            break

        except Exception as e:
            yield f"data: [Error: {e}]\n\n"
            yield "data: [DONE]\n\n"
            return

        assembled = "".join(full_text)
        agent.memory.add_short_term("assistant", assembled)

        # ── Tool call detection + execution with PING heartbeat ────────
        pattern = r"<tool\s+name=[\"']([^\"']+)[\"']>([\s\S]*?)</tool>"
        tool_matches = list(_re.finditer(pattern, assembled))

        if tool_matches:
            # Signal the UI that tool execution is starting
            yield "data: [THINKING]\n\n"

            tool_results = []
            for match in tool_matches:
                func_name = match.group(1)
                yield f"data: [TOOL_START]{func_name}\n\n"

                # Start PING thread for this tool execution
                ping_stop = _threading.Event()
                def _ping_loop(ev=ping_stop):
                    pass   # Can't yield from thread; use queue instead

                # Execute tool with ping queue
                ping_q = _queue.Queue()
                result_box = [None]

                def _run_tool(fname=func_name, match=match, box=result_box, q=ping_q):
                    try:
                        args = _json.loads(match.group(2).strip())
                    except Exception:
                        args = {}
                    try:
                        skill = agent.skill_manager.skills.get(fname)
                        box[0] = skill.execute(fname, args) if skill else f"Unknown tool: {fname}"
                    except Exception as e:
                        box[0] = f"Tool error: {e}"
                    q.put("DONE")

                t = _threading.Thread(target=_run_tool, daemon=True)
                t.start()

                # Emit PINGs every 8 seconds until tool finishes
                while True:
                    try:
                        ping_q.get(timeout=8)
                        break   # Tool done
                    except _queue.Empty:
                        yield "data: [PING]\n\n"

                t.join()
                tool_results.append({"tool": func_name, "result": str(result_box[0])})

            yield f"data: [TOOL_RESULT]{_json.dumps(tool_results)}\n\n"

        yield "data: [DONE]\n\n"

    return FastAPIStreamingResponse(
        _stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

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

# Mount static frontend directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Expose TTS audio directory
TTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tts")
os.makedirs(TTS_DIR, exist_ok=True)
app.mount("/static/tts", StaticFiles(directory=TTS_DIR), name="static_tts")

# Models for the API payload
class ChatRequest(BaseModel):
    message: str
    images: Optional[List[str]] = None

class SkillInstallRequest(BaseModel):
    url: str

class KioskLayout(BaseModel):
    layout: List[Dict]

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

@app.get("/api/usage")
def get_usage():
    """Returns token usage stats from UsageTracker."""
    from core.usage import UsageTracker
    return UsageTracker.instance().get_stats()

@app.post("/api/usage/clear")
def clear_usage():
    """Clears all usage history."""
    from core.usage import UsageTracker
    UsageTracker.instance().clear_history()
    return {"success": True}

@app.post("/api/tts")
def generate_tts(payload: dict):
    """Generates TTS audio and returns the URL path."""
    text = payload.get("text", "")
    if not text.strip():
        return {"success": False, "message": "No text provided"}
        
    from core.tts import TTSManager
    url = TTSManager.instance().generate_audio(text)
    if url:
        return {"success": True, "url": url}
    return {"success": False, "message": "Failed to generate TTS audio"}

@app.get("/api/sessions")
def get_sessions():
    """Returns a list of all historical session IDs."""
    from core.memory import AgentMemory
    return {"sessions": AgentMemory.get_all_sessions()}

@app.post("/api/sessions/switch")
def switch_session(payload: dict):
    """Switches the active agent session."""
    session_id = payload.get("session_id", "default")
    if agent_instance:
        msg = agent_instance.switch_session(session_id)
        return {"success": True, "message": msg}
    return {"success": False, "message": "Agent offline"}

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
        "daemon_status": daemon_status,
        "failover_stats": agent_instance.router.failover_stats if agent_instance and hasattr(agent_instance, "router") else {},
        "failover_chain": config.get("failover_chain", []),
        "memory_stats": agent_instance.memory.get_memory_stats() if agent_instance and hasattr(agent_instance, "memory") else {},
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
        return {"history": agent_instance.memory.get_short_term_context()}
    return {"history": []}

@app.get("/api/kiosk_layout")
def get_kiosk_layout():
    layout_path = "data/kiosk_layout.json"
    if os.path.exists(layout_path):
        with open(layout_path, "r") as f:
            return json.load(f)
    # Default layout if none exists
    return {"layout": [
        {"id": "clock", "type": "clock", "x": 0, "y": 0, "w": 2, "h": 2},
        {"id": "agent", "type": "agent", "x": 2, "y": 0, "w": 2, "h": 4},
        {"id": "weather", "type": "weather", "x": 0, "y": 2, "w": 2, "h": 2}
    ]}

@app.post("/api/kiosk_layout")
def save_kiosk_layout(payload: KioskLayout):
    layout_path = "data/kiosk_layout.json"
    os.makedirs("data", exist_ok=True)
    with open(layout_path, "w") as f:
        json.dump(payload.dict(), f, indent=4)
    return {"success": True}

@app.get("/api/clawhub/search")
def clawhub_search(q: str = ""):
    """Vector search the live ClawHub marketplace at clawhub.ai."""
    from skills.clawhub_client import ClawHubClient
    client = ClawHubClient()
    if not q:
        return {"results": []}
    results = client.search(q)
    return {"results": results}

@app.get("/api/clawhub/browse")
def browse_clawhub(cursor: str = "", limit: int = 20):
    """
    Browse the live ClawHub skill registry.
    Supports cursor-based pagination from the API.
    Falls back to local bundled index if the network is unavailable.
    """
    from skills.clawhub_client import ClawHubClient
    client = ClawHubClient()
    data = client.list_skills(cursor=cursor or None, limit=limit)
    
    # Fall back to local bundled index if network fails
    if not data.get("items"):
        fallback_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "clawhub_index.json")
        if os.path.exists(fallback_path):
            with open(fallback_path, "r") as f:
                local_skills = json.load(f).get("skills", [])
            return {"items": local_skills, "nextCursor": None, "source": "local"}
    
    return {**data, "source": "clawhub.ai"}

@app.post("/api/clawhub/install")
def clawhub_install(payload: ClawHubInstallRequest):
    """
    Download and install a skill from the live ClawHub marketplace.
    Accepts 'slug' (e.g. "web-search") as the primary identifier.
    """
    from skills.clawhub_client import ClawHubClient
    
    slug = payload.slug or payload.skill_id
    if not slug:
        return {"success": False, "message": "No skill slug provided."}

    client = ClawHubClient()
    result = client.install_skill(slug)

    # Hot-load the newly installed skill into the running agent
    if result.get("success") and agent_instance:
        try:
            agent_instance.skill_manager._load_new_skills()
            result["message"] += " Agent hot-loaded with new skill."
        except Exception as e:
            logging.warning(f"Hot-load after install warning: {e}")
    
    return result

@app.post("/api/clawhub/uninstall")
def clawhub_uninstall(payload: ClawHubUninstallRequest):
    """Remove an installed ClawHub skill."""
    from skills.clawhub_client import ClawHubClient
    client = ClawHubClient()
    return client.uninstall_skill(payload.slug)

@app.get("/api/clawhub/installed")
def clawhub_installed():
    """List all ClawHub skills currently installed."""
    from skills.clawhub_client import ClawHubClient
    client = ClawHubClient()
    installed = client.get_installed_clawhub_skills()
    return {"installed": installed}


@app.get("/api/proxy")
def web_proxy(url: str):
    """Simple proxy for iframe-blocked sites (e.g. Home Assistant)."""
    try:
        res = requests.get(url, timeout=10)
        return HTMLResponse(content=res.text)
    except Exception as e:
        return HTMLResponse(content=f"Proxy error: {str(e)}", status_code=500)

def start_webui(agent):
    global agent_instance
    agent_instance = agent

    if not is_webui_enabled():
        return

    port = get_webui_port()
    logging.info(f"Starting Zero-Auth WebUI on port {port}...")

    def run_server():
        # Use uvicorn.Server + isolated asyncio loop so signal handlers
        # don't crash when running inside a daemon thread.
        cfg = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(cfg)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    threading.Thread(target=run_server, daemon=True).start()

