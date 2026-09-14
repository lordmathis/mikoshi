import logging
import mimetypes
import os
import shutil
import uuid

from fastapi import HTTPException, UploadFile

from mikoshi.db.db import Database
from mikoshi.db.models import File

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def upload_dir_path(uploads_root: str, file_id: str) -> str:
    return os.path.join(uploads_root, file_id)


def remove_upload_dir(uploads_root: str, file_id: str) -> None:
    """Delete a file's upload directory (best effort)."""
    dir_path = upload_dir_path(uploads_root, file_id)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path, ignore_errors=True)


def sanitize_filename(filename: str | None) -> str:
    """Strip any directory components from a client-supplied filename.

    Multipart filenames are attacker-controlled; joining them unchecked
    into the upload path allows `../../` writes outside the upload dir.
    """
    name = os.path.basename((filename or "").replace("\\", "/"))
    return name or "unnamed"


async def read_upload_body(
    upload: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES
) -> bytes:
    """Read an upload body in chunks, refusing anything above ``max_bytes``."""
    chunks = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Upload exceeds the {max_bytes // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def save_upload_file(
    db: Database,
    filename: str,
    content: bytes | str,
    content_type: str | None = None,
    source: str = "upload",
    uploads_root: str = "uploads",
) -> File:
    filename = sanitize_filename(filename)
    file_id = str(uuid.uuid4())
    upload_dir = upload_dir_path(uploads_root, file_id)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, filename)

    if isinstance(content, str):
        content = content.encode("utf-8")

    with open(file_path, "wb") as f:
        f.write(content)

    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

    return db.create_file(
        filename=filename,
        file_path=os.path.abspath(file_path),
        content_type=content_type,
        file_id=file_id,
        source=source,
    )
