import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool


class FakeHandler(ToolSetHandler):
    server_name = "fake"

    @tool(description="echoes input", parameters={"type": "object", "properties": {"msg": {"type": "string"}}})
    def echo(self, msg: str) -> str:
        return msg

    @tool(description="async greet", parameters={"type": "object", "properties": {"name": {"type": "string"}}})
    async def greet(self, name: str) -> str:
        return f"hello {name}"

    @tool(description="uses context", parameters={"type": "object", "properties": {}})
    def with_ctx(self, context: ToolCallContext) -> str:
        return context.chat_id

    def plain_method(self):
        return "not a tool"


def _ctx(**overrides):
    defaults = dict(provider=MagicMock(), model_id="m", chat_id="c1")
    defaults.update(overrides)
    return ToolCallContext(**defaults)


@pytest.fixture
def handler():
    return FakeHandler()


@pytest_asyncio.fixture
async def initialized(handler):
    await handler.initialize()
    return handler


class TestInitialize:
    @pytest.mark.asyncio
    async def test_registers_tool_methods(self, handler):
        await handler.initialize()
        tools = await handler.list_tools()
        names = {t.name for t in tools}
        assert names == {"echo", "greet", "with_ctx"}

    @pytest.mark.asyncio
    async def test_skips_plain_methods(self, handler):
        await handler.initialize()
        tools = await handler.list_tools()
        assert all(t.name != "plain_method" for t in tools)


class TestCallTool:
    @pytest.mark.asyncio
    async def test_calls_tool(self, initialized):
        assert await initialized.call_tool("echo", {"msg": "hi"}, _ctx()) == "hi"
        assert await initialized.call_tool("greet", {"name": "world"}, _ctx()) == "hello world"

    @pytest.mark.asyncio
    async def test_context_injection(self, initialized):
        ctx = _ctx(chat_id="chat-42")
        result = await initialized.call_tool("with_ctx", {}, ctx)
        assert result == "chat-42"

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, initialized):
        with pytest.raises(ValueError, match="not found"):
            await initialized.call_tool("nonexistent", {}, _ctx())


class TestCallOtherTool:
    @pytest.mark.asyncio
    async def test_delegates_to_tool_manager(self, handler):
        mock_tm = MagicMock()
        mock_tm.call_tool = AsyncMock(return_value="result")
        handler._tool_manager = mock_tm
        ctx = _ctx()
        result = await handler.call_other_tool("some_tool", {"a": 1}, ctx)
        mock_tm.call_tool.assert_awaited_once_with("some_tool", {"a": 1}, ctx)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_raises_without_tool_manager(self, handler):
        with pytest.raises(RuntimeError, match="ToolManager not set"):
            await handler.call_other_tool("x", {}, _ctx())


class TestSetToolManager:
    def test_sets_once(self, handler):
        tm1 = MagicMock()
        tm2 = MagicMock()
        handler.set_tool_manager(tm1)
        assert handler._tool_manager is tm1
        handler.set_tool_manager(tm2)
        assert handler._tool_manager is tm1

    def test_get_persistent_storage(self, handler):
        tm = MagicMock()
        tm.get_persistent_storage.return_value = {"key": "val"}
        handler._tool_manager = tm
        assert handler.get_persistent_storage() == {"key": "val"}
        tm.get_persistent_storage.assert_called_once_with("fake")
