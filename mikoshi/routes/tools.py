import logging

from fastapi import APIRouter, Request

from mikoshi.tools.manager import normalize_tool

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tools")
async def list_tools(request: Request):
    tool_manager = request.app.state.tool_manager

    tool_servers = []
    server_names = await tool_manager.list_tool_servers()

    for server_name in server_names:
        try:
            tools = await tool_manager.list_tools(server_name)
            tool_list = [normalize_tool(tool) for tool in tools]
            tool_servers.append({"name": server_name, "tools": tool_list})
        except Exception as e:
            logger.warning("Could not list tools from server %s: %s", server_name, e)
            continue

    return {"tool_servers": tool_servers}
