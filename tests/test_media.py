import io

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mikoshi.config import AppConfig, AudioConfig, TranscriptionConfig
from mikoshi.routes.media import router as media_router


class _FakeAsyncClient:
    captured = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        type(self).captured = {"url": url, **kwargs}
        return httpx.Response(
            200, json={"text": "transcribed"}, request=httpx.Request("POST", url)
        )


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(
        "mikoshi.routes.media.httpx.AsyncClient", _FakeAsyncClient
    )
    app = FastAPI()
    app.include_router(media_router, prefix="/api")
    app.state.app_config = AppConfig(
        audio=AudioConfig(transcription=TranscriptionConfig(base_url="http://asr"))
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_sends_bytesio_without_temp_file(self, client):
        resp = await client.post(
            "/api/media/transcribe",
            files={"file": ("memo.webm", b"AUDIO", "audio/webm")},
        )
        assert resp.status_code == 200
        assert resp.json() == {"text": "transcribed"}

        captured = _FakeAsyncClient.captured
        assert captured["url"] == "http://asr/v1/audio/transcriptions"
        name, fileobj, content_type = captured["files"]["file"]
        assert name == "memo.webm"
        assert content_type == "audio/webm"
        assert isinstance(fileobj, io.BytesIO)
        assert fileobj.getvalue() == b"AUDIO"
