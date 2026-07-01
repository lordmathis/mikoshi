import os
import subprocess
from unittest.mock import patch

import pytest

from mikoshi.config import ConnectorsConfig, ConnectorType
from mikoshi.workspace import (
    PathTraversalError,
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceService,
    _remove_empty_parents,
)


@pytest.fixture
def ws(tmp_dir):
    return WorkspaceService(tmp_dir, {})


def _create_workspace(ws, workspace_id="test-ws"):
    root = os.path.join(ws._workspaces_dir, workspace_id)
    os.makedirs(root, exist_ok=True)
    return root


def _create_file(root, rel_path, content="hello"):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return full


class TestRemoveEmptyParents:
    def test_removes_empty_parents(self, tmp_dir):
        nested = os.path.join(tmp_dir, "a", "b", "c")
        os.makedirs(nested)
        _create_file(tmp_dir, "a/file.txt", "keep")
        leaf = os.path.join(nested, "file.txt")
        _create_file(tmp_dir, "a/b/c/file.txt", "x")

        os.remove(leaf)
        _remove_empty_parents(leaf, os.path.join(tmp_dir, "a"))

        assert os.path.isdir(os.path.join(tmp_dir, "a", "b")) is False
        assert os.path.isdir(os.path.join(tmp_dir, "a"))
        assert os.path.isfile(os.path.join(tmp_dir, "a", "file.txt"))

    def test_stops_at_stop_at(self, tmp_dir):
        nested = os.path.join(tmp_dir, "x", "y", "z")
        os.makedirs(nested)
        leaf = os.path.join(nested, "file.txt")
        _create_file(tmp_dir, "x/y/z/file.txt", "x")
        os.remove(leaf)
        _remove_empty_parents(leaf, os.path.join(tmp_dir, "x"))
        assert not os.path.isdir(os.path.join(tmp_dir, "x", "y"))
        assert os.path.isdir(os.path.join(tmp_dir, "x"))

    def test_stops_on_non_empty_parent(self, tmp_dir):
        nested = os.path.join(tmp_dir, "a", "b", "c")
        os.makedirs(nested)
        _create_file(tmp_dir, "a/b/other.txt", "keep")
        _create_file(tmp_dir, "a/b/c/file.txt", "x")
        os.remove(os.path.join(nested, "file.txt"))
        _remove_empty_parents(os.path.join(nested, "file.txt"), tmp_dir)
        assert os.path.isdir(os.path.join(tmp_dir, "a", "b"))
        assert os.path.isdir(os.path.join(tmp_dir, "a", "b", "c")) is False


class TestPathTraversal:
    def test_traversal_with_dotdot(self, ws):
        root = _create_workspace(ws)
        bad = os.path.realpath(os.path.join(root, "..", "..", "etc", "passwd"))
        with pytest.raises(PathTraversalError, match="Path traversal"):
            ws._validate_path(root, bad)

    def test_symlink_outside_workspace(self, ws):
        root = _create_workspace(ws)
        link = os.path.join(root, "evil_link")
        os.symlink("/etc/passwd", link)
        with pytest.raises(PathTraversalError, match="Symlink points outside"):
            ws._validate_path(root, link)

    def test_valid_path_passes(self, ws):
        root = _create_workspace(ws)
        good = os.path.realpath(os.path.join(root, "src", "main.py"))
        ws._validate_path(root, good)


class TestWorkspaceOps:
    def test_get_workspace_path(self, ws):
        _create_workspace(ws, "my-ws")
        path = ws.get_workspace_path("my-ws")
        assert os.path.isdir(path)
        assert path.endswith(os.path.join("workspaces", "my-ws"))

    def test_get_workspace_path_not_found(self, ws):
        with pytest.raises(WorkspaceNotFoundError):
            ws.get_workspace_path("nonexistent")

    def test_delete_workspace_files(self, ws):
        root = _create_workspace(ws, "doomed")
        _create_file(root, "file.txt", "bye")
        ws.delete_workspace_files("doomed")
        assert not os.path.exists(root)

    def test_initialize_workspace_success(self, ws):
        with patch("mikoshi.workspace.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            ws.initialize_workspace("new-ws", "https://example.com/repo.git")
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "git"
            assert "clone" in args

    def test_initialize_workspace_already_exists(self, ws):
        _create_workspace(ws, "existing")
        with pytest.raises(WorkspaceError, match="already exists"):
            ws.initialize_workspace("existing", "https://example.com/repo.git")

    def test_initialize_workspace_clone_failure(self, ws):
        with patch("mikoshi.workspace.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git", stderr="fatal: not found"
            )
            with pytest.raises(WorkspaceError, match="Git clone failed"):
                ws.initialize_workspace("fail-ws", "https://bad.url")

    def test_initialize_workspace_timeout(self, ws):
        with patch("mikoshi.workspace.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 300)
            with pytest.raises(WorkspaceError, match="timed out"):
                ws.initialize_workspace("slow-ws", "https://slow.url")

    def test_initialize_workspace_with_connector_token(self, ws):
        cfg = ConnectorsConfig(type=ConnectorType.GITHUB, token="secret-token")
        ws_with_conn = WorkspaceService(
            ws._data_dir, {"github": cfg}
        )
        with patch("mikoshi.workspace.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            ws_with_conn.initialize_workspace(
                "conn-ws", "https://github.com/org/repo.git", "github"
            )
            args = mock_run.call_args[0][0]
            assert "-c" in args
            assert "Authorization: Basic" in " ".join(args)

    def test_initialize_workspace_connector_no_token(self, ws):
        with patch("mikoshi.workspace.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            ws.initialize_workspace(
                "no-token-ws", "https://example.com/repo.git", "unknown-connector"
            )
            args = mock_run.call_args[0][0]
            assert "-c" not in args

    def test_initialize_workspace_no_repo_url_skips_clone(self, ws):
        with patch("mikoshi.workspace.subprocess.run") as mock_run:
            ws.initialize_workspace("empty-ws", None)
            mock_run.assert_not_called()
        root = os.path.join(ws._workspaces_dir, "empty-ws")
        assert os.path.isdir(root)


class TestFileReadWrite:
    def test_write_and_read(self, ws):
        root = _create_workspace(ws)
        ws.write_file("test-ws", "hello.txt", "hello world")
        assert os.path.isfile(os.path.join(root, "hello.txt"))
        assert ws.read_file("test-ws", "hello.txt") == "hello world"

    def test_write_creates_parent_dirs(self, ws):
        root = _create_workspace(ws)
        ws.write_file("test-ws", "deep/nested/dir/file.txt", "content")
        assert ws.read_file("test-ws", "deep/nested/dir/file.txt") == "content"

    def test_write_traversal_blocked(self, ws):
        _create_workspace(ws)
        with pytest.raises(PathTraversalError):
            ws.write_file("test-ws", "../../etc/evil", "hacked")

    def test_read_file_not_found(self, ws):
        _create_workspace(ws)
        with pytest.raises(WorkspaceError, match="File not found"):
            ws.read_file("test-ws", "nonexistent.txt")

    def test_read_file_raw_text(self, ws):
        _create_workspace(ws)
        ws.write_file("test-ws", "data.txt", "raw content")
        content, mime = ws.read_file_raw("test-ws", "data.txt")
        assert content == b"raw content"
        assert mime == "text/plain"

    def test_read_file_raw_binary(self, ws):
        root = _create_workspace(ws)
        with open(os.path.join(root, "image.png"), "wb") as f:
            f.write(b"\x89PNG\r\n")
        content, mime = ws.read_file_raw("test-ws", "image.png")
        assert content == b"\x89PNG\r\n"
        assert mime == "image/png"


class TestFileTree:
    def test_file_node_has_size(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "sized.txt", "12345")
        tree = ws.get_file_tree("test-ws")
        node = next(c for c in tree.children if c.name == "sized.txt")
        assert node.size == 5

    def test_basic_tree(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "a.txt", "a")
        _create_file(root, "sub/b.txt", "b")

        tree = ws.get_file_tree("test-ws")
        assert tree.type == "dir"
        assert tree.name == ""
        names = [c.name for c in tree.children]
        assert "a.txt" in names
        assert "sub" in names

    def test_excludes_git_dir(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "code.py", "pass")
        _create_file(root, ".git/HEAD", "ref: refs/heads/main")

        tree = ws.get_file_tree("test-ws")
        names = [c.name for c in tree.children]
        assert ".git" not in names
        assert "code.py" in names

    def test_dirs_before_files_sorted_case_insensitive(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "Zebra.txt", "z")
        _create_file(root, "alpha.txt", "a")
        _create_file(root, "Sub/inner.txt", "i")

        tree = ws.get_file_tree("test-ws")
        types = [c.type for c in tree.children]
        names = [c.name for c in tree.children]
        dir_idx = types.index("dir")
        file_idx = types.index("file")
        assert dir_idx < file_idx
        assert names.index("Sub") < names.index("alpha.txt")

    def test_tree_subdirectory(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "sub/deep.txt", "d")
        tree = ws.get_file_tree("test-ws", "sub")
        assert tree.type == "dir"
        assert tree.name == "sub"
        assert len(tree.children) == 1
        assert tree.children[0].name == "deep.txt"

    def test_tree_not_a_directory(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "file.txt", "x")
        with pytest.raises(WorkspaceError, match="not a directory"):
            ws.get_file_tree("test-ws", "file.txt")

    def test_file_node_has_size(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "sized.txt", "12345")
        tree = ws.get_file_tree("test-ws")
        node = next(c for c in tree.children if c.name == "sized.txt")
        assert node.size == 5


class TestDeleteFile:
    def test_delete_file(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "to-delete.txt", "bye")
        ws.delete_file("test-ws", "to-delete.txt")
        assert not os.path.isfile(os.path.join(root, "to-delete.txt"))

    def test_delete_file_not_found(self, ws):
        _create_workspace(ws)
        with pytest.raises(WorkspaceError, match="File not found"):
            ws.delete_file("test-ws", "ghost.txt")

    def test_delete_file_cleans_empty_parents(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "deep/nested/leaf.txt", "x")
        ws.delete_file("test-ws", "deep/nested/leaf.txt")
        assert not os.path.isdir(os.path.join(root, "deep"))

    def test_delete_file_keeps_non_empty_parents(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "dir/keep.txt", "stay")
        _create_file(root, "dir/remove.txt", "go")
        ws.delete_file("test-ws", "dir/remove.txt")
        assert os.path.isfile(os.path.join(root, "dir", "keep.txt"))
        assert os.path.isdir(os.path.join(root, "dir"))


class TestRenameFile:
    def test_rename_file(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "old.txt", "data")
        result = ws.rename_file("test-ws", "old.txt", "new.txt")
        assert result == "new.txt"
        assert not os.path.isfile(os.path.join(root, "old.txt"))
        assert os.path.isfile(os.path.join(root, "new.txt"))
        assert ws.read_file("test-ws", "new.txt") == "data"

    def test_rename_creates_target_parents(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "src.txt", "move me")
        ws.rename_file("test-ws", "src.txt", "new/dir/dest.txt")
        assert os.path.isfile(os.path.join(root, "new", "dir", "dest.txt"))
        assert not os.path.isfile(os.path.join(root, "src.txt"))

    def test_rename_cleans_empty_source_parents(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "olddir/file.txt", "x")
        ws.rename_file("test-ws", "olddir/file.txt", "moved.txt")
        assert not os.path.isdir(os.path.join(root, "olddir"))

    def test_rename_source_not_found(self, ws):
        _create_workspace(ws)
        with pytest.raises(WorkspaceError, match="File not found"):
            ws.rename_file("test-ws", "nope.txt", "dest.txt")

    def test_rename_traversal_blocked_on_new_path(self, ws):
        _create_workspace(ws)
        _create_file(os.path.join(ws._workspaces_dir, "test-ws"), "file.txt", "x")
        with pytest.raises(PathTraversalError):
            ws.rename_file("test-ws", "file.txt", "../../escaped.txt")


class TestListFilesFlat:
    def test_list_files(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "a.txt", "a")
        _create_file(root, "sub/b.txt", "b")
        _create_file(root, "sub/deep/c.txt", "c")

        files = ws.list_files_flat("test-ws")
        assert files == ["a.txt", "sub/b.txt", "sub/deep/c.txt"]

    def test_excludes_git(self, ws):
        root = _create_workspace(ws)
        _create_file(root, "code.py", "pass")
        _create_file(root, ".git/HEAD", "ref")
        _create_file(root, ".git/objects/abc", "blob")

        files = ws.list_files_flat("test-ws")
        assert files == ["code.py"]
