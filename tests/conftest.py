import os
import tempfile

import pytest

from mikoshi.config import AppConfig
from mikoshi.db import Database


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
