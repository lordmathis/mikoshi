from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Protocol

from mikoshi.agents.research.helpers import (
    DEFAULT_CONTEXT_WINDOW,
    _FilteredQueue,
    _batch_findings,
    _count_tokens,
    _format_material_block,
    _slugify,
    _parse_findings_files,
    _summarize_user_prompt,
    _synthesis_budget,
    _synthesis_user_prompt,
)
from mikoshi.agents.research.prompts import (
    NUDGE_PROMPT_TEMPLATE,
    PLAN_FILENAME,
    PLANNER_SYSTEM_PROMPT,
    REPORT_FILENAME,
    RESEARCH_SYSTEM_PROMPT_TEMPLATE,
    REPLANNER_SYSTEM_PROMPT,
    SYNTHESIS_SUMMARIZE_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from mikoshi.tools.workspace import WORKSPACE_SERVER_NAME

if TYPE_CHECKING:
    from mikoshi.agents.research.agent import _InnerResearchAgent

logger = logging.getLogger(__name__)


class StageContext(Protocol):
    """Narrow orchestrator interface that stages depend on."""

    workspace_id: Optional[str]
    chat_id: str
    context_window: Optional[int]

    async def spawn(
        self,
        system_prompt: str,
        user_message: str,
        queue: asyncio.Queue,
        *,
        web: bool = False,
        tool_servers: Optional[List[str]] = None,
        phase: Optional[str] = None,
    ) -> "_InnerResearchAgent": ...

    def file_exists(self, path: str) -> bool: ...

    def read_file(self, path: str) -> str: ...

    def write_file(self, path: str, content: str) -> None: ...

    def list_files(self) -> List[str]: ...


class StageProtocol(Protocol):
    async def apply(self, queue: asyncio.Queue) -> Optional[str]: ...


class Stage:
    """Shared spawn -> nudge -> retry workhorse.

    `success()` decides whether each later step runs. A predicate that always
    returns True collapses the stage to a single best-effort spawn (used by
    Planner-extend and Replanner, where not producing output is valid).
    """

    def __init__(
        self,
        ctx: StageContext,
        system_prompt: str,
        user_message: str,
        success: Callable[[], bool],
        artifact_path: str,
        *,
        tool_servers: Optional[List[str]],
        web: bool = False,
        phase: str = "",
    ):
        self.ctx = ctx
        self.system_prompt = system_prompt
        self.user_message = user_message
        self.success = success
        self.artifact_path = artifact_path
        self.tool_servers = tool_servers
        self.web = web
        self.phase = phase

    def _nudge(self) -> str:
        return NUDGE_PROMPT_TEMPLATE.format(file=self.artifact_path)

    async def _spawn(self, queue: asyncio.Queue) -> "_InnerResearchAgent":
        return await self.ctx.spawn(
            self.system_prompt,
            self.user_message,
            queue,
            web=self.web,
            tool_servers=self.tool_servers,
            phase=self.phase,
        )

    async def apply(self, queue: asyncio.Queue) -> Optional[str]:
        agent = await self._spawn(queue)
        if self.success():
            return self.artifact_path

        logger.info(
            "chat_id=%s %s not produced after spawn, sending nudge",
            self.ctx.chat_id,
            self.artifact_path,
        )
        await agent._loop(self._nudge(), queue=_FilteredQueue(queue))
        if self.success():
            return self.artifact_path

        logger.warning(
            "chat_id=%s %s still missing after nudge, fresh retry",
            self.ctx.chat_id,
            self.artifact_path,
        )
        await self._spawn(queue)
        return self.artifact_path if self.success() else None


def _planner_message(message: str, plan: Optional[str], report: Optional[str]) -> str:
    plan_block = plan if plan else "(none yet)"
    report_block = report if report else "(none yet)"
    return (
        f"User's message: {message}\n\n"
        f"Existing RESEARCH_PLAN.md:\n{plan_block}\n\n"
        f"Existing REPORT.md:\n{report_block}\n\n"
        f"Use the workspace write tool to save RESEARCH_PLAN.md now."
    )


class Planner(Stage):
    """Planner stage. With plan/report supplied -> extend (single best-effort
    spawn appending follow-up tasks); without -> create (spawn/nudge/retry until
    RESEARCH_PLAN.md exists)."""

    def __init__(
        self,
        ctx: StageContext,
        message: str,
        plan: Optional[str] = None,
        report: Optional[str] = None,
    ):
        is_extend = bool(plan)
        if is_extend:
            logger.info(
                "chat_id=%s follow-up: extending plan (%d-char report inline)",
                ctx.chat_id,
                len(report or ""),
            )
        super().__init__(
            ctx,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_message=_planner_message(message, plan, report),
            success=(lambda: True) if is_extend else (lambda: ctx.file_exists(PLAN_FILENAME)),
            artifact_path=PLAN_FILENAME,
            tool_servers=[WORKSPACE_SERVER_NAME],
            phase="research_plan",
        )


class Researcher(Stage):
    """Researcher stage for one plan task. Spawns with web tools and the
    inherited orchestrator tool servers; recovers via nudge/retry if the
    findings file is not written."""

    def __init__(
        self,
        ctx: StageContext,
        task_desc: str,
        task_idx: int,
        original_question: str,
    ):
        findings_file = f"findings/{task_idx:02d}-{_slugify(task_desc)}.md"
        super().__init__(
            ctx,
            system_prompt=RESEARCH_SYSTEM_PROMPT_TEMPLATE.format(
                original_question=original_question,
                task_description=task_desc,
                findings_file=findings_file,
            ),
            user_message=task_desc,
            success=lambda: ctx.file_exists(findings_file),
            artifact_path=findings_file,
            tool_servers=None,
            web=True,
            phase=f"query_{task_idx:02d}",
        )


def _replanner_message(
    original_question: str, plan: str, findings: str
) -> str:
    return (
        f"Original question: {original_question}\n\n"
        f"Current RESEARCH_PLAN.md:\n{plan}\n\n"
        f"Findings from the task just completed:\n---\n{findings}\n---\n\n"
        f"Revise the remaining unchecked tasks in RESEARCH_PLAN.md now using "
        f"the workspace write tool."
    )


class Replanner(Stage):
    """Replanner stage. Always-true success predicate: a single spawn, because
    not changing the plan is a valid outcome (e.g. "No changes needed.")."""

    def __init__(
        self,
        ctx: StageContext,
        original_question: str,
        plan: str,
        findings: str,
    ):
        logger.info(
            "chat_id=%s replanning: %d-char findings inline",
            ctx.chat_id,
            len(findings),
        )
        super().__init__(
            ctx,
            system_prompt=REPLANNER_SYSTEM_PROMPT,
            user_message=_replanner_message(original_question, plan, findings),
            success=lambda: True,
            artifact_path=PLAN_FILENAME,
            tool_servers=[WORKSPACE_SERVER_NAME],
            phase="replan",
        )


class Synthesizer:
    """Synthesizer stage. Different contract from the shared Stage: no tools,
    emits the report/summary as its response, and the outer code writes the
    file. Owns the fast/reduce decision and batching."""

    def __init__(self, ctx: StageContext, original_question: str):
        self.ctx = ctx
        self.original_question = original_question

    async def apply(self, queue: asyncio.Queue) -> None:
        ctx = self.ctx
        if not ctx.workspace_id:
            return

        plan = ctx.read_file(PLAN_FILENAME) or ""
        paths = [p for p in _parse_findings_files(plan) if ctx.file_exists(p)]
        if not paths:
            logger.warning(
                "chat_id=%s no findings files found, skipping synthesis",
                ctx.chat_id,
            )
            return

        items: List[Any] = []
        for path in paths:
            content = ctx.read_file(path)
            if not content:
                logger.warning(
                    "chat_id=%s %s empty or unreadable, skipping",
                    ctx.chat_id,
                    path,
                )
                continue
            items.append((path, content, _count_tokens(content)))

        if not items:
            logger.warning(
                "chat_id=%s all findings files unreadable, skipping synthesis",
                ctx.chat_id,
            )
            return

        total_tokens = sum(t for _, _, t in items)
        context_window = ctx.context_window or DEFAULT_CONTEXT_WINDOW
        budget = _synthesis_budget(context_window)

        if total_tokens <= budget:
            logger.info(
                "chat_id=%s synthesis fast-path: %d findings, %d tokens (budget %d)",
                ctx.chat_id,
                len(items),
                total_tokens,
                budget,
            )
            await self._run_synthesis_agent(
                SYNTHESIS_SYSTEM_PROMPT,
                _synthesis_user_prompt(
                    self.original_question, _format_material_block(items)
                ),
                REPORT_FILENAME,
                queue,
                phase="synthesize",
            )
            return

        logger.info(
            "chat_id=%s synthesis reduce-path: %d findings, %d tokens, budget %d",
            ctx.chat_id,
            len(items),
            total_tokens,
            budget,
        )
        batches = _batch_findings(items, budget)
        for i, batch in enumerate(batches, 1):
            batch_file = f"synthesis/batch_{i:02d}.md"
            await self._run_synthesis_agent(
                SYNTHESIS_SUMMARIZE_PROMPT,
                _summarize_user_prompt(
                    self.original_question, _format_material_block(batch)
                ),
                batch_file,
                queue,
                phase="summarize",
            )

        batch_paths = sorted(
            p
            for p in ctx.list_files()
            if p.startswith("synthesis/batch_") and p.endswith(".md")
        )
        summary_items: List[Any] = []
        for path in batch_paths:
            content = ctx.read_file(path)
            if not content:
                logger.warning(
                    "chat_id=%s %s empty or unreadable, skipping",
                    ctx.chat_id,
                    path,
                )
                continue
            summary_items.append((path, content, _count_tokens(content)))

        if not summary_items:
            logger.warning(
                "chat_id=%s no batch summaries produced, skipping report",
                ctx.chat_id,
            )
            return

        summary_tokens = sum(t for _, _, t in summary_items)
        if summary_tokens > budget:
            logger.warning(
                "chat_id=%s batch summaries (%d tokens) exceed budget (%d); "
                "writing best-effort report",
                ctx.chat_id,
                summary_tokens,
                budget,
            )

        block = _format_material_block(summary_items)
        await self._run_synthesis_agent(
            SYNTHESIS_SYSTEM_PROMPT,
            _synthesis_user_prompt(
                self.original_question, block, from_summaries=True
            ),
            REPORT_FILENAME,
            queue,
            phase="synthesize",
        )

    async def _run_synthesis_agent(
        self,
        system_prompt: str,
        user_message: str,
        output_path: str,
        queue: asyncio.Queue,
        *,
        phase: str = "synthesize",
    ) -> None:
        """Run a no-tool synthesis/summary agent and persist its text response.

        Synthesis output is fundamentally text, and the model produces it most
        reliably as a response (not via a write-tool call). So the agent gets no
        tools, emits the report/summary as its response, and this outer code
        writes the file. The response also streams live to the user."""
        agent = await self.ctx.spawn(
            system_prompt, user_message, queue, tool_servers=[], phase=phase
        )
        content = agent.last_response
        if not content:
            logger.warning(
                "chat_id=%s synthesis agent produced no response; %s not written",
                self.ctx.chat_id,
                output_path,
            )
            return
        self.ctx.write_file(output_path, content)
        logger.info(
            "chat_id=%s wrote %s (%d chars)",
            self.ctx.chat_id,
            output_path,
            len(content),
        )
