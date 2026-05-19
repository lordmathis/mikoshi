import pytest


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("MIKOSHI_TEST_VAR", raising=False)
