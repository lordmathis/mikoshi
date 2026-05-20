import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mikoshi.agents.streaming import StreamEvent
from mikoshi.routes.chats import router as chats_router


def _chat_config(**overrides):
    base = {"model": "openai:gpt-4", "system_prompt": "You are helpful."}
    base.update(overrides)
    return base


class _StubAgent:
    def __init__(self, events=None, error=None):
        self._events = events or []
        self._error = error

    async def chat(self, message, queue, file_ids=None):
        if self._error:
            raise self._error
        for e in self._events:
            await queue.put(e)

    async def retry(self, queue):
        if self._error:
            raise self._error
        for e in self._events:
            await queue.put(e)

    async def edit(self, new_message, queue):
        if self._error:
            raise self._error
        for e in self._events:
            await queue.put(e)


class _StubAgentManager:
    def __init__(self, db):
        self._db = db
        self._agents = {}

    def create(self, chat_id, config):
        self._agents[chat_id] = _StubAgent()
        self._db.save_chat_config(
            chat_id=chat_id,
            model=config.get("model", ""),
            system_prompt=config.get("system_prompt"),
            tool_servers=config.get("tool_servers") or [],
            model_params=config.get("model_params") or {},
        )

    def get(self, chat_id):
        if chat_id not in self._agents:
            raise ValueError(f"Chat '{chat_id}' not found")
        return self._agents[chat_id]

    def remove(self, chat_id):
        self._agents.pop(chat_id, None)


@pytest_asyncio.fixture
async def client(db):
    app = FastAPI()
    app.include_router(chats_router, prefix="/api")
    app.state.database = db
    app.state.agent_manager = _StubAgentManager(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _parse_sse(text):
    events = []
    for chunk in text.strip().split("\n\n"):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


class TestCreateChat:
    @pytest.mark.asyncio
    async def test_create_and_get_roundtrip(self, client, db):
        resp = await client.post("/api/chats", json={"config": _chat_config()})
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "openai:gpt-4"
        assert data["title"] == "Untitled Chat"
        assert data["system_prompt"] == "You are helpful."
        assert data["id"]

        got = await client.get(f"/api/chats/{data['id']}")
        assert got.status_code == 200
        assert got.json()["id"] == data["id"]
        assert got.json()["model"] == "openai:gpt-4"

    @pytest.mark.asyncio
    async def test_create_with_custom_title_and_workspace(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        resp = await client.post(
            "/api/chats",
            json={"config": _chat_config(), "title": "My Chat", "workspace_id": ws.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "My Chat"
        assert body["workspace_id"] == ws.id

    @pytest.mark.asyncio
    async def test_agent_failure_rolls_back_db(self, db):
        app = FastAPI()
        app.include_router(chats_router, prefix="/api")
        app.state.database = db
        mgr = _StubAgentManager(db)
        mgr.create = lambda chat_id, config: (_ for _ in ()).throw(ValueError("bad provider"))
        app.state.agent_manager = mgr
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/chats", json={"config": _chat_config()})
            assert resp.status_code == 400
            assert "bad provider" in resp.json()["detail"]
            assert db.list_chats() == []


class TestListChats:
    @pytest.mark.asyncio
    async def test_list_returns_created_chats(self, client, db):
        await client.post("/api/chats", json={"config": _chat_config(), "title": "A"})
        await client.post("/api/chats", json={"config": _chat_config(), "title": "B"})
        resp = await client.get("/api/chats")
        assert resp.status_code == 200
        titles = [c["title"] for c in resp.json()["chats"]]
        assert "A" in titles and "B" in titles


class TestGetChat:
    @pytest.mark.asyncio
    async def test_not_found(self, client):
        resp = await client.get("/api/chats/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_includes_messages_with_files(self, client, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        f = db.create_file(filename="doc.txt", file_path="doc.txt", content_type="text/plain")
        db.save_message(
            chat.id, role="user", content="hello",
            file_ids=json.dumps([f.id]),
        )
        resp = await client.get(f"/api/chats/{chat.id}")
        assert resp.status_code == 200
        msgs = resp.json()["messages"]
        assert len(msgs) == 1
        assert msgs[0]["files"][0]["filename"] == "doc.txt"


class TestDeleteChat:
    @pytest.mark.asyncio
    async def test_delete_removes_from_db(self, client, db):
        resp = await client.post("/api/chats", json={"config": _chat_config()})
        chat_id = resp.json()["id"]
        del_resp = await client.delete(f"/api/chats/{chat_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True
        assert db.get_chat(chat_id) is None

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        resp = await client.delete("/api/chats/nonexistent")
        assert resp.status_code == 404


class TestUpdateChat:
    @pytest.mark.asyncio
    async def test_update_title(self, client, db):
        resp = await client.post("/api/chats", json={"config": _chat_config()})
        chat_id = resp.json()["id"]
        patched = await client.patch(f"/api/chats/{chat_id}", json={"title": "Renamed"})
        assert patched.status_code == 200
        assert patched.json()["title"] == "Renamed"

    @pytest.mark.asyncio
    async def test_update_config_recreates_agent(self, client, db):
        resp = await client.post("/api/chats", json={"config": _chat_config()})
        chat_id = resp.json()["id"]
        patched = await client.patch(
            f"/api/chats/{chat_id}",
            json={"config": _chat_config(model="anthropic:claude-3", system_prompt="new")},
        )
        assert patched.status_code == 200
        assert patched.json()["model"] == "anthropic:claude-3"

    @pytest.mark.asyncio
    async def test_update_config_bad_agent_returns_400(self, db):
        app = FastAPI()
        app.include_router(chats_router, prefix="/api")
        app.state.database = db
        mgr = _StubAgentManager(db)
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        mgr._agents[chat.id] = _StubAgent()
        mgr.create = lambda chat_id, config: (_ for _ in ()).throw(ValueError("nope"))
        app.state.agent_manager = mgr
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/chats/{chat.id}", json={"config": _chat_config()}
            )
            assert resp.status_code == 400


class TestBranchChat:
    @pytest.mark.asyncio
    async def test_branch_creates_new_chat_with_messages(self, client, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        msg = db.save_message(chat.id, role="user", content="hello")
        resp = await client.post(
            f"/api/chats/{chat.id}/branch",
            json={"message_id": msg.id, "title": "Branched"},
        )
        assert resp.status_code == 200
        branched = resp.json()
        assert branched["id"] != chat.id
        assert branched["title"] == "Branched"
        assert len(branched["messages"]) == 1
        assert branched["messages"][0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        resp = await client.post(
            "/api/chats/nonexistent/branch", json={"message_id": "x"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_bad_message_returns_400(self, client, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        resp = await client.post(
            f"/api/chats/{chat.id}/branch", json={"message_id": "nonexistent"}
        )
        assert resp.status_code == 400


class TestSSEStreaming:
    @pytest.mark.asyncio
    async def test_send_message_streams_events_then_done(self, client, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        client._transport.app.state.agent_manager._agents[chat.id] = _StubAgent(
            events=[StreamEvent(type="text", data={"content": "hi"})]
        )
        resp = await client.post(
            f"/api/chats/{chat.id}/messages", json={"message": "hello"}
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        types = [e["type"] for e in events]
        assert "text" in types
        assert "done" in types
        assert events[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_agent_not_found_returns_404(self, client):
        resp = await client.post(
            "/api/chats/nonexistent/messages", json={"message": "hi"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_agent_error_pushes_error_event_before_done(self, db):
        app = FastAPI()
        app.include_router(chats_router, prefix="/api")
        app.state.database = db
        mgr = _StubAgentManager(db)
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        mgr._agents[chat.id] = _StubAgent(error=RuntimeError("boom"))
        app.state.agent_manager = mgr
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/chats/{chat.id}/messages", json={"message": "go"}
            )
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            types = [e["type"] for e in events]
            assert "error" in types
            assert types[-1] == "done"

    @pytest.mark.asyncio
    async def test_retry_streams_events(self, client, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        client._transport.app.state.agent_manager._agents[chat.id] = _StubAgent(
            events=[StreamEvent(type="text", data={"content": "retry"})]
        )
        resp = await client.post(f"/api/chats/{chat.id}/retry")
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_edit_streams_events(self, client, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="openai:gpt-4")
        client._transport.app.state.agent_manager._agents[chat.id] = _StubAgent(
            events=[StreamEvent(type="text", data={"content": "edited"})]
        )
        resp = await client.post(
            f"/api/chats/{chat.id}/edit", json={"message": "fixed"}
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events[-1]["type"] == "done"
