"""Discovery tool server: lets the model find and call tools from servers
that are not loaded into the tool array upfront."""

import logging
from typing import Any, Dict, List, Optional, Set

from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.handler_base import normalize_tool
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)


def match_tools(
    catalog: List[Dict[str, Any]], query: str, limit: int
) -> List[Dict[str, Any]]:
    tokens = [t for t in query.lower().split() if t]
    if not tokens:
        return []
    matched = []
    for entry in catalog:
        haystack = f"{entry['server']} {entry['name']} {entry['description']}".lower()
        if all(token in haystack for token in tokens):
            matched.append(entry)
            if len(matched) >= limit:
                break
    return matched


class DiscoveryTools(ToolSetHandler):
    server_name = "discovery"

    async def _catalog(self, upfront: Set[str]) -> List[Dict[str, Any]]:
        catalog = []
        for server_name in await self._tool_manager.list_tool_servers():
            if server_name in upfront or server_name == self.server_name:
                continue
            try:
                tools = await self._tool_manager.list_tools(server_name)
            except Exception as e:
                logger.warning(
                    "discovery: cannot list tools from server '%s': %s", server_name, e
                )
                continue
            for t in tools:
                n = normalize_tool(t)
                catalog.append(
                    {
                        "server": server_name,
                        "name": n["name"],
                        "description": n["description"],
                        "parameters": n["parameters"],
                    }
                )
        return catalog

    @tool(
        description=(
            "Search for tools that are not in your current tool list. Use this "
            "when a task needs a capability you don't have. Returns each match's "
            "server, tool name, description and full JSON parameter schema. "
            "Execute a match with discovery__invoke_tool."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Space-separated keywords describing the capability, e.g. 'github create issue'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max matches to return (default 8).",
                },
            },
            "required": ["query"],
        },
    )
    async def search_tools(
        self, query: str, limit: int = 8, context: Optional[ToolCallContext] = None
    ) -> Any:
        if not self._tool_manager:
            return "Error: discovery is not initialized."
        upfront = set(
            self._tool_manager.get_chat_tool_servers(context.chat_id)
            if context
            else []
        )
        catalog = await self._catalog(upfront)
        results = match_tools(catalog, query, max(1, min(int(limit or 8), 25)))
        logger.info(
            "discovery search query=%r matches=%d catalog=%d chat_id=%s",
            query,
            len(results),
            len(catalog),
            context.chat_id if context else "?",
        )
        if not results:
            return {
                "results": [],
                "available_servers": sorted({e["server"] for e in catalog}),
            }
        return {"results": results, "count": len(results)}

    @tool(
        description=(
            "Invoke a tool found via discovery__search_tools. Pass server and tool "
            "exactly as returned by the search, with arguments matching the "
            "returned JSON schema."
        ),
        parameters={
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Tool server name from the search result.",
                },
                "tool": {
                    "type": "string",
                    "description": "Tool name from the search result.",
                },
                "arguments": {
                    "type": "object",
                    "description": "Arguments matching the tool's schema from the search result.",
                },
            },
            "required": ["server", "tool", "arguments"],
        },
    )
    async def invoke_tool(
        self,
        server: str,
        tool: str,
        arguments: dict,
        context: Optional[ToolCallContext] = None,
    ) -> Any:
        if server == self.server_name:
            return "Error: the discovery server cannot invoke itself."
        call_name = f"{server}__{tool}"
        logger.info(
            "discovery invoke %s chat_id=%s",
            call_name,
            context.chat_id if context else "?",
        )
        try:
            return await self.call_other_tool(call_name, arguments or {}, context)
        except ValueError as e:
            servers = (
                await self._tool_manager.list_tool_servers()
                if self._tool_manager
                else []
            )
            return f"Error: {e}. Available servers: {', '.join(servers)}"
