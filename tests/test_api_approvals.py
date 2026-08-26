import asyncio

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mikoshi.routes.approvals import router as approvals_router
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool
from tests.conftest import make_tool_manager
from unittest.mock import MagicMock


class _DangerousToolset(ToolSetHandler):
    server_name = "danger"

    @tool(
        description="destructive",
        parameters={"type": "object", "properties": {}},
        require_approval=True,
    )
    async def risky(self) -> str:
        return "ran"


@pytest_asyncio.fixture
async def client_and_manager():
    app = FastAPI()
    app.include_router(approvals_router, prefix="/api")
    tm = await make_tool_manager(_DangerousToolset())
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

        resp = await client.post(
            f"/api/approvals/{aid}/approve", json={"scope": "once"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["result"] == "ran"
        await task
        assert not tm.is_allowed("c1", "danger__risky")

    @pytest.mark.asyncio
    async def test_approve_always_populates_allowlist(self, client_and_manager):
        client, tm = client_and_manager
        ctx = ToolCallContext(
            provider=MagicMock(), model_id="m", chat_id="c1"
        )
        task = asyncio.create_task(tm.call_tool("danger__risky", {}, ctx))
        await asyncio.sleep(0)
        aid = tm.list_pending_approvals("c1")[0]["id"]

        resp = await client.post(
            f"/api/approvals/{aid}/approve", json={"scope": "always"}
        )
        assert resp.status_code == 200
        await task
        assert tm.is_allowed("c1", "danger__risky")

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
        from mikoshi.tools.approval import ToolDeniedError

        with pytest.raises(ToolDeniedError):
            await task

    @pytest.mark.asyncio
    async def test_approve_unknown_returns_404(self, client_and_manager):
        client, tm = client_and_manager
        resp = await client.post(
            "/api/approvals/nope/approve", json={"scope": "once"}
        )
        assert resp.status_code == 404

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
        await client.post(f"/api/approvals/{aid}/approve", json={"scope": "once"})
        await task
