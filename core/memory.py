"""
core/memory.py — ViClaw Agent Memory  (Feature 1: Full Vector Memory Upgrade)

Improvements in this version:
  - MMR (Maximal Marginal Relevance): returns diverse top-k memories, not just nearest
  - Temporal decay: multiplies similarity score by recency factor so newer memories rank higher
  - Hybrid search: BM25 keyword score merged with vector cosine score (configurable alpha)
  - Background batch indexer: new memories are embedded in a daemon thread, never blocking chat
  - Query expansion: the query is rewritten by the LLM to improve vector recall
  - Smart /compact: LLM summarises the context instead of blindly truncating
  - Short-term checkpoint to SQLite (restart-safe)
  - Per-session isolation
"""

import sqlite3
import os
import json
import math
import logging
import threading
from datetime import datetime, timezone
from collections import Counter

MEMORY_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db")

# Hybrid search weight: 1.0 = pure vector, 0.0 = pure BM25
HYBRID_ALPHA = 0.7
# Temporal decay half-life in days (memories older than this score ~50% of a fresh memory)
DECAY_HALF_LIFE_DAYS = 14
# MMR lambda: 1.0 = pure relevance (no diversity), 0.0 = pure diversity
MMR_LAMBDA = 0.6


def _cosine(a: list, b: list) -> float:
    """Fast cosine similarity between two equal-length float lists."""
    try:
        import numpy as np
        a_arr, b_arr = np.array(a), np.array(b)
        norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        return float(np.dot(a_arr, b_arr) / norm) if norm > 0 else 0.0
    except ImportError:
        # Pure-Python fallback (slow but correct)
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        return dot / (mag_a * mag_b) if mag_a * mag_b > 0 else 0.0


def _temporal_score(timestamp_iso: str) -> float:
    """Returns a decay multiplier in (0, 1] based on how old the memory is."""
    try:
        stored = datetime.fromisoformat(timestamp_iso).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = max(0.0, (now - stored).total_seconds() / 86400)
        return math.exp(-math.log(2) * age_days / DECAY_HALF_LIFE_DAYS)
    except Exception:
        return 1.0


def _bm25_score(content: str, query_tokens: list, avg_dl: float, k1: float = 1.5, b: float = 0.75) -> float:
    """Simplified single-document BM25 score for a query."""
    if not query_tokens or avg_dl == 0:
        return 0.0
    words = content.lower().split()
    dl = len(words)
    tf_map = Counter(words)
    score = 0.0
    for token in query_tokens:
        tf = tf_map.get(token, 0)
        score += (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
    return score


def _mmr_select(candidates: list, query_vec: list, top_k: int, lam: float = MMR_LAMBDA) -> list:
    """
    Maximal Marginal Relevance selection.
    candidates: list of (similarity_score, content, embedding_list)
    Returns the top_k most relevant AND diverse results.
    """
    if not candidates:
        return []
    selected = []
    remaining = list(candidates)

    while len(selected) < top_k and remaining:
        if not selected:
            # First pick: highest relevance
            best = max(remaining, key=lambda x: x[0])
        else:
            # Subsequent picks: balance relevance vs. redundancy
            selected_vecs = [s[2] for s in selected]
            def mmr_score(c):
                rel = c[0]
                red = max(_cosine(c[2], sv) for sv in selected_vecs) if selected_vecs else 0.0
                return lam * rel - (1 - lam) * red
            best = max(remaining, key=mmr_score)

        selected.append(best)
        remaining.remove(best)

    return [c[1] for c in selected]  # Return just the content strings


class AgentMemory:
    def __init__(self, max_short_term: int = 20, session_id: str = "default"):
        self.max_short_term = max_short_term
        self.session_id = session_id
        self.short_term_context: list = []
        self.db_path = MEMORY_DB
        self._embed_queue = []
        self._embed_lock = threading.Lock()
        self._init_db()
        self._restore_short_term()
        self._start_background_indexer()

    @classmethod
    def get_all_sessions(cls) -> list:
        """Returns a list of all unique session IDs that have checkpoints."""
        try:
            with sqlite3.connect(cls(session_id="dummy_for_query").db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT DISTINCT session_id FROM short_term_checkpoint WHERE session_id != 'dummy_for_query' ORDER BY id DESC")
                rows = c.fetchall()
            return [r[0] for r in rows if r[0]]
        except Exception as e:
            logging.warning(f"Failed to list sessions: {e}")
            return []

    # ------------------------------------------------------------------
    # DB Initialisation
    # ------------------------------------------------------------------

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    topic     TEXT,
                    content   TEXT,
                    importance INTEGER DEFAULT 1,
                    embedding TEXT DEFAULT '[]'
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS short_term_checkpoint (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp  TEXT,
                    role       TEXT,
                    content    TEXT
                )
            """)
            # Performance indexes — prevent full table scans as memory grows
            c.execute("CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp DESC)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_memories_topic ON memories(topic)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_stc_session ON short_term_checkpoint(session_id, timestamp DESC)")
            conn.commit()

    # ------------------------------------------------------------------
    # Short-term (in-RAM + checkpoint)
    # ------------------------------------------------------------------

    def _restore_short_term(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT role, content FROM short_term_checkpoint "
                    "WHERE session_id=? ORDER BY id DESC LIMIT ?",
                    (self.session_id, self.max_short_term),
                )
                rows = c.fetchall()
            self.short_term_context = [{"role": r, "content": c} for r, c in reversed(rows)]
            if self.short_term_context:
                logging.info(f"Restored {len(self.short_term_context)} messages (session={self.session_id}).")
        except Exception as e:
            logging.warning(f"Could not restore short-term checkpoint: {e}")
            self.short_term_context = []

    def _checkpoint_message(self, role: str, content: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO short_term_checkpoint (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                    (self.session_id, datetime.now().isoformat(), role, content),
                )
                conn.commit()
        except Exception as e:
            logging.warning(f"Short-term checkpoint write failed: {e}")

    def add_short_term(self, role: str, content: str):
        self.short_term_context.append({"role": role, "content": content})
        self._checkpoint_message(role, content)
        if len(self.short_term_context) > self.max_short_term:
            pop_count = 2 if len(self.short_term_context) >= 2 else 1
            for _ in range(pop_count):
                self.short_term_context.pop(0)

    def get_short_term_context(self) -> list:
        return self.short_term_context

    def clear_short_term(self, session_id: str = None):
        sid = session_id or self.session_id
        self.short_term_context = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM short_term_checkpoint WHERE session_id=?", (sid,))
                conn.commit()
        except Exception as e:
            logging.warning(f"Could not clear short-term checkpoint: {e}")

    def summarize_and_compress(self, router=None):
        """
        Smart /compact: if an LLM router is provided, generates a summary of the oldest
        half of the context and replaces it with a single [SUMMARY] system message.
        Falls back to simple truncation if no router.
        """
        if not self.short_term_context:
            return

        half = len(self.short_term_context) // 2
        to_summarize = self.short_term_context[:half]
        self.short_term_context = self.short_term_context[half:]

        if router:
            try:
                text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in to_summarize])
                summary_prompt = "Summarize the following conversation in 3-5 concise bullet points, preserving key facts and decisions:\n\n" + text
                result = router.generate(summary_prompt, system_prompt="You are a concise summarizer. Output only the bullet points, no preamble.")
                summary_text = result.get("content", "").strip()
                if summary_text:
                    summary_msg = {"role": "system", "content": f"[COMPACTED CONTEXT SUMMARY]\n{summary_text}"}
                    self.short_term_context.insert(0, summary_msg)
                    logging.info("Context compacted with LLM summary.")
                    return
            except Exception as e:
                logging.warning(f"LLM /compact summary failed, falling back to truncation: {e}")

        logging.info("Context compacted by truncation.")

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
            logging.debug(f"Embedding generation failed: {e}")
        return []

    def _expand_query(self, query: str, router=None) -> str:
        """
        Use the LLM to rephrase/expand the query for better vector recall.
        Only called if a router is passed in.
        """
        if not router:
            return query
        try:
            result = router.generate(
                f"Rephrase and expand this search query in 1-2 sentences to improve semantic recall. Query: {query}",
                system_prompt="Output only the expanded query. No explanations."
            )
            expanded = result.get("content", "").strip()
            return expanded if expanded else query
        except Exception:
            return query

    def add_long_term(self, content: str, topic: str = "general", importance: int = 1):
        """Save a memory immediately (embedding computed inline or queued for background)."""
        timestamp = datetime.now().isoformat()
        # Save with empty embedding first for speed, then queue embedding
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO memories (timestamp, topic, content, importance, embedding) VALUES (?, ?, ?, ?, ?)",
                (timestamp, topic, content, importance, "[]"),
            )
            row_id = cur.lastrowid
            conn.commit()

        # Queue background embedding
        with self._embed_lock:
            self._embed_queue.append((row_id, content))

        logging.info(f"Long-term memory saved (id={row_id}): {content[:60]}...")

    def search_long_term(self, query: str, top_k: int = 3, router=None) -> list:
        """
        Hybrid search: vector cosine similarity + BM25 keyword score + temporal decay.
        Results de-duplicated with MMR.
        """
        # Step 1: Query expansion (optional, if router provided)
        expanded_query = self._expand_query(query, router)
        query_vec = self.get_embedding(expanded_query)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT content, embedding, timestamp, importance FROM memories"
            ).fetchall()

        if not rows:
            return []

        # Precompute BM25 avg document length
        query_tokens = query.lower().split()
        all_lengths = [len(r[0].split()) for r in rows]
        avg_dl = sum(all_lengths) / len(all_lengths) if all_lengths else 1.0

        if not query_vec:
            # Pure keyword fallback
            scored = []
            for content, _, timestamp, importance in rows:
                bm25 = _bm25_score(content, query_tokens, avg_dl)
                decay = _temporal_score(timestamp)
                scored.append((bm25 * decay * importance, content))
            scored.sort(reverse=True)
            return [c for _, c in scored[:top_k]]

        # Hybrid scoring: alpha * cosine + (1-alpha) * normalised BM25 + temporal decay
        candidates = []
        bm25_scores = []
        for content, emb_str, timestamp, importance in rows:
            try:
                emb = json.loads(emb_str) if emb_str and emb_str != "[]" else []
            except Exception:
                emb = []
            bm25 = _bm25_score(content, query_tokens, avg_dl)
            bm25_scores.append(bm25)
            candidates.append((content, emb, timestamp, importance, bm25))

        max_bm25 = max(bm25_scores) if bm25_scores else 1.0
        if max_bm25 == 0:
            max_bm25 = 1.0

        scored = []
        for content, emb, timestamp, importance, bm25 in candidates:
            vec_sim = _cosine(query_vec, emb) if emb else 0.0
            norm_bm25 = bm25 / max_bm25
            hybrid = HYBRID_ALPHA * vec_sim + (1 - HYBRID_ALPHA) * norm_bm25
            decay = _temporal_score(timestamp)
            final_score = hybrid * decay * max(1, importance)
            scored.append((final_score, content, emb))

        scored.sort(key=lambda x: x[0], reverse=True)

        # MMR de-duplication over top 2*top_k candidates
        pool = scored[: top_k * 2]
        return _mmr_select(pool, query_vec, top_k)

    # ------------------------------------------------------------------
    # Background embedding indexer (daemon thread)
    # ------------------------------------------------------------------

    def _start_background_indexer(self):
        """Daemon thread that processes the embedding queue every 5 seconds."""
        def _loop():
            while True:
                import time
                time.sleep(5)
                with self._embed_lock:
                    batch = list(self._embed_queue)
                    self._embed_queue.clear()

                for row_id, content in batch:
                    try:
                        vec = self.get_embedding(content)
                        if vec:
                            with sqlite3.connect(self.db_path) as conn:
                                conn.execute(
                                    "UPDATE memories SET embedding=? WHERE id=?",
                                    (json.dumps(vec), row_id),
                                )
                                conn.commit()
                            logging.debug(f"Background embedded memory id={row_id}")
                    except Exception as e:
                        logging.warning(f"Background embed failed for id={row_id}: {e}")

        t = threading.Thread(target=_loop, daemon=True)
        t.name = "ViClaw-MemoryIndexer"
        t.start()
        logging.info("Background memory indexer started.")

    # ------------------------------------------------------------------
    # Convenience / diagnostics
    # ------------------------------------------------------------------

    def get_memory_stats(self) -> dict:
        """Returns stats about the memory database for the /api/diagnostics endpoint."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                embedded = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE embedding != '[]' AND embedding IS NOT NULL"
                ).fetchone()[0]
                pending = len(self._embed_queue)
            return {
                "total_memories": total,
                "embedded_memories": embedded,
                "pending_embedding": pending,
                "hybrid_alpha": HYBRID_ALPHA,
                "decay_half_life_days": DECAY_HALF_LIFE_DAYS,
            }
        except Exception:
            return {}

    # Alias for backward compatibility
    @property
    def short_term(self):
        return self.short_term_context
