import io
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from mikoshi.routes import files as files_module
from mikoshi.routes.upload_utils import read_upload_body, save_upload_file


class _FakeDB:
    pass


def _make_request():
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                database=_FakeDB(),
                app_config=SimpleNamespace(uploads_dir="uploads"),
            )
        )
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

        def fake_save_upload_file(
            db, filename, content, content_type, source=None, uploads_root="uploads"
        ):
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

        def fake_save_upload_file(
            db, filename, content, content_type, source=None, uploads_root="uploads"
        ):
            captured["args"] = (filename, content, content_type, source)
            return SimpleNamespace(
                id="f1", filename=filename, content_type=content_type, source=source
            )

        monkeypatch.setattr(files_module, "save_upload_file", fake_save_upload_file)

        await files_module.upload_files(_make_request(), [_upload("notes.txt")])

        assert captured["args"][0] == "notes.txt"


class _FakeDB:
    def create_file(self, **kwargs):
        return SimpleNamespace(
            id=kwargs["file_id"],
            filename=kwargs["filename"],
            file_path=kwargs["file_path"],
            content_type=kwargs["content_type"],
            source=kwargs["source"],
        )


class TestSaveUploadFileSanitization:
    def test_traversal_filename_stays_in_upload_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        file_obj = save_upload_file(_FakeDB(), "../../evil.txt", b"x")

        expected_dir = os.path.join(tmp_path, "uploads", file_obj.id)
        assert os.path.dirname(file_obj.file_path) == expected_dir
        assert file_obj.filename == "evil.txt"

    def test_backslash_and_empty_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        file_obj = save_upload_file(_FakeDB(), "..\\..\\win.txt", b"x")
        assert file_obj.filename == "win.txt"
        assert os.path.dirname(file_obj.file_path) == os.path.join(
            tmp_path, "uploads", file_obj.id
        )


class TestUploadSizeLimit:
    @pytest.mark.asyncio
    async def test_body_over_limit_rejected_with_413(self):
        upload = _upload("big.bin")
        upload.file = io.BytesIO(b"x" * 10)
        with pytest.raises(HTTPException) as exc:
            await read_upload_body(upload, max_bytes=4)
        assert exc.value.status_code == 413

    @pytest.mark.asyncio
    async def test_body_under_limit_passes(self):
        upload = _upload("ok.bin")
        upload.file = io.BytesIO(b"x" * 4)
        assert await read_upload_body(upload, max_bytes=4) == b"xxxx"
