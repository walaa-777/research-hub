"""
Filesystem tools used by the pipeline to save a finished report, and exposed as
MCP tools by app/mcp_servers/filesystem_server.py for any external MCP client.

Writes are sandboxed to REPORTS_DIR so an LLM-driven path can never escape it.
"""
from __future__ import annotations

import os
from pathlib import Path

REPORTS_DIR = Path(os.environ.get("RESEARCH_HUB_REPORTS_DIR", "../reports")).resolve()
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_path(relative_path: str) -> Path:
    candidate = (REPORTS_DIR / relative_path).resolve()
    if not str(candidate).startswith(str(REPORTS_DIR)):
        raise ValueError(f"Refusing to write outside reports dir: {relative_path}")
    return candidate


def fs_exists(relative_path: str) -> bool:
    return _safe_path(relative_path).exists()


def fs_write(relative_path: str, content: str) -> str:
    path = _safe_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def fs_read(relative_path: str) -> str:
    return _safe_path(relative_path).read_text(encoding="utf-8")
