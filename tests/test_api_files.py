import io
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers

from mikoshi.routes import files as files_module


class _FakeDB:
    pass


def _make_request():
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(database=_FakeDB()))
    )


def _upload(filename):
    from fastapi import UploadFile

    return UploadFile(
        file=io.BytesIO(b"data"),
        size=4,
        filename=filename,
        headers=Headers({"content-type": "text/plain"}),
    )


class TestUploadFiles:
    @pytest.mark.asyncio
    async def test_missing_filename_is_not_literal_none(self, monkeypatch):
        # filename=None must not be stringified to "None".
        captured = {}

        def fake_save_upload_file(db, filename, content, content_type, source=None):
            captured["args"] = (filename, content, content_type, source)
            return SimpleNamespace(
                id="f1", filename=filename, content_type=content_type, source=source
            )

        monkeypatch.setattr(files_module, "save_upload_file", fake_save_upload_file)

        result = await files_module.upload_files(_make_request(), [_upload(None)])

        assert captured["args"][0] == "unnamed"
        assert captured["args"][3] == "upload"
        assert result[0].filename == "unnamed"

    @pytest.mark.asyncio
    async def test_real_filename_preserved(self, monkeypatch):
        captured = {}

        def fake_save_upload_file(db, filename, content, content_type, source=None):
            captured["args"] = (filename, content, content_type, source)
            return SimpleNamespace(
                id="f1", filename=filename, content_type=content_type, source=source
            )

        monkeypatch.setattr(files_module, "save_upload_file", fake_save_upload_file)

        await files_module.upload_files(_make_request(), [_upload("notes.txt")])

        assert captured["args"][0] == "notes.txt"
