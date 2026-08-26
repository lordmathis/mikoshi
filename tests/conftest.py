import os
import tempfile

import pytest
from unittest.mock import MagicMock

from mikoshi.config import AppConfig
from mikoshi.db import Database
from mikoshi.tools.manager import ToolManager
from mikoshi.tools.toolset_handler import ToolSetHandler


class FakeSkill:
    def __init__(self, content="ok", tool_servers=None, read_error=None):
        self._content = content
        self._tool_servers = tool_servers or []
        self._read_error = read_error

    def read_content(self):
        if self._read_error:
            raise self._read_error
        return self._content

    def get_required_tool_servers(self):
        return self._tool_servers


class FakeRegistry:
    def __init__(self, skills=None, default_skill=None):
        self._skills = skills or {}
        self._default_skill = default_skill

    def get_skill(self, name):
        if name in self._skills:
            return self._skills[name]
        if self._default_skill is not None:
            return self._default_skill
        return None


async def make_tool_manager(
    toolset: ToolSetHandler, db: Database | None = None
) -> ToolManager:
    """Build a ToolManager with a single registered toolset.

    Uses the real constructor and the real ``initialize()`` registration
    path; only the handler registration itself is manual (ToolManager has
    no public single-handler API).
    """
    tm = ToolManager(AppConfig(), MagicMock(), db=db)
    await toolset.initialize()
    tm._toolset_handlers[toolset.server_name] = toolset
    tm._server_map[toolset.server_name] = toolset
    return tm


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def tmp_yaml(tmp_dir):
    def _write(content: str) -> str:
        path = os.path.join(tmp_dir, "config.yaml")
        with open(path, "w") as f:
            f.write(content)
        return path

    return _write


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def app_config():
    return AppConfig()
