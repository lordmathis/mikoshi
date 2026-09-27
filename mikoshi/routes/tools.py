import asyncio
import logging

from fastapi import APIRouter, Request

from mikoshi.tools.manager import normalize_tool

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tools")
async def list_tools(request: Request):
    # Tool servers are fixed at startup (loading a new one requires a
    # restart), so the listing never changes over the server's lifetime.
    cached = getattr(request.app.state, "tools_cache", None)
    if cached is not None:
        return cached

    tool_manager = request.app.state.tool_manager
    server_names = await tool_manager.list_tool_servers()

    async def tools_for(server_name):
        try:
            tools = await tool_manager.list_tools(server_name)
            return {"name": server_name, "tools": [normalize_tool(t) for t in tools]}
        except Exception as e:
            logger.warning("Could not list tools from server %s: %s", server_name, e)
            return None

    results = await asyncio.gather(*(tools_for(name) for name in server_names))

    result = {"tool_servers": [r for r in results if r is not None]}
    request.app.state.tools_cache = result
    return result
