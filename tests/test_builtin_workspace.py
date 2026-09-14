import os

import pytest

from mikoshi.tools.builtin.workspace import _resolve_path


class TestResolvePathBoundary:
    def test_sibling_with_shared_prefix_rejected(self, tmp_path):
        root = tmp_path / "ws"
        root.mkdir()
        (tmp_path / "ws-evil").mkdir()
        with pytest.raises(ValueError, match="outside the workspace"):
            _resolve_path(str(root), "../ws-evil/file.txt")

    def test_dotdot_escape_rejected(self, tmp_path):
        root = tmp_path / "ws"
        root.mkdir()
        with pytest.raises(ValueError, match="outside the workspace"):
            _resolve_path(str(root), "../../etc/passwd")

    def test_inside_path_passes(self, tmp_path):
        root = tmp_path / "ws"
        (root / "sub").mkdir(parents=True)
        full = _resolve_path(str(root), "sub/file.txt")
        assert full.startswith(str(root) + os.sep)
