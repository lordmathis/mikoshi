import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.context import format_history, generate_title, parse_mentions
from mikoshi.agents.context.messages import extract_assistant_content
from mikoshi.agents.context.skills import apply_skill_context, build_skill_context
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent
from mikoshi.db.db import Database
from mikoshi.db.models import Message
from mikoshi.providers.provider import Provider
from mikoshi.skills.registry import SkillRegistry
from mikoshi.tools.approval import ToolDeniedError
from mikoshi.tools.context import ToolCallContext, WorkspaceContext
from mikoshi.tools.manager import ToolManager
from mikoshi.workspace import WorkspaceService

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base for all agent types. Provides orchestration via Template Method pattern."""

    def __init__(
        self,
        chat_id: str,
        db: Database,
        provider: Provider,
        tool_manager: ToolManager,
        model_id: str,
        data_dir: str,
        system_prompt: str = "",
        tool_servers: List[str] = [],
        skill_registry: Optional[SkillRegistry] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_iterations: int = 5,
        title_provider: Optional[Provider] = None,
        title_model_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        connector_name: Optional[str] = None,
        workspace_config=None,
        workspace_service: Optional[WorkspaceService] = None,
    ):
        self.chat_id = chat_id
        self.db = db
        self.provider = provider
        self.tool_manager = tool_manager
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.tool_servers = list(tool_servers or [])
        self.skill_registry = skill_registry
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.workspace_id = workspace_id
        self.data_dir = data_dir
        self.connector_name = connector_name
        self._workspace_config = workspace_config
        self._workspace_service = workspace_service
        self._llm_client = provider.get_llm_client()
        self._title_llm_client = (
            title_provider.get_llm_client() if title_provider else None
        )
        self._title_model_id = title_model_id

    @abstractmethod
    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        """Build the initial messages for the agent loop. Subclasses define context strategy."""
        ...

    @abstractmethod
    async def _process_final_response(
        self,
        response: Dict[str, Any],
        message_data: Dict[str, Any],
        queue: Optional[asyncio.Queue],
    ) -> Dict[str, Any]:
        """Handle the final LLM response when no tool calls remain. Subclasses define output strategy."""
        ...

    async def _loop(
        self, message: str, queue: Optional[asyncio.Queue] = None
    ) -> Dict[str, Any]:
        logger.info(
            "chat_id=%s _loop START message_len=%d streaming=%s",
            self.chat_id,
            len(message),
            queue is not None,
        )
        messages = await self._get_iteration_context(message)
        tools = await self._get_tools(self.tool_servers)

        try:
            for iteration in range(self.max_iterations):
                logger.info(
                    "chat_id=%s iteration %d/%d — Sending %d messages to LLM (model=%s)",
                    self.chat_id,
                    iteration + 1,
                    self.max_iterations,
                    len(messages),
                    self.model_id,
                )
                for i, m in enumerate(messages):
                    role = m.get("role", "?")
                    content = m.get("content")
                    if isinstance(content, str) and len(content) > 500:
                        content = content[:500] + "... [truncated]"
                    logger.debug(
                        "  messages[%d] role=%s content=%s",
                        i,
                        role,
                        content,
                    )

                if tools:
                    tool_names = [t["function"]["name"] for t in tools]
                    logger.debug("Available tools: %s", tool_names)

                logger.info(
                    "chat_id=%s iteration %d — calling LLM provider...",
                    self.chat_id,
                    iteration + 1,
                )
                response = await self._llm(messages, tools if tools else None)
                logger.info(
                    "chat_id=%s iteration %d — LLM response received",
                    self.chat_id,
                    iteration + 1,
                )
                logger.debug(
                    "LLM raw response: %s",
                    json.dumps(response, default=str, ensure_ascii=False)[:2000],
                )

                message_data = response["choices"][0]["message"]
                finish_reason = response["choices"][0].get("finish_reason")
                has_tool_calls = bool(message_data.get("tool_calls"))
                logger.info(
                    "chat_id=%s iteration %d — finish_reason=%s, has_tool_calls=%s, content_len=%s",
                    self.chat_id,
                    iteration + 1,
                    finish_reason,
                    has_tool_calls,
                    len(message_data.get("content", "") or ""),
                )

                if (
                    not message_data.get("tool_calls")
                    or len(message_data.get("tool_calls", [])) == 0
                ):
                    logger.info(
                        "chat_id=%s no tool calls — processing final response",
                        self.chat_id,
                    )
                    return await self._process_final_response(
                        response, message_data, queue
                    )

                tool_calls_raw = message_data["tool_calls"]
                logger.info(
                    "chat_id=%s iteration %d — %d tool call(s) to execute: %s",
                    self.chat_id,
                    iteration + 1,
                    len(tool_calls_raw),
                    [tc["function"]["name"] for tc in tool_calls_raw],
                )

                msg = await self._save_message("assistant", response)
                await self._emit(
                    queue, StreamEvent(type="message", data=self._format_message(msg))
                )

                messages.append(
                    {
                        "role": "assistant",
                        "content": message_data.get("content"),
                        "tool_calls": tool_calls_raw,
                    }
                )

                for tc_idx, tool_call in enumerate(tool_calls_raw):
                    tool_name = tool_call["function"]["name"]
                    tool_args_str = tool_call["function"]["arguments"]

                    if isinstance(tool_args_str, str):
                        tool_args = json.loads(tool_args_str)
                    else:
                        tool_args = tool_args_str

                    logger.info(
                        "chat_id=%s tool call %d/%d: %s args=%s",
                        self.chat_id,
                        tc_idx + 1,
                        len(tool_calls_raw),
                        tool_name,
                        json.dumps(tool_args, default=str, ensure_ascii=False)[:1000],
                    )

                    try:
                        workspace_ctx = None
                        if self.workspace_id:
                            from mikoshi.config import WorkspaceConfig

                            wc = self._workspace_config or WorkspaceConfig()
                            workspace_ctx = WorkspaceContext(
                                workspace_id=self.workspace_id,
                                data_dir=self.data_dir,
                                connector=self.connector_name,
                                git_user_name=wc.git_user_name,
                                git_user_email=wc.git_user_email,
                            )
                        ctx = ToolCallContext(
                            provider=self.provider,
                            model_id=self.model_id,
                            chat_id=self.chat_id,
                            workspace=workspace_ctx,
                        )
                        result = await self.tool_manager.call_tool(
                            tool_name,
                            tool_args,
                            ctx,
                        )
                    except ToolDeniedError as e:
                        result = f"Tool '{e.tool_name}' was denied by the user."
                        logger.info(
                            "chat_id=%s tool %s denied by user",
                            self.chat_id,
                            tool_name,
                        )

                    result_str = str(result)
                    logger.info(
                        "chat_id=%s tool %s completed (result_len=%d)",
                        self.chat_id,
                        tool_name,
                        len(result_str),
                    )
                    logger.debug(
                        "Tool %s result: %s",
                        tool_name,
                        result_str[:1000],
                    )

                    msg = await self._save_message(
                        "tool", str(result), tool_call_id=tool_call["id"]
                    )
                    await self._emit(
                        queue,
                        StreamEvent(type="message", data=self._format_message(msg)),
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(result),
                        }
                    )

            logger.warning(
                "chat_id=%s max iterations (%d) reached without final response",
                self.chat_id,
                self.max_iterations,
            )
            msg = await self._save_message(
                "assistant", {"error": "Max iterations reached without final response"}
            )
            await self._emit(
                queue, StreamEvent(type="message", data=self._format_message(msg))
            )
            await self._emit(queue, STREAM_DONE)
            return {"error": "Max iterations reached without final response"}
        except Exception as e:
            logger.error(
                "chat_id=%s agent loop error: %s",
                self.chat_id,
                e,
                exc_info=True,
            )
            await self._emit(queue, StreamEvent(type="error", data={"message": str(e)}))
            await self._emit(queue, STREAM_DONE)
            if queue is None:
                raise

    async def chat(self, message: str, file_ids: List[str] = []) -> Dict[str, Any]:
        logger.info("chat_id=%s chat() saving user message", self.chat_id)
        await self._save_message("user", message, file_ids=file_ids)
        result = await self._loop(message)
        await self._generate_title()
        logger.info("chat_id=%s chat() complete", self.chat_id)
        return result

    async def chat_stream(
        self, message: str, queue: asyncio.Queue, file_ids: List[str] = []
    ) -> None:
        logger.info("chat_id=%s chat_stream() START", self.chat_id)
        try:
            logger.info("chat_id=%s saving user message...", self.chat_id)
            await self._save_message("user", message, file_ids=file_ids)
            logger.info("chat_id=%s user message saved, entering _loop...", self.chat_id)
            await self._loop(message, queue=queue)
            logger.info("chat_id=%s _loop returned, generating title...", self.chat_id)
            await self._generate_title()
            logger.info("chat_id=%s chat_stream() COMPLETE", self.chat_id)
        except Exception as e:
            logger.error(
                "chat_id=%s chat_stream() unexpected error: %s",
                self.chat_id,
                e,
                exc_info=True,
            )
            raise

    def _prepare_retry(self) -> Optional[str]:
        history = self.db.get_chat_history(self.chat_id)
        last_assistant = None
        last_user = None
        for msg in reversed(history):
            if msg.role == "assistant" and last_assistant is None:
                last_assistant = msg
            elif msg.role == "user" and last_user is None:
                last_user = msg
            if last_assistant and last_user:
                break

        if not last_user:
            return None

        if last_assistant:
            for msg in history:
                if msg.role == "tool" and msg.sequence > last_assistant.sequence:
                    self.db.delete_message(msg.id)
            self.db.delete_message(last_assistant.id)

        return last_user.content

    async def retry(self) -> Dict[str, Any]:
        message = self._prepare_retry()
        if not message:
            return {"error": "No user message to retry"}
        return await self._loop(message)

    async def retry_stream(self, queue: asyncio.Queue) -> None:
        logger.info("chat_id=%s retry_stream() START", self.chat_id)
        message = self._prepare_retry()
        if not message:
            logger.warning("chat_id=%s retry_stream() no user message to retry", self.chat_id)
            await queue.put(
                StreamEvent(type="error", data={"message": "No user message to retry"})
            )
            await queue.put(STREAM_DONE)
            return
        logger.info("chat_id=%s retry_stream() entering _loop...", self.chat_id)
        await self._loop(message, queue=queue)
        logger.info("chat_id=%s retry_stream() COMPLETE", self.chat_id)

    def _prepare_edit(self) -> Optional[Message]:
        history = self.db.get_chat_history(self.chat_id)
        last_user = None
        last_assistant = None
        for msg in reversed(history):
            if msg.role == "user" and last_user is None:
                last_user = msg
            elif msg.role == "assistant" and last_assistant is None:
                last_assistant = msg
            if last_user and last_assistant:
                break

        if not last_user:
            return None

        if last_assistant:
            for msg in history:
                if msg.sequence > last_user.sequence:
                    self.db.delete_message(msg.id)

        return last_user

    async def edit(self, new_message: str) -> Dict[str, Any]:
        last_user = self._prepare_edit()

        if not last_user:
            return {"error": "No user message to edit"}

        file_ids_str = getattr(last_user, "file_ids", None)
        file_ids = json.loads(file_ids_str) if file_ids_str else []

        self.db.delete_message(last_user.id)
        await self._save_message("user", new_message, file_ids=file_ids)

        return await self._loop(new_message)

    async def edit_stream(self, new_message: str, queue: asyncio.Queue) -> None:
        logger.info("chat_id=%s edit_stream() START", self.chat_id)
        last_user = self._prepare_edit()

        if not last_user:
            logger.warning("chat_id=%s edit_stream() no user message to edit", self.chat_id)
            await queue.put(
                StreamEvent(type="error", data={"message": "No user message to edit"})
            )
            await queue.put(STREAM_DONE)
            return

        file_ids_str = getattr(last_user, "file_ids", None)
        file_ids = json.loads(file_ids_str) if file_ids_str else []

        self.db.delete_message(last_user.id)
        await self._save_message("user", new_message, file_ids=file_ids)

        logger.info("chat_id=%s edit_stream() entering _loop...", self.chat_id)
        await self._loop(new_message, queue=queue)
        logger.info("chat_id=%s edit_stream() COMPLETE", self.chat_id)

    @staticmethod
    def _format_message(msg: Message) -> dict:
        return {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "reasoning_content": msg.reasoning_content,
            "tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else None,
            "tool_call_id": msg.tool_call_id,
            "sequence": msg.sequence,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "files": [],
        }

    @staticmethod
    async def _emit(queue: Optional[asyncio.Queue], event: StreamEvent) -> None:
        if queue is not None:
            await queue.put(event)

    async def _save_message(
        self,
        role: str,
        content_or_response: str | Dict[str, Any],
        file_ids: List[str] = [],
        tool_call_id: Optional[str] = None,
    ) -> Message:
        if role == "assistant":
            if isinstance(content_or_response, dict):
                if "error" in content_or_response:
                    return self.db.save_message(
                        self.chat_id,
                        "assistant",
                        f"Error: {content_or_response['error']}",
                    )
                else:
                    content, reasoning, tool_calls = extract_assistant_content(
                        content_or_response
                    )
                    tool_calls_json = json.dumps(tool_calls) if tool_calls else None
                    return self.db.save_message(
                        self.chat_id,
                        "assistant",
                        content,
                        reasoning_content=reasoning,
                        tool_calls=tool_calls_json,
                    )
            else:
                return self.db.save_message(
                    self.chat_id, "assistant", content_or_response
                )
        elif role == "tool":
            return self.db.save_message(
                self.chat_id,
                "tool",
                str(content_or_response),
                tool_call_id=tool_call_id,
            )
        else:
            file_ids_json = json.dumps(file_ids) if file_ids else None
            msg = self.db.save_message(
                self.chat_id, "user", content_or_response, file_ids=file_ids_json
            )
            if file_ids:
                self.db.attach_files(file_ids)
            return msg

    async def _build_context(self, message: str) -> List[ChatCompletionMessageParam]:
        mentioned_skills = parse_mentions(message)
        skill_context, required_tool_servers = build_skill_context(
            mentioned_skills, self.skill_registry
        )

        if required_tool_servers:
            new_servers = [
                s for s in required_tool_servers if s not in self.tool_servers
            ]
            if new_servers:
                self.tool_servers = self.tool_servers + new_servers
                self.db.update_chat(
                    self.chat_id, tool_servers=json.dumps(self.tool_servers)
                )
                logger.info(
                    f"Activated skill tool servers for chat {self.chat_id}: {new_servers}"
                )

        messages = format_history(self.db, self.chat_id)
        messages = apply_skill_context(messages, skill_context)

        if self.system_prompt:
            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": self.system_prompt})

        return messages

    async def _get_tools(self, servers: List[str]) -> List[dict]:
        api_tools = []
        for tool_server in servers:
            tools = await self.tool_manager.list_tools(tool_server)
            for tool in tools:
                if hasattr(tool, "parameters"):
                    parameters = tool.parameters
                else:
                    parameters = {}
                api_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": f"{tool_server}__{tool.name}",
                            "description": tool.description,
                            "parameters": parameters,
                        },
                    }
                )
        return api_tools

    async def _llm(
        self,
        messages: List[ChatCompletionMessageParam],
        tools: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        return await self._llm_client.chat_completion(
            model=self.model_id,
            messages=messages,
            tools=tools if tools else None,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    async def _generate_title(self) -> None:
        client = self._title_llm_client or self._llm_client
        model = self._title_model_id or self.model_id
        asyncio.create_task(generate_title(self.chat_id, self.db, client, model))
