from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from mcp.types import Tool

from mikoshi.agents.structured import StructuredAgent
from mikoshi.routes.tools import router as tools_router
from mikoshi.tools.manager import normalize_tool
from mikoshi.tools.toolset_handler import ToolDefinition

_MCP_SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}}


def _mcp_tool():
    return Tool(
        name="echo", description="Echo a message", inputSchema=_MCP_SCHEMA
    )


class TestNormalizeTool:
    def test_mcp_tool_uses_inputschema(self):
        result = normalize_tool(_mcp_tool())
        assert result == {
            "name": "echo",
            "description": "Echo a message",
            "parameters": _MCP_SCHEMA,
        }

    def test_toolset_definition_uses_parameters(self):
        def fn(x: int = 0): ...

        td = ToolDefinition(
            name="fn", description="d", parameters={"type": "object"}, func=fn
        )
        result = normalize_tool(td)
        assert result["parameters"] == {"type": "object"}
        assert result["name"] == "fn"

    def test_missing_schema_defaults_to_empty(self):
        result = normalize_tool(SimpleNamespace(name="n", description=None))
        assert result == {"name": "n", "description": "", "parameters": {}}


class _FakeProvider:
    def get_llm_client(self):
        return MagicMock()


class TestGetTools:
    @pytest.mark.asyncio
    async def test_agent_advertises_mcp_inputschema(self):
        tm = MagicMock()
        tm.list_tools = AsyncMock(return_value=[_mcp_tool()])
        agent = StructuredAgent(
            chat_id="c1",
            db=MagicMock(),
            provider=_FakeProvider(),
            tool_manager=tm,
            model_id="m",
            data_dir="/tmp",
        )

        tools = await agent._get_tools(["mcpserver"])

        assert tools == [
            {
                "type": "function",
                "function": {
                    "name": "mcpserver__echo",
                    "description": "Echo a message",
                    "parameters": _MCP_SCHEMA,
                },
            }
        ]


class TestToolsRoute:
    @pytest.mark.asyncio
    async def test_route_advertises_mcp_inputschema(self):
        app = FastAPI()
        app.include_router(tools_router, prefix="/api")
        tm = MagicMock()
        tm.list_tool_servers = AsyncMock(return_value=["mcpserver"])
        tm.list_tools = AsyncMock(return_value=[_mcp_tool()])
        app.state.tool_manager = tm

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/tools")

        body = resp.json()
        assert body["tool_servers"][0]["tools"][0]["parameters"] == _MCP_SCHEMA
