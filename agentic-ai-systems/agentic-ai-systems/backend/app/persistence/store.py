"""
Cross-thread long-term memory Store.

Separate from the checkpointer on purpose: checkpoints are per-thread conversation
state (resumable, ephemeral-ish); the Store is durable, cross-thread memory -- e.g.
"this user already told us they prefer primary sources over blogs" -- that should
survive into a brand-new research thread. Namespaced (user_id, "preferences" | "past_queries").
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any

DB_PATH = os.environ.get("RESEARCH_HUB_DB_PATH", "./research_hub.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS long_term_store (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (namespace, key)
);
"""


class SqliteStore:
    """Minimal BaseStore-shaped implementation: put / get / search, namespaced."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_SCHEMA)

    def put(self, namespace: tuple[str, ...], key: str, value: dict[str, Any]) -> None:
        ns = "/".join(namespace)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO long_term_store (namespace, key, value, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (ns, key, json.dumps(value), time.time()),
            )

    def get(self, namespace: tuple[str, ...], key: str) -> dict[str, Any] | None:
        ns = "/".join(namespace)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT value FROM long_term_store WHERE namespace=? AND key=?", (ns, key)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, Any]]:
        ns = "/".join(namespace)
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT key, value FROM long_term_store WHERE namespace=? ORDER BY updated_at DESC",
                (ns,),
            ).fetchall()
        return [{"key": k, **json.loads(v)} for k, v in rows]


_store_singleton: SqliteStore | None = None


def get_store() -> SqliteStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = SqliteStore()
    return _store_singleton
