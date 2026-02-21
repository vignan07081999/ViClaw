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
                      importance INTEGER)''')
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

    def add_long_term(self, content, topic="general", importance=1):
        """
        Saves a fact, summary, or user preference to persistent local database.
        """
        timestamp = datetime.now().isoformat()
        logging.info(f"Saving long-term memory: {content[:50]}...")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO memories (timestamp, topic, content, importance) VALUES (?, ?, ?, ?)",
                  (timestamp, topic, content, importance))
        conn.commit()
        conn.close()

    def search_long_term(self, query, top_k=5):
        """
        Retrieves relevant long-term memories.
        In a full clone utilizing vector embeddings, this would do a cosine similarity search.
        Using a simple LIKE approach for this baseline.
        """
        words = [w for w in query.split() if len(w) > 3]
        if not words:
            return []

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Build simple OR query for keywords
        likes = " OR ".join(["content LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]
        
        # Order by importance and recency
        sql = f"SELECT content FROM memories WHERE {likes} ORDER BY importance DESC, timestamp DESC LIMIT {top_k}"
        
        c.execute(sql, params)
        results = c.fetchall()
        conn.close()

        return [r[0] for r in results]
