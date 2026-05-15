import asyncio
import json
import logging
from dataclasses import asdict
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mikoshi.agents.manager import AgentManager
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent
from mikoshi.routes.schemas import serialize_chat

logger = logging.getLogger(__name__)


async def _run_with_done_guard(coro, queue: asyncio.Queue, chat_id: str):
    """Wrap a streaming coroutine and guarantee STREAM_DONE is always emitted.

    Without this, if the coroutine crashes before entering _loop (e.g. in
    _save_message) or is cancelled (CancelledError bypasses except Exception),
    the queue never receives a done event and event_stream hangs forever on
    queue.get(), leaving the frontend stuck on "Breaching...".
    """
    try:
        await coro
    except asyncio.CancelledError:
        logger.warning("chat_id=%s stream task cancelled", chat_id)
        raise
    except Exception as e:
        logger.error(
            "chat_id=%s stream task failed outside _loop: %s", chat_id, e, exc_info=True
        )
        await queue.put(StreamEvent(type="error", data={"message": str(e)}))
    finally:
        await queue.put(STREAM_DONE)
        logger.debug("chat_id=%s done guard fired", chat_id)


async def event_stream(
    task: asyncio.Task, queue: asyncio.Queue, chat_id: str
) -> AsyncGenerator[str, None]:
    try:
        while True:
            event: StreamEvent = await queue.get()
            logger.debug(
                "chat_id=%s SSE event: type=%s", chat_id, event.type
            )
            yield f"data: {json.dumps(asdict(event))}\n\n"
            if event.type == "done":
                logger.debug("chat_id=%s SSE stream complete", chat_id)
                break
    except GeneratorExit:
        logger.warning("chat_id=%s SSE client disconnected, cancelling task", chat_id)
        task.cancel()
        raise


router = APIRouter()


class ModelParams(BaseModel):
    max_iterations: Optional[int] = 5
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ChatConfig(BaseModel):
    model: str
    system_prompt: Optional[str] = None
    tool_servers: Optional[List[str]] = None
    model_params: Optional[ModelParams] = None


class CreateChatRequest(BaseModel):
    title: Optional[str] = "Untitled Chat"
    workspace_id: Optional[str] = None
    config: ChatConfig


class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    config: Optional[ChatConfig] = None


class SendMessageRequest(BaseModel):
    message: str
    file_ids: List[str] = []
    stream: Optional[bool] = False


class BranchChatRequest(BaseModel):
    message_id: str
    title: Optional[str] = None


class EditLastMessageRequest(BaseModel):
    message: str
    stream: Optional[bool] = False


class RetryRequest(BaseModel):
    stream: Optional[bool] = False


@router.post("/chats")
async def create_chat(request: Request, body: CreateChatRequest):
    """
    Create a new chat session with an agent.
    """
    database = request.app.state.database
    agent_manager: AgentManager = request.app.state.agent_manager

    chat = database.create_chat(title=body.title, workspace_id=body.workspace_id)

    try:
        agent_manager.create(
            chat_id=chat.id,
            config=body.config.model_dump(),
        )
    except ValueError as e:
        database.delete_chat(chat.id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        database.delete_chat(chat.id)
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")

    updated_chat = database.get_chat(chat.id)

    return serialize_chat(updated_chat)


@router.get("/chats")
async def list_chats(request: Request, limit: int = 20):
    """
    List recent chats ordered by most recently updated.
    """
    database = request.app.state.database

    chats = database.list_chats(limit=limit)

    return {"chats": [serialize_chat(chat) for chat in chats]}


@router.get("/chats/{chat_id}")
async def get_chat(request: Request, chat_id: str):
    """
    Get chat metadata and full message history.
    """
    database = request.app.state.database

    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

    messages = database.get_chat_history(chat_id)

    all_file_ids = []
    for msg in messages:
        if msg.file_ids:
            all_file_ids.extend(json.loads(msg.file_ids))

    files_by_id = database.get_files(all_file_ids)

    return serialize_chat(chat, messages=messages, files_by_id=files_by_id)


@router.delete("/chats/{chat_id}")
async def delete_chat(request: Request, chat_id: str):
    """
    Delete a chat and all its messages, and remove its agent.
    """
    database = request.app.state.database
    agent_manager: AgentManager = request.app.state.agent_manager

    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

    agent_manager.remove(chat_id)

    database.delete_chat(chat_id)

    return {"success": True}


@router.patch("/chats/{chat_id}")
async def update_chat(request: Request, chat_id: str, body: UpdateChatRequest):
    """
    Update chat metadata (e.g., title) and/or configuration.
    """
    database = request.app.state.database
    agent_manager: AgentManager = request.app.state.agent_manager

    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

    update_kwargs = {}

    if body.title is not None:
        update_kwargs["title"] = body.title

    if body.config:
        try:
            agent_manager.remove(chat_id)
            agent_manager.create(chat_id=chat_id, config=body.config.model_dump())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update agent: {str(e)}"
            )

    updated_chat = database.update_chat(chat_id, **update_kwargs)
    if not updated_chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

    return serialize_chat(updated_chat)


@router.post("/chats/{chat_id}/branch")
async def branch_chat(request: Request, chat_id: str, body: BranchChatRequest):
    """
    Create a new chat branching from an existing chat.
    Copies all messages and attachments up to and including the specified message.
    This allows exploring different conversation paths without losing the original.
    """
    database = request.app.state.database
    agent_manager: AgentManager = request.app.state.agent_manager

    source_chat = database.get_chat(chat_id)
    if not source_chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

    branched_chat = database.branch_chat(
        source_chat_id=chat_id, up_to_message_id=body.message_id, new_title=body.title
    )

    if not branched_chat:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to branch chat. Message '{body.message_id}' may not exist in chat '{chat_id}'.",
        )

    try:
        config = {
            "model": branched_chat.model,
            "system_prompt": branched_chat.system_prompt,
            "tool_servers": json.loads(branched_chat.tool_servers)
            if branched_chat.tool_servers
            else None,
            "model_params": json.loads(branched_chat.model_params)
            if branched_chat.model_params
            else None,
        }

        agent_manager.create(chat_id=branched_chat.id, config=config)
    except Exception as e:
        database.delete_chat(branched_chat.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create agent for branch: {str(e)}",
        )

    messages = database.get_chat_history(branched_chat.id)

    all_file_ids = []
    for msg in messages:
        if msg.file_ids:
            all_file_ids.extend(json.loads(msg.file_ids))

    files_by_id = database.get_files(all_file_ids)

    return serialize_chat(branched_chat, messages=messages, files_by_id=files_by_id)


@router.post("/chats/{chat_id}/messages")
async def send_message(request: Request, chat_id: str, body: SendMessageRequest):
    """
    Send a message and get AI response.

    Supports both streaming and non-streaming responses.
    For streaming, set stream=true in request body and use Server-Sent Events (SSE).
    """
    agent_manager: AgentManager = request.app.state.agent_manager

    try:
        agent = agent_manager.get(chat_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if body.stream:
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(
            _run_with_done_guard(
                agent.chat_stream(
                    message=body.message, queue=queue, file_ids=body.file_ids
                ),
                queue,
                chat_id,
            )
        )
        return StreamingResponse(
            event_stream(task, queue, chat_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await agent.chat(message=body.message, file_ids=body.file_ids)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/chats/{chat_id}/retry")
async def retry_message(request: Request, chat_id: str, body: RetryRequest):
    """
    Retry the last message by deleting the last assistant response and re-processing.

    This is useful when the LLM fails or returns an error. It resends all messages
    up to but not including the last assistant response.
    """
    agent_manager: AgentManager = request.app.state.agent_manager

    try:
        agent = agent_manager.get(chat_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if body.stream:
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(
            _run_with_done_guard(agent.retry_stream(queue=queue), queue, chat_id)
        )
        return StreamingResponse(
            event_stream(task, queue, chat_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await agent.retry()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/chats/{chat_id}/edit")
async def edit_last_user_message(
    request: Request, chat_id: str, body: EditLastMessageRequest
):
    """
    Edit the last user message and delete the assistant's response, then re-process.

    This allows users to modify their last message and get a new response from the LLM.
    """
    agent_manager: AgentManager = request.app.state.agent_manager

    try:
        agent = agent_manager.get(chat_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if body.stream:
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(
            _run_with_done_guard(
                agent.edit_stream(new_message=body.message, queue=queue),
                queue,
                chat_id,
            )
        )
        return StreamingResponse(
            event_stream(task, queue, chat_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await agent.edit(body.message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
