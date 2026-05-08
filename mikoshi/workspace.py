import logging
import os
import shutil
import subprocess
from typing import List, Optional

from mikoshi.config import ConnectorsConfig
from mikoshi.connectors.client_base import FileNode

logger = logging.getLogger(__name__)


class WorkspaceError(Exception):
    pass


class WorkspaceNotFoundError(WorkspaceError):
    pass


class PathTraversalError(WorkspaceError):
    pass


class WorkspaceService:
    def __init__(self, data_dir: str, connectors_config: dict[str, ConnectorsConfig]):
        self._data_dir = data_dir
        self._connectors_config = connectors_config
        self._workspaces_dir = os.path.join(data_dir, "workspaces")
        os.makedirs(self._workspaces_dir, exist_ok=True)

    def _resolve_connector_token(self, connector_name: str) -> Optional[str]:
        cfg = self._connectors_config.get(connector_name)
        return cfg.token if cfg else None

    def _build_auth_url(self, repo_url: str, token: str) -> str:
        if "github.com" in repo_url:
            return repo_url.replace("https://", f"https://x-access-token:{token}@")
        return repo_url.replace("https://", f"https://x-access-token:{token}@")

    def _workspace_root(self, workspace_id: str) -> str:
        return os.path.realpath(os.path.join(self._workspaces_dir, workspace_id))

    def _validate_path(self, workspace_root: str, resolved_path: str):
        if os.path.realpath(resolved_path) != resolved_path:
            if os.path.islink(resolved_path):
                real = os.path.realpath(resolved_path)
                if not real.startswith(workspace_root):
                    raise PathTraversalError(
                        f"Symlink points outside workspace: {resolved_path}"
                    )
        if not resolved_path.startswith(workspace_root):
            raise PathTraversalError(f"Path traversal detected: {resolved_path}")

    def initialize_workspace(
        self,
        workspace_id: str,
        repo_url: str,
        connector_name: Optional[str] = None,
    ):
        target_dir = self._workspace_root(workspace_id)
        if os.path.exists(target_dir):
            raise WorkspaceError(f"Workspace directory already exists: {target_dir}")

        os.makedirs(target_dir, exist_ok=True)

        clone_url = repo_url
        if connector_name:
            token = self._resolve_connector_token(connector_name)
            if token:
                clone_url = self._build_auth_url(repo_url, token)

        try:
            subprocess.run(
                ["git", "clone", clone_url, target_dir],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise WorkspaceError(f"Git clone failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise WorkspaceError("Git clone timed out")

        logger.info(f"Initialized workspace {workspace_id} from {repo_url}")

    def get_workspace_path(self, workspace_id: str) -> str:
        root = self._workspace_root(workspace_id)
        if not os.path.isdir(root):
            raise WorkspaceNotFoundError(
                f"Workspace directory not found: {workspace_id}"
            )
        return root

    def delete_workspace_files(self, workspace_id: str):
        root = self._workspace_root(workspace_id)
        if os.path.exists(root):
            shutil.rmtree(root, ignore_errors=True)
            logger.info(f"Deleted workspace files for {workspace_id}")

    def get_file_tree(self, workspace_id: str, path: str = "") -> FileNode:
        root = self.get_workspace_path(workspace_id)
        target = os.path.join(root, path) if path else root
        resolved = os.path.realpath(target)
        self._validate_path(root, resolved)

        if not os.path.isdir(resolved):
            raise WorkspaceError(f"Path is not a directory: {path}")

        children = []
        try:
            entries = sorted(
                os.scandir(resolved), key=lambda e: (not e.is_dir(), e.name.lower())
            )
        except PermissionError:
            entries = []

        for entry in entries:
            if entry.name == ".git":
                continue
            rel_path = os.path.relpath(entry.path, root)
            node_type = "dir" if entry.is_dir() else "file"
            size = None
            if entry.is_file(follow_symlinks=False):
                try:
                    size = entry.stat().st_size
                except OSError:
                    pass
            children.append(
                FileNode(path=rel_path, name=entry.name, type=node_type, size=size)
            )

        dir_name = os.path.basename(resolved) if path else ""
        return FileNode(path=path, name=dir_name, type="dir", children=children)

    def read_file(self, workspace_id: str, path: str) -> str:
        root = self.get_workspace_path(workspace_id)
        full_path = os.path.realpath(os.path.join(root, path))
        self._validate_path(root, full_path)

        if not os.path.isfile(full_path):
            raise WorkspaceError(f"File not found: {path}")

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_file(self, workspace_id: str, path: str, content: str):
        root = self.get_workspace_path(workspace_id)
        full_path = os.path.realpath(os.path.join(root, path))
        self._validate_path(root, full_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_files_flat(self, workspace_id: str) -> List[str]:
        root = self.get_workspace_path(workspace_id)
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            if ".git" in dirnames:
                dirnames.remove(".git")
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)
                files.append(rel_path)
        return sorted(files)
