import asyncio
import logging
import re
from typing import Any, Dict, List, Tuple

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.plugin_base import AgentPluginBase
from mikoshi.agents.react import ReActAgent
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent

logger = logging.getLogger(__name__)

PLAN_FILENAME = "RESEARCH_PLAN.md"

PLANNING_SYSTEM_PROMPT = """\
You are a research planning agent. Given a research question, create a focused \
research plan.

Write a file called RESEARCH_PLAN.md with EXACTLY this format:

# Research: [the question]

## Tasks
- [ ] First focused sub-question
- [ ] Second focused sub-question
- [ ] Third focused sub-question

Guidelines:
- Create 3-7 focused, researchable sub-questions
- Each task should be answerable through web search
- Order from foundational to advanced
- Be specific: "What is WebAssembly GC?" is better than "Research WebAssembly"
- Use EXACTLY "- [ ] " (dash, space, bracket, space, bracket, space) for each task
- Do NOT add any other content outside this format
"""

RESEARCH_SYSTEM_PROMPT_TEMPLATE = """\
You are a research agent investigating a specific sub-question.

Original question: {original_question}
Your assigned task: {task_description}

Use web search to find relevant sources. Read and analyze the results. Write your \
findings to {findings_file}. Include sources, key facts, and relevant details.

When you have written your findings, update RESEARCH_PLAN.md:
1. Find the first "- [ ]" line (this is your task)
2. Change it to "- [x]" and append " → {findings_file}" after the task text
3. If you discovered important new sub-questions, add them as new "- [ ]" lines \
at the END of the task list

Be thorough but focused on your specific task.
"""

SYNTHESIS_SYSTEM_PROMPT = """\
You are a research synthesis agent. Read RESEARCH_PLAN.md to find all completed \
tasks and their findings files. Read every findings file and write a comprehensive \
REPORT.md that answers the original research question.

Structure your report with clear sections, cite sources, and synthesize findings \
across all sub-questions into a coherent answer.
"""


class _InnerResearchAgent(ReActAgent):
    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message},
        ]


class _FilteredQueue:
    def __init__(self, queue: asyncio.Queue, step: int):
        self._queue = queue
        self._step = step

    async def put(self, item):
        if item is STREAM_DONE or (
            isinstance(item, StreamEvent) and item.type == "done"
        ):
            return
        if isinstance(item, StreamEvent) and item.type == "message":
            data = {**item.data, "step": self._step}
            item = StreamEvent(type="message", data=data)
        await self._queue.put(item)


def _parse_pending_tasks(plan: str) -> List[Tuple[str, int]]:
    """Return [(description, 1-based index), ...] for unchecked tasks."""
    tasks = []
    idx = 0
    for line in plan.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            idx += 1
            tasks.append((stripped[5:].strip(), idx))
        elif stripped.startswith("- [x]"):
            idx += 1
    return tasks


def _parse_title(plan: str) -> str:
    for line in plan.split("\n"):
        if line.startswith("# Research:"):
            return line[len("# Research:") :].strip()
    return ""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")[:50]


class ResearchAgent(BaseAgent):
    """Multi-layered research agent. The outer loop is pure code — it reads the
    plan file and spawns inner ReAct agents for planning, researching, and
    synthesizing. RESEARCH_PLAN.md is the communication channel between loops."""

    max_outer_iterations: int = 15
    max_inner_iterations: int = 15

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        return [
            {"role": "system", "content": ""},
            {"role": "user", "content": message},
        ]

    async def _process_final_response(
        self,
        response: Dict[str, Any],
        message_data: Dict[str, Any],
        queue: asyncio.Queue,
    ) -> Dict[str, Any]:
        await self._emit(queue, STREAM_DONE)
        return {}

    async def _loop(self, message: str, queue: asyncio.Queue) -> Dict[str, Any]:
        try:
            step = 0

            plan = self._read_plan()
            if not plan:
                await self._spawn(
                    PLANNING_SYSTEM_PROMPT,
                    f"Create a research plan for: {message}",
                    queue,
                    step,
                )
                step += 1
                plan = self._read_plan()
                if not plan:
                    logger.error(
                        "chat_id=%s failed to create research plan",
                        self.chat_id,
                    )
                    await self._emit(queue, STREAM_DONE)
                    return {}

            original_question = _parse_title(plan) or message

            for _ in range(self.max_outer_iterations):
                plan = self._read_plan() or ""
                pending = _parse_pending_tasks(plan)
                if not pending:
                    break

                task_desc, task_idx = pending[0]
                findings_file = f"findings/{task_idx:02d}-{_slugify(task_desc)}.md"

                prompt = RESEARCH_SYSTEM_PROMPT_TEMPLATE.format(
                    original_question=original_question,
                    task_description=task_desc,
                    findings_file=findings_file,
                )

                await self._spawn(prompt, task_desc, queue, step)
                step += 1

            await self._spawn(
                SYNTHESIS_SYSTEM_PROMPT,
                "Read all findings files listed in RESEARCH_PLAN.md and write REPORT.md.",
                queue,
                step,
            )

            await self._emit(queue, STREAM_DONE)
        except Exception as e:
            logger.error(
                "chat_id=%s research agent error: %s",
                self.chat_id,
                e,
                exc_info=True,
            )
            await self._emit(queue, StreamEvent(type="error", data={"message": str(e)}))
            await self._emit(queue, STREAM_DONE)

    def _read_plan(self) -> str | None:
        if not self.workspace_id or not self._workspace_service:
            return None
        try:
            files = self._workspace_service.list_files_flat(self.workspace_id)
            if PLAN_FILENAME not in files:
                return None
            return self._workspace_service.read_file(self.workspace_id, PLAN_FILENAME)
        except Exception:
            return None

    async def _spawn(
        self,
        system_prompt: str,
        user_message: str,
        queue: asyncio.Queue,
        step: int,
    ) -> None:
        agent = _InnerResearchAgent(
            chat_id=self.chat_id,
            db=self.db,
            provider=self.provider,
            tool_manager=self.tool_manager,
            model_id=self.model_id,
            system_prompt=system_prompt,
            tool_servers=self.tool_servers,
            max_iterations=self.max_inner_iterations,
            workspace_id=self.workspace_id,
            data_dir=self.data_dir,
            connector_name=self.connector_name,
            workspace_config=self._workspace_config,
            workspace_service=self._workspace_service,
            skill_registry=self.skill_registry,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        filtered = _FilteredQueue(queue, step)
        agent_task = asyncio.create_task(agent._loop(user_message, queue=filtered))
        keepalive = asyncio.create_task(self._keepalive(queue, step))
        try:
            await agent_task
        finally:
            keepalive.cancel()
            try:
                await keepalive
            except asyncio.CancelledError:
                pass

    async def _keepalive(self, queue: asyncio.Queue, step: int) -> None:
        """Send heartbeat events to keep SSE connection alive during long operations."""
        try:
            while True:
                await asyncio.sleep(15)
                await queue.put(
                    StreamEvent(
                        type="message",
                        data={"role": "heartbeat", "step": step},
                    )
                )
        except asyncio.CancelledError:
            pass


class ResearchAgentPlugin(ResearchAgent, AgentPluginBase):
    pass
