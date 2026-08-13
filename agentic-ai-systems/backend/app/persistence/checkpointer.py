"""
Per-thread short-term persistence: wraps langgraph's SqliteSaver so pipeline.py's
@entrypoint can resume a thread after an interrupt() (or after a process restart)
without the caller knowing anything about SQLite.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("RESEARCH_HUB_DB_PATH", "./research_hub.sqlite3")


@contextmanager
def get_checkpointer():
    """
    Yields a langgraph BaseCheckpointSaver backed by SQLite.

    Import is local (not top-level) so `python -m app.mcp_servers.*` and other
    entry points that don't need the checkpointer don't pay for langgraph's
    sqlite extra unless they use it.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        saver = SqliteSaver(conn)
        saver.setup()
        yield saver
    finally:
        conn.close()


def list_threads() -> list[str]:
    """Used by GET /api/threads. Reads checkpoint thread ids directly for a light,
    read-only listing without opening a full LangGraph saver."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
        )
        return [row[0] for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
