from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mikoshi.routes.config import router as config_router


def _make_app(model_registry, provider_registry):
    app = FastAPI()
    app.include_router(config_router, prefix="/api")
    app.state.model_registry = model_registry
    app.state.provider_registry = provider_registry
    return app


def _registry(agent_names=(), providers=None):
    registry = MagicMock()
    registry.list_agent_names.return_value = list(agent_names)
    registry.list_providers.return_value = providers or {}
    return registry


def _provider(model_ids=None, error=None):
    provider = MagicMock()
    if error is not None:
        provider.get_model_ids = AsyncMock(side_effect=error)
    else:
        provider.get_model_ids = AsyncMock(return_value=model_ids)
    return provider


class TestListModels:
    @pytest.mark.asyncio
    async def test_lists_agents_and_provider_models(self):
        provider = _provider(model_ids=["m1", "m2"])
        app = _make_app(
            _registry(agent_names=["3X-1L-3D"]),
            _registry(providers={"prov": provider}),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/config/models")

        ids = [m["id"] for m in resp.json()["data"]]
        assert ids == ["3X-1L-3D", "prov:m1", "prov:m2"]

    @pytest.mark.asyncio
    async def test_failed_provider_does_not_hide_other_providers(self):
        providers = {
            "ok": _provider(model_ids=["m1"]),
            "broken": _provider(error=RuntimeError("boom")),
        }
        app = _make_app(_registry(), _registry(providers=providers))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/config/models")

        ids = [m["id"] for m in resp.json()["data"]]
        assert ids == ["ok:m1"]
