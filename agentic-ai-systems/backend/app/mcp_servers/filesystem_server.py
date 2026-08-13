"""
Standalone MCP server exposing sandboxed report read/write/exists as MCP tools.
Same in-process-vs-MCP split as web_search_server.py -- see its docstring.

Run: python -m app.mcp_servers.filesystem_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.tools.fs_tools import fs_exists, fs_read, fs_write

mcp = FastMCP("research-hub-filesystem")


@mcp.tool()
def write_report(relative_path: str, content: str) -> str:
    """Write `content` to reports/<relative_path>, sandboxed to the reports dir."""
    return fs_write(relative_path, content)


@mcp.tool()
def read_report(relative_path: str) -> str:
    """Read a previously saved report."""
    return fs_read(relative_path)


@mcp.tool()
def report_exists(relative_path: str) -> bool:
    """Check whether a report path already exists (used before an overwrite)."""
    return fs_exists(relative_path)


if __name__ == "__main__":
    mcp.run(transport="stdio")
