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
    try:
        await coro
    except asyncio.CancelledError:
        logger.warning("chat_id=%s stream task cancelled", chat_id)
        raise
    except Exception as e:
        logger.error("chat_id=%s stream task failed outside _loop: %s", chat_id, e, exc_info=True)
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
            logger.debug("chat_id=%s SSE event: type=%s", chat_id, event.type)
            yield f"data: {json.dumps(asdict(event))}\n\n"
            if event.type == "done":
                logger.debug("chat_id=%s SSE stream complete", chat_id)
                break
    except GeneratorExit:
        logger.warning("chat_id=%s SSE client disconnected, cancelling task", chat_id)
        task.cancel()
        raise


def _run_agent_stream(chat_id: str, agent_manager: AgentManager, coro_factory):
    try:
        agent = agent_manager.get(chat_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_run_with_done_guard(coro_factory(agent, queue), queue, chat_id))
    return StreamingResponse(
        event_stream(task, queue, chat_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _collect_message_files(database, messages) -> dict:
    all_file_ids = []
    for msg in messages:
        if msg.file_ids:
            all_file_ids.extend(json.loads(msg.file_ids))
    return database.get_files(all_file_ids)


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
    file_ids: Optional[List[str]] = None


class BranchChatRequest(BaseModel):
    message_id: str
    title: Optional[str] = None


class EditLastMessageRequest(BaseModel):
    message: str


@router.post("/chats")
async def create_chat(request: Request, body: CreateChatRequest):
    database = request.app.state.database
    agent_manager: AgentManager = request.app.state.agent_manager

    chat = database.create_chat(title=body.title, workspace_id=body.workspace_id)

    try:
        agent_manager.create(chat_id=chat.id, config=body.config.model_dump())
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
    database = request.app.state.database
    chats = database.list_chats(limit=limit)
    return {"chats": [serialize_chat(chat) for chat in chats]}


@router.get("/chats/{chat_id}")
async def get_chat(request: Request, chat_id: str):
    database = request.app.state.database
    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

    messages = database.get_chat_history(chat_id)
    files_by_id = _collect_message_files(database, messages)
    return serialize_chat(chat, messages=messages, files_by_id=files_by_id)


@router.delete("/chats/{chat_id}")
async def delete_chat(request: Request, chat_id: str):
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
            raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")

    updated_chat = database.update_chat(chat_id, **update_kwargs)
    if not updated_chat:
        raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")
    return serialize_chat(updated_chat)


@router.post("/chats/{chat_id}/branch")
async def branch_chat(request: Request, chat_id: str, body: BranchChatRequest):
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
            "tool_servers": json.loads(branched_chat.tool_servers) if branched_chat.tool_servers else None,
            "model_params": json.loads(branched_chat.model_params) if branched_chat.model_params else None,
        }
        agent_manager.create(chat_id=branched_chat.id, config=config)
    except Exception as e:
        database.delete_chat(branched_chat.id)
        raise HTTPException(status_code=500, detail=f"Failed to create agent for branch: {str(e)}")

    messages = database.get_chat_history(branched_chat.id)
    files_by_id = _collect_message_files(database, messages)
    return serialize_chat(branched_chat, messages=messages, files_by_id=files_by_id)


@router.post("/chats/{chat_id}/messages")
async def send_message(request: Request, chat_id: str, body: SendMessageRequest):
    agent_manager: AgentManager = request.app.state.agent_manager
    return _run_agent_stream(
        chat_id, agent_manager,
        lambda agent, q: agent.chat(message=body.message, queue=q, file_ids=body.file_ids),
    )


@router.post("/chats/{chat_id}/retry")
async def retry_message(request: Request, chat_id: str):
    agent_manager: AgentManager = request.app.state.agent_manager
    return _run_agent_stream(
        chat_id, agent_manager,
        lambda agent, q: agent.retry(queue=q),
    )


@router.post("/chats/{chat_id}/edit")
async def edit_last_user_message(request: Request, chat_id: str, body: EditLastMessageRequest):
    agent_manager: AgentManager = request.app.state.agent_manager
    return _run_agent_stream(
        chat_id, agent_manager,
        lambda agent, q: agent.edit(new_message=body.message, queue=q),
    )
