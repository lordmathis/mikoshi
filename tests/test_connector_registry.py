from unittest.mock import AsyncMock

import pytest

from mikoshi.connectors.registry import ConnectorRegistry


class _FakeConnector:
    def __init__(self):
        self.close = AsyncMock()


class TestClose:
    @pytest.mark.asyncio
    async def test_closes_all_and_clears_registry(self):
        registry = ConnectorRegistry()
        a, b = _FakeConnector(), _FakeConnector()
        registry._connectors = {"github": a, "forgejo": b}

        await registry.close()

        a.close.assert_awaited_once()
        b.close.assert_awaited_once()
        assert registry.list_connectors() == {}

    @pytest.mark.asyncio
    async def test_close_error_does_not_stop_others(self):
        registry = ConnectorRegistry()
        boom = _FakeConnector()
        boom.close = AsyncMock(side_effect=RuntimeError("x"))
        ok = _FakeConnector()
        registry._connectors = {"bad": boom, "good": ok}

        await registry.close()

        ok.close.assert_awaited_once()
        assert registry.list_connectors() == {}
