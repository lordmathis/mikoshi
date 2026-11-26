import asyncio

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mikoshi.routes.approvals import router as approvals_router
from mikoshi.tools.approval import ToolDeniedError
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool
from tests.conftest import make_tool_manager
from unittest.mock import MagicMock


class _RuleToolset(ToolSetHandler):
    server_name = "danger"

    @tool(
        description="destructive",
        parameters={"type": "object", "properties": {"cmd": {"type": "string"}}},
        require_approval=True,
    )
    async def risky(self, cmd: str = "") -> str:
        return "ran"

    def suggested_rule(self, arguments: dict) -> str | None:
        tokens = arguments.get("cmd", "").split()
        return tokens[0] if tokens else None

    def is_auto_approved(self, arguments: dict, rules: set[str]) -> bool:
        tokens = arguments.get("cmd", "").split()
        return bool(tokens) and tokens[0] in rules


@pytest_asyncio.fixture
async def client_and_manager():
    app = FastAPI()
    app.include_router(approvals_router, prefix="/api")
    tm = await make_tool_manager(_RuleToolset())
    app.state.tool_manager = tm
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, tm


class TestApprovalRoutes:
    @pytest.mark.asyncio
    async def test_approve_once(self, client_and_manager):
        client, tm = client_and_manager
        ctx = ToolCallContext(
            provider=MagicMock(), model_id="m", chat_id="c1"
        )
        task = asyncio.create_task(tm.call_tool("danger__risky", {}, ctx))
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        resp = await client.post(f"/api/approvals/{aid}/approve", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["result"] == "ran"
        await task

        task2 = asyncio.create_task(
            tm.call_tool("danger__risky", {"cmd": "npm run build"}, ctx)
        )
        await asyncio.sleep(0)
        assert len(tm.list_pending_approvals("c1")) == 1
        await tm.deny_tool(tm.list_pending_approvals("c1")[0]["id"])
        with pytest.raises(ToolDeniedError):
            await task2

    @pytest.mark.asyncio
    async def test_approve_with_rule_auto_approves_matching_calls(self, client_and_manager):
        client, tm = client_and_manager
        ctx = ToolCallContext(
            provider=MagicMock(), model_id="m", chat_id="c1"
        )
        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"cmd": "npm run build"}, ctx)
        )
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        resp = await client.post(
            f"/api/approvals/{aid}/approve", json={"rule": "npm"}
        )
        assert resp.status_code == 200
        await task

        result = await tm.call_tool("danger__risky", {"cmd": "npm ci"}, ctx)
        assert result == "ran"
        assert tm.list_pending_approvals("c1") == []

    @pytest.mark.asyncio
    async def test_deny(self, client_and_manager):
        client, tm = client_and_manager
        ctx = ToolCallContext(
            provider=MagicMock(), model_id="m", chat_id="c1"
        )
        task = asyncio.create_task(tm.call_tool("danger__risky", {}, ctx))
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        resp = await client.post(f"/api/approvals/{aid}/deny")
        assert resp.status_code == 200
        assert resp.json()["status"] == "denied"

        with pytest.raises(ToolDeniedError):
            await task

    @pytest.mark.asyncio
    async def test_approve_unknown_returns_404(self, client_and_manager):
        client, tm = client_and_manager
        resp = await client.post(
            "/api/approvals/nope/approve", json={"rule": "npm"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_includes_suggested_rule(self, client_and_manager):
        client, tm = client_and_manager
        ctx = ToolCallContext(
            provider=MagicMock(), model_id="m", chat_id="c1"
        )
        task = asyncio.create_task(
            tm.call_tool("danger__risky", {"cmd": "git status"}, ctx)
        )
        await asyncio.sleep(0)

        resp = await client.get("/api/approvals?chat_id=c1")
        assert resp.status_code == 200
        assert resp.json()["approvals"][0]["rule"] == "git"

        aid = resp.json()["approvals"][0]["id"]
        await client.post(f"/api/approvals/{aid}/approve", json={})
        await task

    @pytest.mark.asyncio
    async def test_list_includes_message_id(self, client_and_manager):
        client, tm = client_and_manager

        async def on_requested(approval_id, tool_name, arguments):
            return "msg-42"

        ctx = ToolCallContext(
            provider=MagicMock(),
            model_id="m",
            chat_id="c1",
            on_approval_requested=on_requested,
        )
        task = asyncio.create_task(tm.call_tool("danger__risky", {}, ctx))
        await asyncio.sleep(0)

        resp = await client.get("/api/approvals?chat_id=c1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["approvals"][0]["message_id"] == "msg-42"

        aid = body["approvals"][0]["id"]
        await client.post(f"/api/approvals/{aid}/approve", json={})
        await task
