from types import SimpleNamespace

import pytest

from mikoshi.tools.builtin.discovery import DiscoveryTools, match_tools
from mikoshi.tools.context import ToolCallContext

CATALOG = [
    {
        "server": "github",
        "name": "create_issue",
        "description": "Create a GitHub issue",
        "parameters": {},
    },
    {
        "server": "github",
        "name": "list_pulls",
        "description": "List pull requests",
        "parameters": {},
    },
    {
        "server": "k8s",
        "name": "rollout",
        "description": "Restart a deployment",
        "parameters": {},
    },
]


def _mcp_tool(name, description, parameters=None):
    return SimpleNamespace(
        name=name,
        description=description,
        input_schema=parameters or {"type": "object", "properties": {}},
    )


class _StubManager:
    def __init__(self, servers):
        self._servers = servers
        self.calls = []

    async def list_tool_servers(self):
        return list(self._servers)

    async def list_tools(self, server_name):
        return self._servers[server_name]

    async def call_tool(self, call_name, arguments, context):
        self.calls.append((call_name, arguments))
        return {"called": call_name}


def _discovery(servers):
    tools = DiscoveryTools()
    tools.set_tool_manager(_StubManager(servers))
    return tools


def _context(upfront=None):
    return ToolCallContext(
        provider=None,
        model_id="m",
        chat_id="c1",
        upfront_tool_servers=upfront or [],
    )


def test_match_tools_requires_every_token_case_insensitive():
    assert match_tools(CATALOG, "GITHUB issue", 8) == [CATALOG[0]]
    assert match_tools(CATALOG, "github issue kubernetes", 8) == []


def test_match_tools_matches_server_name_respects_limit_and_skips_blank_queries():
    assert [e["name"] for e in match_tools(CATALOG, "github", 1)] == ["create_issue"]
    assert match_tools(CATALOG, "   ", 8) == []


@pytest.mark.asyncio
async def test_initialize_registers_search_and_invoke_tools():
    discovery = DiscoveryTools()

    await discovery.initialize()

    assert set(discovery._tools) == {"search_tools", "invoke_tool"}


@pytest.mark.asyncio
async def test_search_tools_excludes_upfront_and_discovery_servers():
    servers = {
        "workspace": [_mcp_tool("read_file", "Read a file")],
        "github": [
            _mcp_tool("create_issue", "Create a GitHub issue", {"type": "object"})
        ],
        "discovery": [_mcp_tool("search_tools", "fake")],
    }
    discovery = _discovery(servers)

    result = await discovery.search_tools(
        "issue", context=_context(upfront=["workspace"])
    )

    assert result["count"] == 1
    entry = result["results"][0]
    assert entry["server"] == "github"
    assert entry["parameters"] == {"type": "object"}


@pytest.mark.asyncio
async def test_search_tools_no_match_returns_available_servers():
    discovery = _discovery(
        {"github": [_mcp_tool("create_issue", "Create a GitHub issue")]}
    )

    result = await discovery.search_tools("zzz nothing", context=_context())

    assert result["results"] == []
    assert result["available_servers"] == ["github"]


@pytest.mark.asyncio
async def test_invoke_tool_calls_manager_with_reconstructed_name():
    stub = _StubManager({"github": [_mcp_tool("create_issue", "x")]})
    discovery = DiscoveryTools()
    discovery.set_tool_manager(stub)
    context = _context()

    result = await discovery.invoke_tool(
        "github", "create_issue", {"title": "t"}, context=context
    )

    assert result == {"called": "github__create_issue"}
    assert stub.calls == [("github__create_issue", {"title": "t"})]


@pytest.mark.asyncio
async def test_invoke_tool_refuses_discovery_itself():
    stub = _StubManager({"discovery": []})
    discovery = DiscoveryTools()
    discovery.set_tool_manager(stub)

    result = await discovery.invoke_tool(
        "discovery", "search_tools", {}, context=_context()
    )

    assert stub.calls == []
    assert "cannot invoke itself" in result


@pytest.mark.asyncio
async def test_invoke_tool_unknown_server_lists_available_servers():
    class _MissingServerManager(_StubManager):
        async def call_tool(self, call_name, arguments, context):
            raise ValueError("Tool server 'nope' not found")

    discovery = DiscoveryTools()
    discovery.set_tool_manager(_MissingServerManager({"github": []}))

    result = await discovery.invoke_tool("nope", "x", {}, context=_context())

    assert "Tool server 'nope' not found" in result
    assert "Available servers: github" in result
