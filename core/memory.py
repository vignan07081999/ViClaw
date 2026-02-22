import sqlite3
import os
import json
import logging
from datetime import datetime

MEMORY_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db")

class AgentMemory:
    def __init__(self, max_short_term=20):
        self.max_short_term = max_short_term
        self.short_term_context = []  # List of dicts: {"role": "...", "content": "..."}
        self.db_path = MEMORY_DB
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS memories
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp TEXT,
                      topic TEXT,
                      content TEXT,
                      importance INTEGER,
                      embedding TEXT)''')
        conn.commit()
        conn.close()

    def add_short_term(self, role, content):
        self.short_term_context.append({"role": role, "content": content})
        
        # Smart Context compression: If over limit, we remove the oldest 2 messages
        # to ensure we typically drop a full (user + assistant) pair rather than breaking flow
        if len(self.short_term_context) > self.max_short_term:
            logging.info("Memory Limit Reached: Sliding context window to compress memory.")
            # Drop the oldest two messages (assuming they aren't marked as system critical)
            # In a full implementation, you could summarize these and inject them as a fresh 'system' message
            pop_count = 2 if len(self.short_term_context) >= 2 else 1
            for _ in range(pop_count):
                self.short_term_context.pop(0)

    def get_short_term_context(self):
        return self.short_term_context

    def get_embedding(self, text):
        """
        Calls Ollama locally to generate a vector embedding using nomic-embed-text.
        """
        try:
            import requests
            from core.config import get_config
            url = get_config().get("ollama_url", "http://localhost:11434")
            res = requests.post(f"{url.rstrip('/')}/api/embeddings", json={
                "model": "nomic-embed-text",
                "prompt": text
            }, timeout=10)
            if res.status_code == 200:
                return res.json().get("embedding", [])
        except Exception as e:
            logging.error(f"Failed to generate embedding: {e}")
        return []

    def add_long_term(self, content, topic="general", importance=1):
        """
        Saves a fact or document chunk to persistent local database via Vector Embeddings.
        """
        timestamp = datetime.now().isoformat()
        logging.info(f"Saving embedded memory: {content[:50]}...")
        
        # Generate Nomic embedding
        vec = self.get_embedding(content)
        vec_str = json.dumps(vec) if vec else "[]"
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO memories (timestamp, topic, content, importance, embedding) VALUES (?, ?, ?, ?, ?)",
                  (timestamp, topic, content, importance, vec_str))
        conn.commit()
        conn.close()

    def search_long_term(self, query, top_k=3):
        """
        Retrieves relevant long-term memories using cosine similarity against Ollama embeddings.
        Fallback to fuzzy string matching if vector graph fails.
        """
        query_vec = self.get_embedding(query)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT content, embedding FROM memories")
        rows = c.fetchall()
        conn.close()

        if not rows:
            return []

        if not query_vec:
            # Fallback to fuzzy text search if embeddings offline
            words = [w for w in query.split() if len(w) > 3]
            if not words: return []
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            likes = " OR ".join(["content LIKE ?" for _ in words])
            params = [f"%{w}%" for w in words]
            sql = f"SELECT content FROM memories WHERE {likes} ORDER BY importance DESC, timestamp DESC LIMIT {top_k}"
            c.execute(sql, params)
            fallback_res = c.fetchall()
            conn.close()
            return [r[0] for r in fallback_res]

        # Vector Math Calculation (Cosine Similarity)
        try:
            import numpy as np
            q_arr = np.array(query_vec)
            scored_rows = []
            
            for content, emb_str in rows:
                if not emb_str or emb_str == "[]": continue
                db_arr = np.array(json.loads(emb_str))
                
                # Cosine sim
                dot = np.dot(q_arr, db_arr)
                norm = np.linalg.norm(q_arr) * np.linalg.norm(db_arr)
                sim = dot / norm if norm > 0 else 0
                
                scored_rows.append((sim, content))
                
            # Sort highest similarity first
            scored_rows.sort(key=lambda x: x[0], reverse=True)
            return [r[1] for r in scored_rows[:top_k]]
            
        except ImportError:
            logging.error("Numpy not installed. Cannot compute vector distance.")
            return []
