import asyncio
from typing import Any, Dict, List

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.workspace import WorkspaceAgent


class SubAgent(WorkspaceAgent):
    """Inner agent whose transcript lives in memory and in the DB tagged
    with its phase — never in the parent conversation's LLM context. The
    first `_loop(message)` seeds [persona, workspace, user] and persists the
    task message; a second `_loop(message)` appends it and continues the
    same in-memory conversation (used for nudges)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: List[ChatCompletionMessageParam] = []
        self.last_response: str = ""

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        if self._messages:
            self._messages.append({"role": "user", "content": message})
            return self._messages

        self._messages = [{"role": "system", "content": self.system_prompt}]
        self._insert_workspace_context(self._messages)
        await self._save_message("user", message)
        self._messages.append({"role": "user", "content": message})
        return self._messages

    async def _process_final_response(
        self,
        response: Dict[str, Any],
        message_data: Dict[str, Any],
        queue: asyncio.Queue,
    ) -> Dict[str, Any]:
        self.last_response = message_data.get("content") or ""
        self._messages.append(
            {"role": "assistant", "content": message_data.get("content")}
        )
        return await super()._process_final_response(response, message_data, queue)
