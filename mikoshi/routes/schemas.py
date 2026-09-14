from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mikoshi.db.db import loads_json_field
from mikoshi.db.models import Chat, File, Message


def format_timestamp(dt: datetime) -> str:
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    if not iso.endswith("Z") and "+" not in iso and "-" not in iso[10:]:
        return iso + "Z"
    return iso


def serialize_message(
    msg: Message,
    files_by_id: Optional[Dict[str, File]] = None,
) -> Dict[str, Any]:
    file_ids: List[str] = loads_json_field(msg.file_ids, [])
    files = []
    if files_by_id:
        for fid in file_ids:
            if fid in files_by_id:
                f = files_by_id[fid]
                files.append(
                    {
                        "id": f.id,
                        "filename": f.filename,
                        "content_type": f.content_type,
                        "source": f.source,
                    }
                )
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "reasoning_content": msg.reasoning_content,
        "tool_calls": loads_json_field(msg.tool_calls, None),
        "tool_call_id": msg.tool_call_id,
        "sequence": msg.sequence,
        "created_at": format_timestamp(msg.created_at),
        "files": files,
    }


def serialize_chat(
    chat: Chat,
    messages: Optional[List[Message]] = None,
    files_by_id: Optional[Dict[str, File]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "id": chat.id,
        "title": chat.title,
        "created_at": format_timestamp(chat.created_at),
        "updated_at": format_timestamp(chat.updated_at),
        "model": chat.model,
        "system_prompt": chat.system_prompt,
        "tool_servers": loads_json_field(chat.tool_servers, None),
        "model_params": loads_json_field(chat.model_params, None),
        "workspace_id": chat.workspace_id,
    }
    if messages is not None:
        result["messages"] = [serialize_message(msg, files_by_id) for msg in messages]
    return result


class FileResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    source: Optional[str] = None
