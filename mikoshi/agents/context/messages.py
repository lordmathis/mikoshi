import base64
import json
import logging
import os
from typing import Any, Dict, List

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.db.db import Database

logger = logging.getLogger(__name__)


def parse_content(msg_content: str):
    """Parse message content from JSON or return as plain string."""
    try:
        return json.loads(msg_content)
    except (json.JSONDecodeError, TypeError):
        return msg_content


def parse_tool_arguments(raw: Any):
    """Parse tool-call arguments JSON, returning the raw value on failure.

    A model can emit truncated JSON when its output hits the length limit
    mid-argument; we keep the raw string so persistence never crashes and the
    caller can report a recoverable error.
    """
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def extract_text_content(raw_content: str) -> str:
    """Decode message content to plain text regardless of storage format."""
    content = parse_content(raw_content)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text")
    return str(content)


def extract_assistant_content(
    response: Dict[str, Any],
) -> tuple[str, str | None, List[Dict] | None]:
    """Extract content, reasoning_content, and tool_calls from assistant response.

    Returns tool_calls as a list of dicts with preserved IDs for persistence.
    """
    choices = response.get("choices", [])
    if not choices:
        return "", None, None
    msg_data = choices[0].get("message", {})
    if isinstance(msg_data, dict):
        content = msg_data.get("content", "") or ""
        reasoning_content = msg_data.get("reasoning_content")
        raw_tool_calls = msg_data.get("tool_calls")
    else:
        content = getattr(msg_data, "content", "") or ""
        reasoning_content = getattr(msg_data, "reasoning_content", None)
        raw_tool_calls = getattr(msg_data, "tool_calls", None)

    if raw_tool_calls:
        tool_calls = [
            {
                "id": tc.get("id", f"call_{i}"),
                "name": tc["function"]["name"],
                "arguments": parse_tool_arguments(tc["function"]["arguments"]),
            }
            for i, tc in enumerate(raw_tool_calls)
        ]
        return content, reasoning_content, tool_calls

    return content, reasoning_content, None


def process_user_message(db: Database, msg) -> ChatCompletionMessageParam:
    """Process user message and reconstruct content with attachments.

    Handles text files (appended to content) and images (encoded as base64).
    """
    content = parse_content(msg.content)

    file_ids_str = getattr(msg, "file_ids", None)
    file_ids = []
    if file_ids_str:
        try:
            file_ids = json.loads(file_ids_str)
        except json.JSONDecodeError:
            pass

    files = []
    if file_ids:
        for fid in file_ids:
            f = db.get_file(fid)
            if f:
                files.append(f)
            else:
                logger.warning(f"File {fid} referenced by message {msg.id} not found.")

    if not files:
        return {"role": "user", "content": content}

    content_text = content if isinstance(content, str) else ""
    if not isinstance(content, str):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                content_text = part.get("text", "")
                break

    text_files = []
    image_files = []
    for attachment in files:
        if attachment.content_type.startswith("image/"):
            image_files.append(attachment)
        else:
            text_files.append(attachment)

    if text_files:
        content_text += "\n\n--- Attached Text Files ---\n"
    for attachment in text_files:
        if not os.path.exists(attachment.file_path):
            continue
        try:
            with open(attachment.file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            filename = os.path.basename(attachment.file_path)
            content_text += f"\n\n--- Content of {filename} ---\n{file_content}"
        except Exception as e:
            logger.error(f"Failed to read attachment {attachment.file_path}: {e}")

    if not image_files:
        return {"role": "user", "content": content_text}

    content_parts: List[Dict[str, Any]] = [{"type": "text", "text": content_text}]

    for attachment in image_files:
        if not os.path.exists(attachment.file_path):
            continue
        try:
            with open(attachment.file_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(attachment.file_path)[1].lower().lstrip(".")
            image_format = "jpeg" if ext in ("jpg", "jpeg") else ext or "jpeg"
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{image_format};base64,{img_data}"
                    },
                }
            )
        except Exception as e:
            logger.error(f"Failed to read image {attachment.file_path}: {e}")

    return {"role": "user", "content": content_parts}


def format_history(db: Database, chat_id: str) -> List[ChatCompletionMessageParam]:
    """Format chat history from DB into OpenAI message format.

    Handles user messages with attachments, assistant and system messages,
    and tool result messages.
    """
    history = db.get_chat_history(chat_id)
    messages: List[ChatCompletionMessageParam] = []

    for msg in history:
        if msg.role == "user":
            messages.append(process_user_message(db, msg))
        elif msg.role == "assistant":
            content = parse_content(msg.content)
            msg_dict: Dict[str, Any] = {"role": "assistant", "content": content}
            if msg.tool_calls:
                tool_calls_data = json.loads(msg.tool_calls)
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"])
                            if isinstance(tc["arguments"], dict)
                            else tc["arguments"],
                        },
                    }
                    for i, tc in enumerate(tool_calls_data)
                ]
            messages.append(msg_dict)
        elif msg.role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or "unknown",
                    "content": msg.content,
                }
            )
        elif msg.role == "system":
            content = parse_content(msg.content)
            messages.append({"role": "system", "content": content})

    return messages
