import logging
import mimetypes
import os
import uuid

from mikoshi.db.db import Database
from mikoshi.db.models import File

logger = logging.getLogger(__name__)


def save_upload_file(
    db: Database,
    filename: str,
    content: bytes | str,
    content_type: str | None = None,
    source: str = "upload",
) -> File:
    file_id = str(uuid.uuid4())
    upload_dir = os.path.join("uploads", file_id)
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
