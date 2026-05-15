import json
import logging
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.plugin_base import AgentPluginBase
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent

logger = logging.getLogger(__name__)


class StructuredAgent(BaseAgent):
    system_prompt: str = (
        "You are a stateful agent that maintains persistent state across conversation "
        "turns. You receive a CURRENT STATE object and must return an updated state "
        "along with a message to the user.\n\n"
        "## Output Format\n\n"
        "When you have finished calling any tools and are ready to respond, your "
        "final response MUST be a single valid JSON object with exactly two top-level "
        "keys:\n\n"
        '- "user_message" (string): The plain-text message to display to the user.\n'
        '- "new_state" (object): The updated state object. It will be merged into the '
        "current state for the next turn. Omitted keys are preserved from the "
        "current state.\n\n"
        "## Example\n\n"
        'Current state: {"count": 0, "name": "Alice"}\n'
        'User: "Increment the counter and change the name to Bob."\n\n'
        "Your response:\n"
        "```json\n"
        '{"user_message": "Done! Incremented the counter to 1 and updated the name '
        'to Bob.", "new_state": {"count": 1, "name": "Bob"}}\n'
        "```\n\n"
        "## Rules\n\n"
        "- Do NOT include any text outside the JSON object in your final response.\n"
        "- If you call tools, wait for all tool results before producing your final "
        "JSON response.\n"
        '- "new_state" must be a valid JSON object (not a string, number, or array).\n'
        '- Only include keys in "new_state" that you intend to update or add.'
    )

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        state = self.db.get_chat_state(self.chat_id)
        system_content = self.system_prompt + f"\n\nCURRENT STATE: {json.dumps(state)}"
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": message},
        ]

    async def _process_final_response(
        self,
        response: Dict[str, Any],
        message_data: Dict[str, Any],
        queue: Optional[Any],
    ) -> Dict[str, Any]:
        user_msg, new_state = self._parse_final_response(
            message_data.get("content", "")
        )
        merged_state = {**self.db.get_chat_state(self.chat_id), **new_state}
        self.db.update_chat_state(self.chat_id, merged_state)

        msg = await self._save_message("assistant", user_msg)
        await self._emit(
            queue, StreamEvent(type="message", data=self._format_message(msg))
        )
        await self._emit(queue, STREAM_DONE)
        return {"user_message": user_msg, "new_state": merged_state}

    def _parse_final_response(self, content: str) -> tuple:
        if not content:
            return content, {}

        text = content.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
            user_msg = parsed.get("user_message", content)
            new_state = parsed.get("new_state", {})
            return user_msg, new_state
        except (json.JSONDecodeError, TypeError):
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                user_msg = parsed.get("user_message", content)
                new_state = parsed.get("new_state", {})
                return user_msg, new_state
            except (json.JSONDecodeError, TypeError):
                pass

        return content, {}


class StructuredAgentPlugin(StructuredAgent, AgentPluginBase):
    pass
