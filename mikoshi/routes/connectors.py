import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mikoshi.db.db import Database
from mikoshi.routes.schemas import FileResponse
from mikoshi.routes.upload_utils import save_upload_file

router = APIRouter(prefix="/connectors")
logger = logging.getLogger(__name__)


class EstimateTokensRequest(BaseModel):
    repo: str
    paths: List[str]
    exclude_paths: Optional[List[str]] = None


class Connector(BaseModel):
    name: str
    type: str


class FilesRequest(BaseModel):
    repo: str
    paths: List[str]
    exclude_paths: Optional[List[str]] = None


def _get_connector(request: Request, name: str):
    connector_registry = getattr(request.app.state, "connector_registry", None)

    if not connector_registry:
        raise HTTPException(
            status_code=503,
            detail="Connector registry is not configured.",
        )

    connector = connector_registry.get_connector(name)

    if not connector:
        raise HTTPException(
            status_code=404,
            detail=f"Connector '{name}' not found.",
        )

    return connector


@router.get("")
async def list_connectors(request: Request):
    """List all registered connectors."""
    connector_registry = getattr(request.app.state, "connector_registry", None)
    if not connector_registry:
        return {"connectors": []}

    connectors = connector_registry.list_connectors()
    return {
        "connectors": [
            Connector(name=name, type=client.type)
            for name, client in connectors.items()
        ]
    }


@router.get("/repositories")
async def list_repositories(request: Request, connector: str):
    """
    List repositories accessible with the configured credentials.

    Query parameters:
    - connector: Connector name
    """
    client = _get_connector(request, connector)

    try:
        repos = await client.list_repositories()
        return {"repositories": repos}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list repositories: {str(e)}"
        )


@router.get("/tree")
async def browse_tree(request: Request, connector: str, repo: str, path: str = ""):
    """
    Browse the file tree of a repository.

    Query parameters:
    - connector: Connector name
    - repo: Repository identifier
    - path: Path within the repository (empty for root)
    """
    client = _get_connector(request, connector)

    try:
        tree = await client.browse_tree(repo, path)
        return tree.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to browse tree: {str(e)}")


@router.post("/estimate")
async def estimate_tokens(
    request: Request, connector: str, body: EstimateTokensRequest
):
    """
    Estimate token count for files from a repository.
    Supports both individual files and directories (which are expanded recursively).
    Optionally exclude specific paths.

    Query parameters:
    - connector: Connector name

    Body:
    - repo: Repository identifier
    - paths: List of paths to estimate
    - exclude_paths: Optional list of paths to exclude
    """
    client = _get_connector(request, connector)

    try:
        logger.info(
            f"Estimating tokens for repo={body.repo}, paths={body.paths}, exclude={body.exclude_paths}"
        )

        all_file_paths = await _expand_paths_to_files(
            client, body.repo, body.paths, body.exclude_paths or []
        )

        logger.info(
            f"Expanded to {len(all_file_paths)} files: {all_file_paths[:10]}..."
        )

        if not all_file_paths:
            return {"total_tokens": 0, "files": {}}

        estimate = await client.estimate_tokens(body.repo, all_file_paths)
        logger.info(f"Token estimate: {estimate.total_tokens}")
        return estimate.model_dump()
    except Exception as e:
        logger.error(f"Failed to estimate tokens: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to estimate tokens: {str(e)}"
        )


@router.post("/files", response_model=List[FileResponse])
async def fetch_repository_files(request: Request, connector: str, body: FilesRequest):
    """Fetch files from repository server-side, store to disk, and return their metadata."""
    client = _get_connector(request, connector)

    try:
        file_paths = await _expand_paths_to_files(
            client, body.repo, body.paths, body.exclude_paths or []
        )
    except Exception as e:
        logger.error(f"Failed to expand repository paths: {e}")
        raise HTTPException(
            status_code=400, detail=f"Failed to expand repository paths: {e}"
        )

    db: Database = request.app.state.database
    source_str = f"{client.type}:{body.repo}"
    result = []
    for path in file_paths:
        try:
            content = await client.get_file_content(body.repo, path)
            filename = os.path.basename(path)

            file_obj = save_upload_file(db, filename, content, source=source_str)

            result.append(
                FileResponse(
                    id=file_obj.id,
                    filename=file_obj.filename,
                    content_type=file_obj.content_type,
                    source=file_obj.source,
                )
            )

        except Exception as e:
            logger.error(f"Failed to download and save repository file {path}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download repository file {path}: {e}",
            )

    return result


async def _expand_paths_to_files(
    client, repo: str, paths: List[str], exclude_paths: List[str]
) -> List[str]:
    """Expand paths (which may include directories) to a list of file paths."""
    exclude_set = set(exclude_paths)
    all_files = []

    for path in paths:
        if path in exclude_set:
            continue

        try:
            logger.debug(f"Processing path: '{path}'")
            tree_node = await client.browse_tree(repo, path)
            logger.debug(f"Path '{path}' type: {tree_node.type}")

            if tree_node.type == "file":
                all_files.append(path)
            else:
                files_in_dir = await _get_all_files_in_dir(
                    client, repo, tree_node, exclude_set
                )
                logger.debug(f"Found {len(files_in_dir)} files in directory '{path}'")
                all_files.extend(files_in_dir)
        except Exception as e:
            logger.error(f"Failed to process path '{path}': {str(e)}")
            continue

    return all_files


async def _get_all_files_in_dir(client, repo: str, node, exclude_set: set) -> List[str]:
    """Recursively get all file paths in a directory."""
    files = []

    if not node.children:
        return files

    for child in node.children:
        if child.path in exclude_set:
            continue

        if child.type == "file":
            files.append(child.path)
        else:
            try:
                subtree = await client.browse_tree(repo, child.path)
                subfiles = await _get_all_files_in_dir(
                    client, repo, subtree, exclude_set
                )
                files.extend(subfiles)
            except Exception:
                continue

    return files
