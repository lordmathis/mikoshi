import asyncio
import logging
from typing import TYPE_CHECKING

from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

if TYPE_CHECKING:
    from mikoshi.agents.manager import AgentManager

logger = logging.getLogger(__name__)

SUBAGENTS_SERVER_NAME = "subagents"

DELEGATE_DESCRIPTION = (
    "Delegate a self-contained subtask to a sub-agent that runs with a fresh "
    "context and its own tools. Use for parallelizable or context-heavy work "
    "that does not need this conversation's history.\n"
    "- The sub-agent knows nothing about this conversation: include all "
    "context, files, and requirements in the task.\n"
    "- The sub-agent's final message is returned verbatim as the tool "
    "result, so instruct it in the task to end with a complete report.\n"
    "- Sub-agents cannot delegate further."
)

DELEGATE_PARAMETERS = {
    "type": "object",
    "properties": {
        "agent": {
            "type": "string",
            "description": "Name of the sub-agent persona to delegate to.",
        },
        "task": {
            "type": "string",
            "description": "Complete, self-contained task description.",
        },
    },
    "required": ["agent", "task"],
}


class SubagentTools(ToolSetHandler):
    server_name = SUBAGENTS_SERVER_NAME

    def __init__(self):
        super().__init__()
        self._agent_manager = None

    def bind_agent_manager(self, agent_manager: "AgentManager") -> None:
        self._agent_manager = agent_manager

    async def list_tools(self):
        # The agent registry doesn't exist yet at initialize() time, so the
        # available agent names are written into the description per turn.
        if self._agent_manager:
            names = ", ".join(
                sorted(self._agent_manager.agent_registry.list_agent_names())
            )
            delegate = self._tools.get("delegate")
            if delegate:
                delegate.description = f"{DELEGATE_DESCRIPTION}\nAvailable agents: {names}."
        return await super().list_tools()

    @tool(
        description=DELEGATE_DESCRIPTION,
        parameters=DELEGATE_PARAMETERS,
    )
    async def delegate(self, agent: str, task: str, context: ToolCallContext) -> str:
        if not self._agent_manager:
            return "Error: sub-agent delegation is not available."

        try:
            sub = self._agent_manager.spawn_subagent(agent, context.chat_id)
        except ValueError as e:
            return f"Error: {e}"

        logger.info(
            "chat_id=%s delegating to '%s' (phase=%s)",
            context.chat_id,
            agent,
            sub.phase,
        )
        # Imported here: agents -> base -> tools.manager -> this module is
        # a cycle at import time.
        from mikoshi.agents.streaming import FilteredQueue

        # No stream queue means no live events; the transcript still
        # persists and the result still returns.
        queue = context.stream_queue or asyncio.Queue()
        await sub._loop(task, queue=FilteredQueue(queue))
        return sub.last_response or "Sub-agent produced no output."
