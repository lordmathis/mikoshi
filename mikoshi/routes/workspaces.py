import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from mikoshi.routes.schemas import format_timestamp, serialize_chat
from mikoshi.workspace import WorkspaceError

router = APIRouter(prefix="/workspaces")
logger = logging.getLogger(__name__)


class CreateWorkspaceRequest(BaseModel):
    name: str
    repo_url: str
    connector: Optional[str] = None


class WriteFileRequest(BaseModel):
    content: str


class RenameFileRequest(BaseModel):
    new_path: str


def _serialize_workspace(workspace) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "repo_url": workspace.repo_url,
        "connector": workspace.connector,
        "created_at": format_timestamp(workspace.created_at),
        "updated_at": format_timestamp(workspace.updated_at),
    }


def _get_workspace_service(request: Request):
    service = getattr(request.app.state, "workspace_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="Workspace service not available")
    return service


def _require_workspace(database, workspace_id):
    workspace = database.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.post("")
async def create_workspace(request: Request, body: CreateWorkspaceRequest):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)

    workspace = database.create_workspace(
        name=body.name, repo_url=body.repo_url, connector=body.connector
    )

    try:
        workspace_service.initialize_workspace(
            workspace_id=workspace.id,
            repo_url=workspace.repo_url,
            connector_name=workspace.connector,
        )
    except WorkspaceError as e:
        database.delete_workspace(workspace.id)
        raise HTTPException(status_code=400, detail=str(e))

    updated = database.get_workspace(workspace.id)
    return _serialize_workspace(updated)


@router.get("")
async def list_workspaces(request: Request):
    database = request.app.state.database
    workspaces = database.list_workspaces()
    return {"workspaces": [_serialize_workspace(w) for w in workspaces]}


@router.get("/{workspace_id}")
async def get_workspace(request: Request, workspace_id: str):
    database = request.app.state.database
    workspace = _require_workspace(database, workspace_id)
    return _serialize_workspace(workspace)


@router.get("/{workspace_id}/tree")
async def get_workspace_tree(request: Request, workspace_id: str, path: str = ""):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    tree = workspace_service.get_file_tree(workspace_id, path)
    return tree.model_dump()


@router.get("/{workspace_id}/files/{path:path}")
async def get_workspace_file(request: Request, workspace_id: str, path: str):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    content, mime_type = workspace_service.read_file_raw(workspace_id, path)
    if mime_type.startswith("text/") or mime_type in (
        "application/json",
        "application/javascript",
        "application/xml",
    ):
        return PlainTextResponse(content.decode("utf-8", errors="replace"))
    return Response(content=content, media_type=mime_type)


@router.put("/{workspace_id}/files/{path:path}")
async def write_workspace_file(request: Request, workspace_id: str, path: str, body: WriteFileRequest):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    try:
        workspace_service.write_file(workspace_id, path, body.content)
    except WorkspaceError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True}


@router.post("/{workspace_id}/files/{path:path}")
async def create_workspace_file(request: Request, workspace_id: str, path: str, body: WriteFileRequest):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    try:
        workspace_service.write_file(workspace_id, path, body.content)
    except WorkspaceError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True}


@router.delete("/{workspace_id}/files/{path:path}")
async def delete_workspace_file(request: Request, workspace_id: str, path: str):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    try:
        workspace_service.delete_file(workspace_id, path)
    except WorkspaceError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True}


@router.patch("/{workspace_id}/files/{path:path}")
async def rename_workspace_file(request: Request, workspace_id: str, path: str, body: RenameFileRequest):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    try:
        new_path = workspace_service.rename_file(workspace_id, path, body.new_path)
    except WorkspaceError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, "new_path": new_path}


@router.get("/{workspace_id}/ls")
async def list_workspace_files(request: Request, workspace_id: str):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    _require_workspace(database, workspace_id)

    files = workspace_service.list_files_flat(workspace_id)
    return {"files": files}


@router.delete("/{workspace_id}")
async def delete_workspace(request: Request, workspace_id: str):
    database = request.app.state.database
    workspace_service = _get_workspace_service(request)
    agent_manager = request.app.state.agent_manager
    _require_workspace(database, workspace_id)

    database.delete_chats_by_workspace(workspace_id, agent_manager)
    workspace_service.delete_workspace_files(workspace_id)
    database.delete_workspace(workspace_id)

    return {"success": True}
