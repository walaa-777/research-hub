"""
Standalone MCP server exposing web_search / fetch_page / domain_lookup as MCP tools
for any MCP client (Claude Desktop, the `mcp` inspector, etc).

The pipeline itself does NOT talk to this process -- it calls the identical logic
in-process via app/tools/*.py to avoid stdio/subprocess overhead on the hot path.
See docs/write-up.md 3.4 for the reasoning. This file exists purely so the same
tools are usable outside this project too.

Run: python -m app.mcp_servers.web_search_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.tools.domain_lookup import domain_lookup
from app.tools.fetch_page import fetch_page
from app.tools.web_search import web_search

mcp = FastMCP("research-hub-web-search")


@mcp.tool()
def search(query: str, n: int = 5) -> list[dict]:
    """Search the web and return [{url, title, snippet}, ...]."""
    return web_search(query, n=n)


@mcp.tool()
def fetch(url: str) -> str:
    """Fetch and extract readable text content from a URL."""
    return fetch_page(url)


@mcp.tool()
def domain_credibility(url: str) -> dict:
    """Return a cheap offline credibility signal for a URL's domain."""
    return domain_lookup(url)


if __name__ == "__main__":
    mcp.run(transport="stdio")
