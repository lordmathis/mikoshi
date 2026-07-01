import asyncio
import logging
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.plugin_base import AgentPluginBase
from mikoshi.agents.react import ReActAgent
from mikoshi.agents.research.helpers import (
    _FilteredQueue,
    _parse_pending_tasks,
    _parse_title,
    _slugify,
)
from mikoshi.agents.research.prompts import PLAN_FILENAME, REPORT_FILENAME
from mikoshi.agents.research.stages import (
    Planner,
    Researcher,
    Replanner,
    Synthesizer,
)
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent
from mikoshi.tools.workspace import _workspace_result

logger = logging.getLogger(__name__)


class _InnerResearchAgent(ReActAgent):
    """ReAct inner agent whose transcript persists across `_loop` calls: a
    second `_loop(message)` appends `message` as a user turn and continues
    the same in-memory conversation instead of starting fresh."""

    def __init__(self, **kwargs):
        self.phase: Optional[str] = kwargs.pop("phase", None)
        super().__init__(**kwargs)
        self._messages: List[ChatCompletionMessageParam] = []
        self.last_response: str = ""

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        if self._messages:
            self._messages.append({"role": "user", "content": message})
            return self._messages
        self._messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message},
        ]
        return self._messages

    def _format_message(self, msg) -> dict:
        data = BaseAgent._format_message(msg)
        if self.phase:
            data["phase"] = self.phase
        return data

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


class ResearchAgent(BaseAgent):
    """Multi-layered research agent. The outer loop is pure code — it reads the
    plan file and spawns inner ReAct agents for planning, researching, and
    synthesizing. RESEARCH_PLAN.md is the communication channel between loops.

    Acts as the `StageContext` for the stage classes: it provides spawn + file
    state ops, and decides control flow from file state (never model output)."""

    max_outer_iterations: int = 15
    max_inner_iterations: int = 15
    context_window: Optional[int] = None

    _active_queue: Optional[asyncio.Queue] = None

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
        self._active_queue = queue
        try:
            plan = self._read_plan()
            if not plan:
                if not await Planner(self, message).apply(queue):
                    logger.error(
                        "chat_id=%s failed to create research plan",
                        self.chat_id,
                    )
                    await self._emit(queue, STREAM_DONE)
                    return {}
                plan = self._read_plan()
            elif self.file_exists(REPORT_FILENAME):
                await Planner(self, message, plan, self._read_report()).apply(queue)
                plan = self._read_plan() or plan

            original_question = _parse_title(plan) or message

            for _ in range(self.max_outer_iterations):
                self._reconcile_plan()
                plan = self._read_plan() or ""
                pending = _parse_pending_tasks(plan)
                if not pending:
                    break

                task_desc, task_idx = pending[0]
                findings_path = await Researcher(
                    self, task_desc, task_idx, original_question
                ).apply(queue)

                self._reconcile_plan()
                plan = self._read_plan() or ""
                if _parse_pending_tasks(plan) and findings_path:
                    findings = self.read_file(findings_path)
                    if findings:
                        await Replanner(self, original_question, plan, findings).apply(
                            queue
                        )

            self._reconcile_plan()
            await Synthesizer(self, original_question).apply(queue)

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
        finally:
            self._active_queue = None
        return {}

    # --- file-state ops (source of truth for control flow) ---

    def _read_plan(self) -> Optional[str]:
        if PLAN_FILENAME not in self.list_files():
            return None
        return self.read_file(PLAN_FILENAME) or None

    def _read_report(self) -> str:
        return self.read_file(REPORT_FILENAME)

    def read_file(self, path: str) -> str:
        if not self.workspace_id or not self._workspace_service:
            return ""
        try:
            return self._workspace_service.read_file(self.workspace_id, path)
        except Exception:
            return ""

    def file_exists(self, path: str) -> bool:
        if not self.workspace_id or not self._workspace_service:
            return False
        try:
            return path in self._workspace_service.list_files_flat(self.workspace_id)
        except Exception:
            return False

    def write_file(self, path: str, content: str) -> None:
        if not self.workspace_id or not self._workspace_service:
            return
        self._workspace_service.write_file(self.workspace_id, path, content)
        self._emit_workspace_change(path)

    def _emit_workspace_change(self, path: str) -> None:
        """Emit the same `__workspace` tool message the workspace write tool
        produces, so the FE reloads the file tree and the open file. Mirrors
        `BaseAgent._execute_tool_calls` — direct writes here would otherwise
        bypass the streaming layer (e.g. REPORT.md, RESEARCH_PLAN.md)."""
        queue = self._active_queue
        if queue is None:
            return
        msg = self.db.save_message(
            self.chat_id, "tool", _workspace_result(f"Wrote {path}", paths=[path])
        )
        asyncio.create_task(
            self._emit(
                queue, StreamEvent(type="message", data=self._format_message(msg))
            )
        )

    def list_files(self) -> List[str]:
        if not self.workspace_id or not self._workspace_service:
            return []
        try:
            return self._workspace_service.list_files_flat(self.workspace_id)
        except Exception:
            return []

    def _reconcile_plan(self) -> None:
        """Check off tasks whose findings file already exists.

        The research agent sometimes writes findings but forgets to update the
        plan; without this, the outer loop would re-research the same task and
        synthesis would miss the findings. Findings-file existence is the source
        of truth.
        """
        plan = self._read_plan()
        if not plan:
            return
        files = set(self.list_files())

        new_lines = []
        changed = False
        idx = 0
        for line in plan.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                idx += 1
                desc = stripped[5:].strip()
                findings_file = f"findings/{idx:02d}-{_slugify(desc)}.md"
                if findings_file in files:
                    new_lines.append(f"- [x] {desc}")
                    changed = True
                    continue
            elif stripped.startswith("- [x]"):
                idx += 1
            new_lines.append(line)

        if changed:
            self.write_file(PLAN_FILENAME, "\n".join(new_lines))

    # --- shared runner for stages ---

    async def spawn(
        self,
        system_prompt: str,
        user_message: str,
        queue: asyncio.Queue,
        *,
        web: bool = False,
        tool_servers: Optional[List[str]] = None,
        phase: Optional[str] = None,
    ) -> _InnerResearchAgent:
        base = (
            list(tool_servers)
            if tool_servers is not None
            else list(self.tool_servers or [])
        )
        if web and "web_tools" not in base:
            base.append("web_tools")
        agent = _InnerResearchAgent(
            chat_id=self.chat_id,
            db=self.db,
            provider=self.provider,
            tool_manager=self.tool_manager,
            model_id=self.model_id,
            system_prompt=system_prompt,
            tool_servers=base,
            max_iterations=self.max_inner_iterations,
            workspace_id=self.workspace_id,
            data_dir=self.data_dir,
            connector_name=self.connector_name,
            workspace_config=self._workspace_config,
            workspace_service=self._workspace_service,
            skill_registry=self.skill_registry,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            phase=phase,
        )
        filtered = _FilteredQueue(queue)
        await agent._loop(user_message, queue=filtered)
        return agent


class ResearchAgentPlugin(ResearchAgent, AgentPluginBase):
    pass
