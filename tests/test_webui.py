import httpx
import pytest
from fastapi import FastAPI

from mikoshi import webui as webui_module
from mikoshi.webui import setup_webui


@pytest.fixture
def static_app(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>index</html>")
    (dist / "app.js").write_text("console.log(1)")
    (dist / "sw.js").write_text("// sw")
    (dist / "manifest.webmanifest").write_text("{}")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("console.log(2)")
    (tmp_path / "secret.txt").write_text("SECRET")
    monkeypatch.setattr(webui_module, "_find_webui_dist", lambda: dist)

    app = FastAPI()
    setup_webui(app)
    return app


async def _get(app, path):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


class TestStaticContainment:
    @pytest.mark.asyncio
    async def test_regular_file_served(self, static_app):
        response = await _get(static_app, "/app.js")
        assert response.status_code == 200
        assert response.text == "console.log(1)"

    @pytest.mark.asyncio
    async def test_index_served_for_extensionless_path(self, static_app):
        response = await _get(static_app, "/some/route")
        assert response.status_code == 200
        assert "index" in response.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        [
            "/..%2Fsecret.txt",
            "/%2e%2e/secret.txt",
            "/..%2f..%2fsecret.txt",
        ],
    )
    async def test_encoded_dot_segments_rejected(self, static_app, path):
        response = await _get(static_app, path)
        assert response.status_code == 404
        assert "SECRET" not in response.text

    @pytest.mark.asyncio
    async def test_symlink_inside_dist_pointing_out_rejected(self, static_app, tmp_path):
        (tmp_path / "dist" / "linked.js").symlink_to(tmp_path / "secret.txt")
        assert (await _get(static_app, "/linked.js")).status_code == 404


class TestCacheHeaders:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/some/route",
            "/index.html",
            "/sw.js",
            "/manifest.webmanifest",
        ],
    )
    async def test_shell_files_are_no_cache(self, static_app, path):
        response = await _get(static_app, path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"

    @pytest.mark.asyncio
    async def test_hashed_assets_are_immutable(self, static_app):
        response = await _get(static_app, "/assets/index-abc123.js")
        assert response.status_code == 200
        assert response.headers["cache-control"] == (
            "public, max-age=31536000, immutable"
        )

    @pytest.mark.asyncio
    async def test_regular_files_have_no_cache_control(self, static_app):
        response = await _get(static_app, "/app.js")
        assert response.status_code == 200
        assert "cache-control" not in response.headers


class TestMimeTypes:
    @pytest.mark.asyncio
    async def test_webmanifest_mime_type(self, static_app):
        response = await _get(static_app, "/manifest.webmanifest")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/manifest+json"
        )
