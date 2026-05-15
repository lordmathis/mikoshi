import logging
import os
import shutil
from typing import List

from fastapi import APIRouter, HTTPException, Request, UploadFile

from mikoshi.routes.schemas import FileResponse
from mikoshi.routes.upload_utils import save_upload_file

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/files", response_model=List[FileResponse])
async def upload_files(request: Request, files: List[UploadFile]):
    db = request.app.state.database
    result = []

    for upload in files:
        filename = upload.filename or str(upload.filename)
        content = await upload.read()
        content_type = (
            upload.content_type
            or "application/octet-stream"
        )

        file_obj = save_upload_file(db, filename, content, content_type, source="upload")

        result.append(
            FileResponse(
                id=file_obj.id,
                filename=file_obj.filename,
                content_type=file_obj.content_type,
                source=file_obj.source,
            )
        )

    return result


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_file(request: Request, file_id: str):
    db = request.app.state.database
    file_obj = db.get_file(file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        id=file_obj.id, filename=file_obj.filename, content_type=file_obj.content_type
    )


@router.delete("/files/{file_id}")
async def delete_file(request: Request, file_id: str):
    db = request.app.state.database
    file_obj = db.get_file(file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")

    if file_obj.status == "attached":
        raise HTTPException(status_code=400, detail="Cannot delete an attached file")

    db.delete_file(file_id)

    upload_dir = os.path.join("uploads", file_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)

    return {"status": "success"}
