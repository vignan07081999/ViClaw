"""
core/usage.py — ViClaw Usage Tracker  (Feature 6)

Records per-call and cumulative token usage for every LLM interaction.
  - Estimates tokens via tiktoken (if available) or simple char/4 heuristic
  - Persists to SQLite in data/usage.db for cross-session totals
  - Exposes get_stats() for /api/usage and format_report() for viclaw usage CLI
"""

import sqlite3
import os
import json
import time
import logging
from datetime import datetime, timezone

USAGE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "usage.db")


def _estimate_tokens(text: str, model: str = "") -> int:
    """Estimate token count. Uses tiktoken when available, falls back to char/4."""
    if not text:
        return 0
    try:
        import tiktoken
        # Map common Ollama models to tiktoken encodings
        ENC_MAP = {
            "gpt": "cl100k_base",
            "llama": "cl100k_base",
            "qwen": "cl100k_base",
            "mistral": "cl100k_base",
            "phi": "cl100k_base",
        }
        enc_name = "cl100k_base"
        for key, enc in ENC_MAP.items():
            if key in model.lower():
                enc_name = enc
                break
        enc = tiktoken.get_encoding(enc_name)
        return len(enc.encode(text))
    except Exception:
        # Rough fallback: ~4 chars per token
        return max(1, len(text) // 4)


class UsageTracker:
    """Singleton usage tracker — use UsageTracker.instance() to get the shared instance."""
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._init_db()
        # In-process session counters (reset on restart)
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_calls = 0
        self.session_start = datetime.now(timezone.utc).isoformat()

    def _init_db(self):
        os.makedirs(os.path.dirname(USAGE_DB), exist_ok=True)
        with sqlite3.connect(USAGE_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp          TEXT,
                    model              TEXT,
                    provider           TEXT,
                    prompt_tokens      INTEGER,
                    completion_tokens  INTEGER,
                    latency_ms         INTEGER,
                    failover_used      TEXT
                )
            """)
            conn.commit()

    def record(self, model: str, provider: str, prompt: str, completion: str,
               latency_ms: int = 0, failover_used: str = ""):
        """Record a single LLM call. Call this after every generate() completes."""
        prompt_toks = _estimate_tokens(prompt, model)
        comp_toks = _estimate_tokens(completion, model)

        # Update in-session counters
        self.session_prompt_tokens += prompt_toks
        self.session_completion_tokens += comp_toks
        self.session_calls += 1

        # Persist to SQLite
        try:
            with sqlite3.connect(USAGE_DB) as conn:
                conn.execute(
                    "INSERT INTO usage_log (timestamp, model, provider, prompt_tokens, "
                    "completion_tokens, latency_ms, failover_used) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(), model, provider,
                     prompt_toks, comp_toks, latency_ms, failover_used)
                )
                conn.commit()
        except Exception as e:
            logging.warning(f"Usage log write failed: {e}")

    def get_stats(self, last_n: int = 50) -> dict:
        """Returns usage stats for the API endpoint."""
        try:
            with sqlite3.connect(USAGE_DB) as conn:
                # Totals
                row = conn.execute(
                    "SELECT COUNT(*), SUM(prompt_tokens), SUM(completion_tokens), AVG(latency_ms) FROM usage_log"
                ).fetchone()
                total_calls, total_prompt, total_comp, avg_lat = row
                total_calls = total_calls or 0
                total_prompt = total_prompt or 0
                total_comp = total_comp or 0
                avg_lat = round(avg_lat or 0, 1)

                # Per-model breakdown
                by_model = conn.execute(
                    "SELECT model, COUNT(*), SUM(prompt_tokens), SUM(completion_tokens) "
                    "FROM usage_log GROUP BY model ORDER BY COUNT(*) DESC"
                ).fetchall()

                # Recent calls
                recent = conn.execute(
                    "SELECT timestamp, model, provider, prompt_tokens, completion_tokens, latency_ms, failover_used "
                    "FROM usage_log ORDER BY id DESC LIMIT ?", (last_n,)
                ).fetchall()

            return {
                "session": {
                    "calls": self.session_calls,
                    "prompt_tokens": self.session_prompt_tokens,
                    "completion_tokens": self.session_completion_tokens,
                    "total_tokens": self.session_prompt_tokens + self.session_completion_tokens,
                    "started": self.session_start,
                },
                "alltime": {
                    "calls": total_calls,
                    "prompt_tokens": int(total_prompt),
                    "completion_tokens": int(total_comp),
                    "total_tokens": int(total_prompt + total_comp),
                    "avg_latency_ms": avg_lat,
                },
                "by_model": [
                    {
                        "model": r[0], "calls": r[1],
                        "prompt_tokens": r[2] or 0, "completion_tokens": r[3] or 0
                    } for r in by_model
                ],
                "recent": [
                    {
                        "timestamp": r[0], "model": r[1], "provider": r[2],
                        "prompt_tokens": r[3], "completion_tokens": r[4],
                        "latency_ms": r[5], "failover": r[6] or ""
                    } for r in recent
                ],
            }
        except Exception as e:
            logging.warning(f"Usage stats query failed: {e}")
            return {}

    def format_report(self) -> str:
        """Returns a rich-formatted CLI report string."""
        stats = self.get_stats(last_n=10)
        if not stats:
            return "No usage data available yet."

        s = stats.get("session", {})
        a = stats.get("alltime", {})
        lines = [
            "\n[bold cyan]━━━ ViClaw Usage Report ━━━[/bold cyan]",
            f"\n[bold yellow]This session[/bold yellow] (since {s.get('started', '?')[:19]})",
            f"  Calls:      {s.get('calls', 0)}",
            f"  Prompt:     {s.get('prompt_tokens', 0):,} tokens",
            f"  Completion: {s.get('completion_tokens', 0):,} tokens",
            f"  Total:      {s.get('total_tokens', 0):,} tokens",
            f"\n[bold yellow]All-time totals[/bold yellow]",
            f"  Calls:      {a.get('calls', 0):,}",
            f"  Prompt:     {a.get('prompt_tokens', 0):,} tokens",
            f"  Completion: {a.get('completion_tokens', 0):,} tokens",
            f"  Total:      {a.get('total_tokens', 0):,} tokens",
            f"  Avg latency:{a.get('avg_latency_ms', 0):.0f} ms",
        ]

        by_model = stats.get("by_model", [])
        if by_model:
            lines.append("\n[bold yellow]Per-model breakdown[/bold yellow]")
            for m in by_model:
                lines.append(f"  {m['model']:<30} {m['calls']:>4} calls  {(m['prompt_tokens'] or 0) + (m['completion_tokens'] or 0):>8,} tokens")

        recent = stats.get("recent", [])
        if recent:
            lines.append("\n[bold yellow]Last 10 calls[/bold yellow]")
            for r in recent:
                ts = r["timestamp"][:19] if r.get("timestamp") else "?"
                fov = f" [failover→{r['failover']}]" if r.get("failover") else ""
                lines.append(
                    f"  {ts}  {r.get('model','?'):<25} "
                    f"{r.get('prompt_tokens',0)+r.get('completion_tokens',0):>6,} tok  "
                    f"{r.get('latency_ms',0):>4}ms{fov}"
                )
        return "\n".join(lines)

    def clear_history(self):
        """Wipe all usage history from the database."""
        try:
            with sqlite3.connect(USAGE_DB) as conn:
                conn.execute("DELETE FROM usage_log")
                conn.commit()
            self.session_prompt_tokens = 0
            self.session_completion_tokens = 0
            self.session_calls = 0
            logging.info("Usage history cleared.")
        except Exception as e:
            logging.warning(f"Failed to clear usage history: {e}")
