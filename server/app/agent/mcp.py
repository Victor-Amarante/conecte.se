"""Optional MCP tool loading.

External tools are declared in a JSON file (``mcp_servers.json`` by default)
using the shape ``langchain-mcp-adapters`` expects::

    {
      "servers": {
        "clima": {"transport": "stdio", "command": "uvx", "args": ["mcp-weather"]},
        "gtfs":  {"transport": "streamable_http", "url": "https://example/mcp"}
      }
    }

This is the seam that lets new capabilities be attached without touching the
graph. Failures here are never fatal — the agent falls back to its built-in
tools, because a misconfigured side tool must not take the assistant down.
"""

import json
from pathlib import Path

from langchain_core.tools import BaseTool
from loguru import logger

from app.core.config import settings


async def load_mcp_tools(config_path: Path | None = None) -> list[BaseTool]:
    path = config_path or settings.mcp_config_path
    if not path.exists():
        logger.debug(f"No MCP config at {path}; skipping external tools")
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"Could not read MCP config at {path}: {exc}")
        return []

    servers = raw.get("servers") or raw.get("mcpServers") or {}
    if not servers:
        logger.info(f"MCP config at {path} declares no servers")
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
    except Exception as exc:
        logger.error(f"Failed to load MCP tools: {exc}")
        return []

    logger.info(
        f"Loaded {len(tools)} MCP tool(s) from {len(servers)} server(s): "
        f"{[t.name for t in tools]}"
    )
    return tools
