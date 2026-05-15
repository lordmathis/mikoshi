import logging
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent
from mikoshi.db.db import Database
from mikoshi.providers.provider import Provider
from mikoshi.skills.registry import SkillRegistry
from mikoshi.tools.manager import ToolManager

logger = logging.getLogger(__name__)


class ReActAgent(BaseAgent):
    """ReAct agent: iterative think -> act -> observe loop."""

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
        workspace_service=None,
    ):
        super().__init__(
            chat_id=chat_id,
            db=db,
            provider=provider,
            tool_manager=tool_manager,
            model_id=model_id,
            system_prompt=system_prompt,
            tool_servers=tool_servers,
            skill_registry=skill_registry,
            temperature=temperature,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            title_provider=title_provider,
            title_model_id=title_model_id,
            workspace_id=workspace_id,
            data_dir=data_dir,
            connector_name=connector_name,
            workspace_config=workspace_config,
            workspace_service=workspace_service,
        )

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        return await self._build_context(message)

    async def _process_final_response(
        self,
        response: Dict[str, Any],
        message_data: Dict[str, Any],
        queue: Optional[Any],
    ) -> Dict[str, Any]:
        logger.info(
            "chat_id=%s _process_final_response — saving assistant message",
            self.chat_id,
        )
        msg = await self._save_message("assistant", response)
        await self._emit(
            queue, StreamEvent(type="message", data=self._format_message(msg))
        )
        logger.info(
            "chat_id=%s _process_final_response — emitting STREAM_DONE",
            self.chat_id,
        )
        await self._emit(queue, STREAM_DONE)
        return response


class ReActAgentPlugin(ReActAgent):
    """Base class for ReAct agent plugins."""

    default: bool = False
    name: str = ""
    provider_id: str = ""
    model_id: str = ""
    system_prompt: str = ""
    tool_servers: List[str] = []
    max_iterations: int = 5
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def post_init(self) -> None:
        """Called after all dependencies are injected. Override for custom setup."""
        pass
