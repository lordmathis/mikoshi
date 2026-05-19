import os
import tempfile

import pytest


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
