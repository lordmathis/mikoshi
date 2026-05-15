import asyncio
import logging
from typing import Any, Dict, List

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.plugin_base import AgentPluginBase
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent

logger = logging.getLogger(__name__)


class ReActAgent(BaseAgent):
    """ReAct agent: iterative think -> act -> observe loop."""

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        return await self._build_context(message)

    async def _process_final_response(
        self,
        response: Dict[str, Any],
        message_data: Dict[str, Any],
        queue: asyncio.Queue,
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


class ReActAgentPlugin(ReActAgent, AgentPluginBase):
    """Base class for ReAct agent plugins."""
