import json
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mikoshi.config import AppConfig
from mikoshi.connectors.client_base import FileNode
from mikoshi.git import GitResult, GitStatus
from mikoshi.routes.workspaces import router as workspaces_router
from mikoshi.workspace import WorkspaceError


class _StubAgentManager:
    def __init__(self):
        self._agents = {}

    def remove(self, chat_id):
        self._agents.pop(chat_id, None)


class _StubWorkspaceService:
    def __init__(self, fail_init=False):
        self._fail_init = fail_init
        self._files = {}

    def initialize_workspace(self, workspace_id, repo_url, connector_name=None):
        if self._fail_init:
            raise WorkspaceError("clone failed")

    def get_workspace_path(self, workspace_id):
        return f"/tmp/workspaces/{workspace_id}"

    def delete_workspace_files(self, workspace_id):
        pass

    def read_file_raw(self, workspace_id, path):
        key = (workspace_id, path)
        if key not in self._files:
            raise WorkspaceError(f"File not found: {path}")
        content, mime = self._files[key]
        return content, mime

    def write_file(self, workspace_id, path, content):
        self._files[(workspace_id, path)] = (content.encode(), "text/plain")

    def delete_file(self, workspace_id, path):
        self._files.pop((workspace_id, path), None)

    def rename_file(self, workspace_id, old_path, new_path):
        key = (workspace_id, old_path)
        if key not in self._files:
            raise WorkspaceError(f"File not found: {old_path}")
        self._files[(workspace_id, new_path)] = self._files.pop(key)
        return new_path

    def get_file_tree(self, workspace_id, path=""):
        return FileNode(path=path, name="", type="dir", children=[])

    def list_files_flat(self, workspace_id):
        return [path for ws, path in self._files if ws == workspace_id]

    def _resolve_connector_token(self, connector_name):
        return None


@pytest_asyncio.fixture
async def client(db, app_config):
    app = FastAPI()
    app.include_router(workspaces_router, prefix="/api")
    app.state.database = db
    app.state.workspace_service = _StubWorkspaceService()
    app.state.agent_manager = _StubAgentManager()
    app.state.app_config = app_config
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _create_workspace_payload(**overrides):
    base = {"name": "test-ws", "repo_url": "https://github.com/org/repo"}
    base.update(overrides)
    return base


class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_create_and_get_roundtrip(self, client, db):
        resp = await client.post("/api/workspaces", json=_create_workspace_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-ws"
        assert data["repo_url"] == "https://github.com/org/repo"
        assert data["id"]

        got = await client.get(f"/api/workspaces/{data['id']}")
        assert got.status_code == 200
        assert got.json()["id"] == data["id"]

    @pytest.mark.asyncio
    async def test_init_failure_rolls_back_db(self, db, app_config):
        app = FastAPI()
        app.include_router(workspaces_router, prefix="/api")
        app.state.database = db
        app.state.workspace_service = _StubWorkspaceService(fail_init=True)
        app.state.agent_manager = _StubAgentManager()
        app.state.app_config = app_config
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/workspaces", json=_create_workspace_payload())
            assert resp.status_code == 400
            assert db.list_workspaces() == []

    @pytest.mark.asyncio
    async def test_create_with_connector(self, client, db):
        resp = await client.post(
            "/api/workspaces",
            json=_create_workspace_payload(connector="github"),
        )
        assert resp.status_code == 200
        assert resp.json()["connector"] == "github"

    @pytest.mark.asyncio
    async def test_create_without_repo_url(self, client, db):
        resp = await client.post(
            "/api/workspaces",
            json={"name": "research-only"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "research-only"
        assert data["repo_url"] is None


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_list_returns_created_workspaces(self, client, db):
        await client.post("/api/workspaces", json=_create_workspace_payload(name="ws1"))
        await client.post("/api/workspaces", json=_create_workspace_payload(name="ws2"))
        resp = await client.get("/api/workspaces")
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()["workspaces"]]
        assert "ws1" in names and "ws2" in names


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_not_found(self, client):
        resp = await client.get("/api/workspaces/nonexistent")
        assert resp.status_code == 404


class TestDeleteWorkspace:
    @pytest.mark.asyncio
    async def test_delete_removes_from_db(self, client, db):
        resp = await client.post("/api/workspaces", json=_create_workspace_payload())
        ws_id = resp.json()["id"]
        del_resp = await client.delete(f"/api/workspaces/{ws_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True
        assert db.get_workspace(ws_id) is None

    @pytest.mark.asyncio
    async def test_delete_cascades_linked_chats(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        chat = db.create_chat(workspace_id=ws.id)
        await client.delete(f"/api/workspaces/{ws.id}")
        assert db.get_chat(chat.id) is None

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        resp = await client.delete("/api/workspaces/nonexistent")
        assert resp.status_code == 404


class TestFileRead:
    @pytest.mark.asyncio
    async def test_text_file_returns_plain_text(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        svc = client._transport.app.state.workspace_service
        svc._files[(ws.id, "readme.md")] = (b"Hello world", "text/markdown")
        resp = await client.get(f"/api/workspaces/{ws.id}/files/readme.md")
        assert resp.status_code == 200
        assert resp.text == "Hello world"
        assert "text/plain" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_binary_file_returns_response_with_media_type(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        svc = client._transport.app.state.workspace_service
        svc._files[(ws.id, "img.png")] = (b"\x89PNG\r\n", "image/png")
        resp = await client.get(f"/api/workspaces/{ws.id}/files/img.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    @pytest.mark.asyncio
    async def test_json_file_returns_plain_text(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        svc = client._transport.app.state.workspace_service
        svc._files[(ws.id, "data.json")] = (b'{"key": 1}', "application/json")
        resp = await client.get(f"/api/workspaces/{ws.id}/files/data.json")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]


class TestFileWrite:
    @pytest.mark.asyncio
    async def test_write_file(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        resp = await client.put(
            f"/api/workspaces/{ws.id}/files/test.txt",
            json={"content": "hello"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestFileDelete:
    @pytest.mark.asyncio
    async def test_delete_file(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        svc = client._transport.app.state.workspace_service
        svc._files[(ws.id, "del.txt")] = (b"x", "text/plain")
        resp = await client.delete(f"/api/workspaces/{ws.id}/files/del.txt")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestFileRename:
    @pytest.mark.asyncio
    async def test_rename_returns_new_path(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        svc = client._transport.app.state.workspace_service
        svc._files[(ws.id, "old.txt")] = (b"x", "text/plain")
        resp = await client.patch(
            f"/api/workspaces/{ws.id}/files/old.txt",
            json={"new_path": "new.txt"},
        )
        assert resp.status_code == 200
        assert resp.json()["new_path"] == "new.txt"


class TestFileTree:
    @pytest.mark.asyncio
    async def test_returns_tree(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        resp = await client.get(f"/api/workspaces/{ws.id}/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "dir"


class TestListFiles:
    @pytest.mark.asyncio
    async def test_returns_files_list(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        svc = client._transport.app.state.workspace_service
        svc._files[(ws.id, "a.txt")] = (b"a", "text/plain")
        svc._files[(ws.id, "b.txt")] = (b"b", "text/plain")
        resp = await client.get(f"/api/workspaces/{ws.id}/ls")
        assert resp.status_code == 200
        assert "a.txt" in resp.json()["files"]


class TestGitEndpoints:
    @pytest.mark.asyncio
    async def test_git_status(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        mock_status = GitStatus(branch="main", staged=1, unstaged=0, untracked=2)
        with patch("mikoshi.routes.workspaces.GitService") as MockGit:
            MockGit.return_value.status.return_value = mock_status
            resp = await client.get(f"/api/workspaces/{ws.id}/git/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch"] == "main"
        assert data["staged"] == 1
        assert data["untracked"] == 2

    @pytest.mark.asyncio
    async def test_git_commit_uses_app_config(self, client, db, app_config):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        mock_result = GitResult(success=True, output="committed")
        with patch("mikoshi.routes.workspaces.GitService") as MockGit:
            MockGit.return_value.commit.return_value = mock_result
            resp = await client.post(
                f"/api/workspaces/{ws.id}/git/commit",
                json={"message": "initial"},
            )
            MockGit.return_value.commit.assert_called_once_with(
                "initial",
                app_config.workspace.git_user_name,
                app_config.workspace.git_user_email,
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_git_pull(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        mock_result = GitResult(success=True, output="already up to date")
        with patch("mikoshi.routes.workspaces.GitService") as MockGit:
            MockGit.return_value.pull.return_value = mock_result
            resp = await client.post(f"/api/workspaces/{ws.id}/git/pull")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["output"] == "already up to date"

    @pytest.mark.asyncio
    async def test_git_push(self, client, db):
        ws = db.create_workspace(name="ws", repo_url="https://x.com/repo")
        mock_result = GitResult(success=False, output="rejected")
        with patch("mikoshi.routes.workspaces.GitService") as MockGit:
            MockGit.return_value.push.return_value = mock_result
            resp = await client.post(f"/api/workspaces/{ws.id}/git/push")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_git_not_found_workspace(self, client):
        resp = await client.get("/api/workspaces/nonexistent/git/status")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_git_status_rejected_without_repo(self, client, db):
        ws = db.create_workspace(name="ws")
        resp = await client.get(f"/api/workspaces/{ws.id}/git/status")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_git_commit_rejected_without_repo(self, client, db):
        ws = db.create_workspace(name="ws")
        resp = await client.post(
            f"/api/workspaces/{ws.id}/git/commit",
            json={"message": "msg"},
        )
        assert resp.status_code == 400
