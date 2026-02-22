"""
core/memory.py — ViClaw Agent Memory

Improvements in this version:
  - Short-term context is checkpointed to SQLite on every add_short_term() call
  - On startup, the last N messages are restored from the DB so context survives daemon restarts
  - Per-session isolation: each session_id gets its own short-term buffer (supports multi-user WebUI)
  - Cosine similarity search still falls back to fuzzy text if embeddings unavailable
"""

import sqlite3
import os
import json
import logging
from datetime import datetime

MEMORY_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db")


class AgentMemory:
    def __init__(self, max_short_term: int = 20, session_id: str = "default"):
        self.max_short_term = max_short_term
        self.session_id = session_id
        self.short_term_context: list = []
        self.db_path = MEMORY_DB
        self._init_db()
        self._restore_short_term()

    # ------------------------------------------------------------------
    # DB Initialisation
    # ------------------------------------------------------------------

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Long-term semantic memory
            c.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    topic     TEXT,
                    content   TEXT,
                    importance INTEGER,
                    embedding TEXT
                )
            """)
            # Short-term checkpoint per session
            c.execute("""
                CREATE TABLE IF NOT EXISTS short_term_checkpoint (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp  TEXT,
                    role       TEXT,
                    content    TEXT
                )
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Short-term (in-RAM + checkpoint)
    # ------------------------------------------------------------------

    def _restore_short_term(self):
        """Restore the last `max_short_term` messages from the DB checkpoint on startup."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT role, content FROM short_term_checkpoint "
                    "WHERE session_id=? ORDER BY id DESC LIMIT ?",
                    (self.session_id, self.max_short_term),
                )
                rows = c.fetchall()
            # Rows come back newest-first; reverse to get chronological order
            self.short_term_context = [{"role": r, "content": c} for r, c in reversed(rows)]
            if self.short_term_context:
                logging.info(
                    f"Restored {len(self.short_term_context)} messages from short-term checkpoint "
                    f"(session={self.session_id})."
                )
        except Exception as e:
            logging.warning(f"Could not restore short-term checkpoint: {e}")
            self.short_term_context = []

    def _checkpoint_message(self, role: str, content: str):
        """Persist a single message to the short-term checkpoint table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO short_term_checkpoint (session_id, timestamp, role, content) "
                    "VALUES (?, ?, ?, ?)",
                    (self.session_id, datetime.now().isoformat(), role, content),
                )
                conn.commit()
        except Exception as e:
            logging.warning(f"Short-term checkpoint write failed: {e}")

    def add_short_term(self, role: str, content: str):
        self.short_term_context.append({"role": role, "content": content})
        self._checkpoint_message(role, content)

        # Sliding window: drop oldest pair when over limit
        if len(self.short_term_context) > self.max_short_term:
            logging.info("Memory sliding window: compressing oldest context pair.")
            pop_count = 2 if len(self.short_term_context) >= 2 else 1
            for _ in range(pop_count):
                self.short_term_context.pop(0)

    def get_short_term_context(self) -> list:
        return self.short_term_context

    def clear_short_term(self, session_id: str = None):
        """Clear in-RAM context and wipe the checkpoint for this session."""
        sid = session_id or self.session_id
        self.short_term_context = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM short_term_checkpoint WHERE session_id=?", (sid,)
                )
                conn.commit()
        except Exception as e:
            logging.warning(f"Could not clear short-term checkpoint: {e}")

    def summarize_and_compress(self):
        """Drop the oldest half of context (called by /compact slash command)."""
        half = len(self.short_term_context) // 2
        self.short_term_context = self.short_term_context[half:]
        logging.info("Context compacted by /compact command.")

    # ------------------------------------------------------------------
    # Long-term vector memory
    # ------------------------------------------------------------------

    def get_embedding(self, text: str) -> list:
        try:
            import requests
            from core.config import get_config
            url = get_config().get("ollama_url", "http://localhost:11434")
            res = requests.post(
                f"{url.rstrip('/')}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=10,
            )
            if res.status_code == 200:
                return res.json().get("embedding", [])
        except Exception as e:
            logging.error(f"Embedding generation failed: {e}")
        return []

    def add_long_term(self, content: str, topic: str = "general", importance: int = 1):
        timestamp = datetime.now().isoformat()
        vec = self.get_embedding(content)
        vec_str = json.dumps(vec) if vec else "[]"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO memories (timestamp, topic, content, importance, embedding) "
                "VALUES (?, ?, ?, ?, ?)",
                (timestamp, topic, content, importance, vec_str),
            )
            conn.commit()
        logging.info(f"Long-term memory saved: {content[:60]}...")

    def search_long_term(self, query: str, top_k: int = 3) -> list:
        query_vec = self.get_embedding(query)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT content, embedding FROM memories"
            ).fetchall()

        if not rows:
            return []

        if not query_vec:
            # Fuzzy text fallback when embeddings unavailable
            words = [w for w in query.split() if len(w) > 3]
            if not words:
                return []
            with sqlite3.connect(self.db_path) as conn:
                likes = " OR ".join(["content LIKE ?" for _ in words])
                params = [f"%{w}%" for w in words]
                sql = (
                    f"SELECT content FROM memories WHERE {likes} "
                    f"ORDER BY importance DESC, timestamp DESC LIMIT {top_k}"
                )
                fallback = conn.execute(sql, params).fetchall()
            return [r[0] for r in fallback]

        # Vector cosine similarity
        try:
            import numpy as np
            q_arr = np.array(query_vec)
            scored = []
            for content, emb_str in rows:
                if not emb_str or emb_str == "[]":
                    continue
                db_arr = np.array(json.loads(emb_str))
                norm = np.linalg.norm(q_arr) * np.linalg.norm(db_arr)
                sim = float(np.dot(q_arr, db_arr) / norm) if norm > 0 else 0.0
                scored.append((sim, content))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [c for _, c in scored[:top_k]]
        except ImportError:
            logging.error("numpy not installed. Cannot compute vector similarity.")
            return []
