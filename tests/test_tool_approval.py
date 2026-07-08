import asyncio
import inspect

import pytest
from unittest.mock import MagicMock

from mikoshi.db.db import Database
from mikoshi.tools.approval import ToolDeniedError
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.manager import ToolManager
from mikoshi.tools.toolset_handler import ToolDefinition, ToolSetHandler, tool


class _DangerousToolset(ToolSetHandler):
    server_name = "danger"

    @tool(
        description="a destructive tool",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
        require_approval=True,
    )
    async def risky(self, x: int = 0) -> str:
        return f"ran risky with x={x}"


def _ctx(**overrides):
    defaults = dict(provider=MagicMock(), model_id="m", chat_id="c1")
    defaults.update(overrides)
    return ToolCallContext(**defaults)


def _sync_init(handler: ToolSetHandler) -> None:
    """Populate handler._tools without an event loop (for use inside async tests)."""
    for _, method in inspect.getmembers(handler, predicate=inspect.ismethod):
        if not hasattr(method, "_tool_definition"):
            continue
        td = method._tool_definition
        handler._tools[td.name] = ToolDefinition(
            name=td.name,
            description=td.description,
            parameters=td.parameters,
            func=method,
            require_approval=td.require_approval,
        )


def _make_manager(db: Database | None = None) -> ToolManager:
    tm = ToolManager.__new__(ToolManager)
    tm._server_map = {}
    tm._toolset_handlers = {}
    tm._pending_approvals = {}
    tm._chat_allowlist = {}
    tm._db = db

    handler = _DangerousToolset()
    _sync_init(handler)
    tm._toolset_handlers[handler.server_name] = handler
    tm._server_map[handler.server_name] = handler
    return tm


class TestCallToolApproval:
    @pytest.mark.asyncio
    async def test_approve_runs_tool(self, db):
        tm = _make_manager()
        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 1}, _ctx())
        )
        await asyncio.sleep(0)
        approvals = tm.list_pending_approvals("c1")
        assert len(approvals) == 1
        aid = approvals[0]["id"]

        result = await tm.approve_tool(aid)
        assert result == "ran risky with x=1"
        assert await task == "ran risky with x=1"
        assert tm.list_pending_approvals("c1") == []

    @pytest.mark.asyncio
    async def test_deny_raises_tool_denied(self, db):
        tm = _make_manager()
        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 2}, _ctx())
        )
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        await tm.deny_tool(aid)
        with pytest.raises(ToolDeniedError):
            await task
        assert tm.list_pending_approvals("c1") == []

    @pytest.mark.asyncio
    async def test_allowlist_skips_prompt(self, db):
        tm = _make_manager()
        tm.allow("c1", "danger__risky")

        result = await tm.call_tool("danger__risky", {"x": 5}, _ctx())
        assert result == "ran risky with x=5"
        assert tm.list_pending_approvals("c1") == []

    @pytest.mark.asyncio
    async def test_allowlist_is_chat_scoped(self, db):
        tm = _make_manager()
        tm.allow("c1", "danger__risky")

        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 9}, _ctx(chat_id="c2"))
        )
        await asyncio.sleep(0)
        assert len(tm.list_pending_approvals("c2")) == 1
        await tm.deny_tool(tm.list_pending_approvals("c2")[0]["id"])
        with pytest.raises(ToolDeniedError):
            await task

    @pytest.mark.asyncio
    async def test_approve_always_adds_to_allowlist(self, db):
        tm = _make_manager()
        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 7}, _ctx())
        )
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        await tm.approve_tool(aid, scope="always")
        await task
        assert tm.is_allowed("c1", "danger__risky")

    @pytest.mark.asyncio
    async def test_callback_invoked_and_message_id_stored(self, db):
        tm = _make_manager()
        seen = {}

        async def on_requested(approval_id, tool_name, arguments):
            seen["approval_id"] = approval_id
            seen["tool_name"] = tool_name
            seen["arguments"] = arguments
            return "msg-abc"

        task = asyncio.create_task(
            tm.call_tool(
                "danger__risky", {"x": 3}, _ctx(on_approval_requested=on_requested)
            )
        )
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        assert seen["approval_id"] == aid
        assert seen["tool_name"] == "danger__risky"
        assert seen["arguments"] == {"x": 3}
        assert tm._pending_approvals[aid].message_id == "msg-abc"

        await tm.approve_tool(aid)
        await task

    @pytest.mark.asyncio
    async def test_persists_approval_to_db(self, db):
        tm = _make_manager(db)
        chat = db.create_chat()

        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 1}, _ctx(chat_id=chat.id))
        )
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals(chat.id)[0]["id"]

        stored = db.get_approval_by_id(aid)
        assert stored["status"] == "pending"
        assert stored["tool_name"] == "danger__risky"

        await tm.approve_tool(aid)
        await task
        assert db.get_approval_by_id(aid)["status"] == "approved"

    @pytest.mark.asyncio
    async def test_deny_updates_db_status(self, db):
        tm = _make_manager(db)
        chat = db.create_chat()

        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 1}, _ctx(chat_id=chat.id))
        )
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals(chat.id)[0]["id"]

        await tm.deny_tool(aid)
        with pytest.raises(ToolDeniedError):
            await task
        assert db.get_approval_by_id(aid)["status"] == "denied"

    @pytest.mark.asyncio
    async def test_list_pending_filters_by_chat(self, db):
        tm = _make_manager()
        task1 = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 1}, _ctx(chat_id="c1"))
        )
        task2 = asyncio.create_task(
            tm.call_tool("danger__risky", {"x": 2}, _ctx(chat_id="c2"))
        )
        await asyncio.sleep(0)

        assert len(tm.list_pending_approvals("c1")) == 1
        assert len(tm.list_pending_approvals("c2")) == 1

        await tm.approve_tool(tm.list_pending_approvals("c1")[0]["id"])
        await tm.deny_tool(tm.list_pending_approvals("c2")[0]["id"])
        await task1
        with pytest.raises(ToolDeniedError):
            await task2
