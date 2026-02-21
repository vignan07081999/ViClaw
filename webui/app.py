import logging
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import threading

from core.config import is_webui_enabled, get_webui_port

app = FastAPI(title="OpenClaw Clone WebUI")

# Global reference to the agent instance to fetch status (set by main.py)
agent_instance = None

@app.get("/", response_class=HTMLResponse)
def index():
    # A simple single-page dashboard to monitor the agent state
    html_content = """
    <html>
        <head>
            <title>OpenClaw Clone Dashboard</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f9; color: #333; }
                h1 { color: #2c3e50; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .status-on { color: green; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>OpenClaw Clone Dashboard</h1>
            <div class="card">
                <h2>Agent Status: <span class="status-on">Running</span></h2>
                <p>Use the API endpoints to inspect memory and skills.</p>
            </div>
            <div class="card">
                <h2>Loaded Skills</h2>
                <ul id="skills-list">Loading...</ul>
            </div>
            
            <script>
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
                                li.innerText = skill.name + ' - ' + skill.description;
                                list.appendChild(li);
                            });
                        }
                    });
            </script>
        </body>
    </html>
    """
    return html_content

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

def start_webui(agent):
    global agent_instance
    agent_instance = agent
    
    if not is_webui_enabled():
        return
        
    port = get_webui_port()
    logging.info(f"Starting WebUI on port {port}...")
    
    def run_server():
        # Uvicorn needs to run without reloading in this threaded context
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
        
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
