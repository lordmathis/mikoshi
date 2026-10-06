import datetime
import logging
import mimetypes
import os
import re
import shutil
from typing import List, Optional

import yaml

from mikoshi.config import ConnectorsConfig, resolve_connector_token
from mikoshi.connectors.client_base import FileNode
from mikoshi.git import GitTimeout, auth_env, run_git

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Frontmatter must open and close within this many bytes or the file is skipped.
FRONTMATTER_READ_CAP = 64 * 1024


def _glob_to_regex(pattern: str) -> re.Pattern:
    parts = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            parts.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def _json_safe(value):
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


class WorkspaceError(Exception):
    pass


class WorkspaceNotFoundError(WorkspaceError):
    pass


class WorkspaceFileNotFoundError(WorkspaceError):
    pass


class PathTraversalError(WorkspaceError):
    pass


def _remove_empty_parents(path: str, stop_at: str):
    parent = os.path.dirname(path)
    while parent != stop_at and parent.startswith(stop_at):
        try:
            os.rmdir(parent)
        except OSError:
            break
        parent = os.path.dirname(parent)


def walk_files(root: str):
    """Yield absolute paths of all files under root, pruning .git dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for filename in filenames:
            yield os.path.join(dirpath, filename)


class WorkspaceService:
    def __init__(self, data_dir: str, connectors_config: dict[str, ConnectorsConfig]):
        self._data_dir = data_dir
        self._connectors_config = connectors_config
        self._workspaces_dir = os.path.join(data_dir, "workspaces")
        os.makedirs(self._workspaces_dir, exist_ok=True)

    def connector_token(self, connector_name: str) -> Optional[str]:
        return resolve_connector_token(self._connectors_config, connector_name)

    def _workspace_root(self, workspace_id: str) -> str:
        return os.path.realpath(os.path.join(self._workspaces_dir, workspace_id))

    def _validate_path(self, workspace_root: str, resolved_path: str):
        # Resolve again so a symlinked final component is caught even if
        # the caller didn't realpath; idempotent for resolved inputs.
        # The separator boundary matters so a sibling like `<root>evil`
        # can't pass a plain prefix check.
        real = os.path.realpath(resolved_path)
        inside = real == workspace_root or real.startswith(workspace_root + os.sep)
        if not inside:
            raise PathTraversalError("Path is outside the workspace")

    async def initialize_workspace(
        self,
        workspace_id: str,
        repo_url: Optional[str] = None,
        connector_name: Optional[str] = None,
    ):
        target_dir = self._workspace_root(workspace_id)
        if os.path.exists(target_dir):
            raise WorkspaceError("Workspace directory already exists")

        os.makedirs(target_dir, exist_ok=True)

        if not repo_url:
            logger.info(f"Initialized empty workspace {workspace_id}")
            return

        # Token auth only makes sense for the HTTPS transport; SSH ignores
        # http.extraHeader, and we don't want to offer the token to arbitrary
        # URL schemes anyway.
        clone_env = None
        if connector_name and repo_url.startswith("https://"):
            token = self.connector_token(connector_name)
            if token:
                clone_env = auth_env(token)

        try:
            rc, _, stderr = await run_git(
                ["clone", repo_url, target_dir], env=clone_env, timeout=300
            )
        except GitTimeout:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise WorkspaceError("Git clone timed out")
        if rc != 0:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise WorkspaceError(f"Git clone failed: {stderr.strip()}")

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

    def _resolve_and_validate_file(self, workspace_id: str, path: str) -> str:
        root = self.get_workspace_path(workspace_id)
        full_path = os.path.realpath(os.path.join(root, path))
        self._validate_path(root, full_path)
        if not os.path.isfile(full_path):
            raise WorkspaceFileNotFoundError(f"File not found: {path}")
        return full_path

    def read_file(self, workspace_id: str, path: str) -> str:
        full_path = self._resolve_and_validate_file(workspace_id, path)

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def read_file_raw(self, workspace_id: str, path: str) -> tuple[bytes, str]:
        full_path = self._resolve_and_validate_file(workspace_id, path)

        with open(full_path, "rb") as f:
            content = f.read()

        mime_type, _ = mimetypes.guess_type(full_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        return content, mime_type

    def write_file(self, workspace_id: str, path: str, content: str):
        root = self.get_workspace_path(workspace_id)
        full_path = os.path.realpath(os.path.join(root, path))
        self._validate_path(root, full_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def delete_file(self, workspace_id: str, path: str):
        root = self.get_workspace_path(workspace_id)
        full_path = os.path.realpath(os.path.join(root, path))
        self._validate_path(root, full_path)
        if not os.path.isfile(full_path):
            raise WorkspaceFileNotFoundError(f"File not found: {path}")
        os.remove(full_path)
        _remove_empty_parents(full_path, root)

    def rename_file(self, workspace_id: str, old_path: str, new_path: str) -> str:
        root = self.get_workspace_path(workspace_id)
        old_full = os.path.realpath(os.path.join(root, old_path))
        new_full = os.path.realpath(os.path.join(root, new_path))
        self._validate_path(root, old_full)
        self._validate_path(root, new_full)
        if not os.path.isfile(old_full):
            raise WorkspaceFileNotFoundError(f"File not found: {old_path}")
        os.makedirs(os.path.dirname(new_full), exist_ok=True)
        os.rename(old_full, new_full)
        _remove_empty_parents(old_full, root)
        return new_path

    def list_files_flat(self, workspace_id: str) -> List[str]:
        root = self.get_workspace_path(workspace_id)
        return sorted(
            os.path.relpath(path, root) for path in walk_files(root)
        )

    def get_frontmatter(self, workspace_id: str, pattern: str) -> List[dict]:
        root = self.get_workspace_path(workspace_id)
        regex = _glob_to_regex(pattern)

        results = []
        for rel_path in self.list_files_flat(workspace_id):
            if not regex.match(rel_path):
                continue
            frontmatter = self._read_frontmatter(os.path.join(root, rel_path))
            if frontmatter:
                results.append({"path": rel_path, "frontmatter": frontmatter})
        return results

    def _read_frontmatter(self, full_path: str) -> Optional[dict]:
        try:
            with open(full_path, "rb") as f:
                head = f.read(FRONTMATTER_READ_CAP).decode(
                    "utf-8", errors="replace"
                )
        except OSError:
            return None

        match = FRONTMATTER_RE.match(head)
        if not match:
            return None

        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            logger.debug(f"Invalid frontmatter YAML in {full_path}")
            return None

        if not isinstance(data, dict) or not data:
            return None
        return _json_safe(data)
