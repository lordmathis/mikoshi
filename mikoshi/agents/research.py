import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import tiktoken
from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.plugin_base import AgentPluginBase
from mikoshi.agents.react import ReActAgent
from mikoshi.agents.streaming import STREAM_DONE, StreamEvent
from mikoshi.tools.workspace import WORKSPACE_SERVER_NAME

logger = logging.getLogger(__name__)

PLAN_FILENAME = "RESEARCH_PLAN.md"
REPORT_FILENAME = "REPORT.md"

PLANNER_SYSTEM_PROMPT = """\
Your ONLY job is to write RESEARCH_PLAN.md. You do not do research, you do not \
write findings, and you do not write REPORT.md — separate agents handle those.

You are given the current state inline and the user's message. Do exactly ONE of \
the following, save the result with the workspace write tool, then STOP:

1. If NO plan exists yet, create a focused plan for the user's question in \
EXACTLY this format:

# Research: [the question]

## Tasks
- [ ] First focused sub-question
- [ ] Second focused sub-question
- [ ] Third focused sub-question

New-plan guidelines:
- 5-7 sub-questions. Cover the question thoroughly, but every task should be \
one the user would actually want answered — don't pad with background or \
tangents just to reach the count.
- Each task must directly serve answering the user's actual question. The end \
result should be a clear, well-supported answer a normal person can understand \
— based on evidence, not a literature review padded with background, jargon, or \
tangents. If a premise in the question is genuinely contested (e.g. whether a \
claimed effect is even real), that is worth at most one task — otherwise don't \
pad.
- Be specific and answerable through web search: "What is the evidence that X \
causes Y?" beats "Research X."
- Order tasks so they collectively build the answer the user is looking for.
- Use EXACTLY "- [ ] " (dash, space, bracket, space, bracket, space) per task.

2. If a plan AND a finished REPORT.md already exist, the user wants to dig \
deeper. APPEND new "- [ ] " tasks relevant to the ORIGINAL question and the \
user's request. Do not remove or modify existing tasks; only add tasks directly \
relevant to the request, and ignore topics the user did not raise.

After saving, respond with ONE short confirmation sentence (e.g. "Plan \
created.") and STOP. Do not check off tasks, do not call any further tools, and \
do not create any other file.
"""

REPLANNER_SYSTEM_PROMPT = """\
Your ONLY job is to correct flawed assumptions in the REMAINING tasks based on \
what was just learned — nothing else. You are given the original question, the \
current plan, and the findings from the task just completed (inline). You do not \
do research, and you do not write findings or REPORT.md.

If an UNCHECKED ("- [ ]") task rests on an assumption the findings contradicted \
or superseded, don't just patch the wording — reword it to pursue what the \
findings show actually matters for answering the original question. If the \
task's premise is now moot, redirect it to something genuinely useful rather \
than researching a dead premise. Keep reworded tasks clear and readable, not \
academic tangents.

Hard rules:
- The NUMBER of tasks must not change. Do NOT add, remove, merge, or reorder \
tasks, and do NOT touch "- [x]" lines — their positions are load-bearing.
- Reword existing "- [ ]" lines in place only, and keep them "- [ ] " \
(unchecked) — never mark tasks complete; completion is tracked automatically.
- If no task rests on a contradicted assumption, respond "No changes needed." \
and STOP — do not rewrite the file.
Otherwise save RESEARCH_PLAN.md with the workspace write tool, respond with one \
short sentence, and STOP. Do not call further tools or create any other file.
"""

RESEARCH_SYSTEM_PROMPT_TEMPLATE = """\
You are a research agent investigating a specific sub-question.

Original question: {original_question}
Your assigned task: {task_description}

Use web_search to find relevant sources. To read a page, call summarize_website \
with the URL and a focus describing what you need — it returns a concise summary, \
letting you cover many sources without overflowing context. Write your findings \
to {findings_file}. Include sources, key facts, and relevant details.

Stay strictly on your assigned task and the original question. Do not drift into \
adjacent topics the user did not ask about (for example, if the user did not \
mention pain, do not pursue pain-related questions). Do not edit RESEARCH_PLAN.md.

If you discover an open question that would materially advance answering the \
ORIGINAL question, add a "## Potential follow-up questions" section at the END \
of your findings file — one short question per line. Leave it out otherwise.

Be thorough but focused on your specific task.
"""

SYNTHESIS_SYSTEM_PROMPT = """\
You are a research synthesis agent. You are given research material inline \
below. Write the report that directly answers the user's original research \
question, and output the full report as your response.

Write for a normal person: clear, readable, and to the point. Ground every \
claim in the research and cite sources, but do NOT write a literature review \
or pad with academic jargon, background, or tangents the user did not ask \
about. Use plain language, and explain technical terms briefly only when they \
are unavoidable. Lead with the answer the user is looking for, then support it. \
If the findings show the question rests on a premise that doesn't hold, say so \
plainly and answer what's actually true instead of answering the question as \
originally framed.

End with a "## Suggested follow-up questions" section: list the few open \
questions that would most advance answering the original question, as a \
numbered list. The user may ask you to research specific ones next.
"""

SYNTHESIS_SUMMARIZE_PROMPT = """\
You are a research summarization agent. You are given one batch of research \
findings inline below. Write a focused summary that preserves all key facts, \
numbers, and source URLs, and output it as your response. This summary will \
later be merged with other batch summaries into a final report, so be complete \
but concise. Copy any "## Potential follow-up questions" section from the \
findings verbatim.
"""

NUDGE_PROMPT_TEMPLATE = """\
Stop researching. You forgot the required wrap-up step. Do it now:

Write your findings to {findings_file} (use the workspace write tool).

Do not search the web again. Do not edit RESEARCH_PLAN.md.
"""


class _InnerResearchAgent(ReActAgent):
    """ReAct inner agent whose transcript persists across `_loop` calls: a
    second `_loop(message)` appends `message` as a user turn and continues
    the same in-memory conversation instead of starting fresh."""

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
        self._messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message},
        ]
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


class _FilteredQueue:
    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    async def put(self, item):
        if item is STREAM_DONE or (
            isinstance(item, StreamEvent) and item.type == "done"
        ):
            return
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


DEFAULT_CONTEXT_WINDOW = 64000
SYNTHESIS_OUTPUT_RESERVE = 2048
SYNTHESIS_RESERVE_FRACTION = 0.30

# cl100k_base is an approximation for non-OpenAI models; callers budget
# conservatively (SYNTHESIS_RESERVE_FRACTION) to absorb the mismatch.
_ENCODER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _synthesis_budget(context_window: int) -> int:
    """Tokens available for findings material in a single synthesis/summary
    call, after reserving room for the prompt, the output, and a safety
    margin."""
    reserve = max(
        SYNTHESIS_OUTPUT_RESERVE, int(context_window * SYNTHESIS_RESERVE_FRACTION)
    )
    return max(1024, context_window - reserve)


def _parse_findings_files(plan: str) -> List[str]:
    """Findings-file paths for completed tasks, in plan order. Derived from the
    task index + description via the same naming convention as the
    research/reconcile loops (findings/{idx:02d}-{slug}.md) — never parsed from
    the plan text. Indexing mirrors _reconcile_plan: both [ ] and [x]
    increment idx."""
    paths = []
    idx = 0
    for line in plan.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            idx += 1
        elif stripped.startswith("- [x]"):
            idx += 1
            desc = stripped[5:].strip()
            paths.append(f"findings/{idx:02d}-{_slugify(desc)}.md")
    return paths


def _batch_findings(
    items: List[Tuple[str, str, int]], budget: int
) -> List[List[Tuple[str, str, int]]]:
    """Greedily pack (path, content, tokens) items into batches whose token
    totals stay within budget. An item larger than budget gets its own batch."""
    batches: List[List[Tuple[str, str, int]]] = []
    current: List[Tuple[str, str, int]] = []
    current_tokens = 0
    for item in items:
        toks = item[2]
        if current and current_tokens + toks > budget:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(item)
        current_tokens += toks
    if current:
        batches.append(current)
    return batches


def _format_material_block(items: List[Tuple[str, str, int]]) -> str:
    parts = [f"=== {path} ===\n{content}" for path, content, _ in items]
    return "\n\n".join(parts)


def _synthesis_user_prompt(
    original_question: str, block: str, from_summaries: bool = False
) -> str:
    source = "batch summaries" if from_summaries else "research findings"
    return (
        f"Original research question: {original_question}\n\n"
        f"Below are the {source}:\n\n{block}\n\n"
        f"Write REPORT.md now using the workspace write tool."
    )


def _summarize_user_prompt(original_question: str, block: str) -> str:
    return (
        f"Original research question: {original_question}\n\n"
        f"Below is your batch of research findings:\n\n{block}\n\n"
        f"Write the summary file now using the workspace write tool."
    )


class ResearchAgent(BaseAgent):
    """Multi-layered research agent. The outer loop is pure code — it reads the
    plan file and spawns inner ReAct agents for planning, researching, and
    synthesizing. RESEARCH_PLAN.md is the communication channel between loops."""

    max_outer_iterations: int = 15
    max_inner_iterations: int = 15
    context_window: Optional[int] = None

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
            plan = self._read_plan()
            if not plan:
                for attempt in range(3):
                    await self._run_planner(message, plan=None, report=None, queue=queue)
                    plan = self._read_plan()
                    if plan:
                        break
                    logger.warning(
                        "chat_id=%s plan not created after attempt %d, retrying",
                        self.chat_id,
                        attempt + 1,
                    )
                if not plan:
                    logger.error(
                        "chat_id=%s failed to create research plan after 3 attempts",
                        self.chat_id,
                    )
                    await self._emit(queue, STREAM_DONE)
                    return {}
            elif self._workspace_file_exists(REPORT_FILENAME):
                await self._run_planner(
                    message, plan=plan, report=self._read_report(), queue=queue
                )
                plan = self._read_plan() or plan

            original_question = _parse_title(plan) or message

            for _ in range(self.max_outer_iterations):
                self._reconcile_plan()
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

                await self._research_task(prompt, task_desc, findings_file, queue)

                self._reconcile_plan()
                plan = self._read_plan() or ""
                if _parse_pending_tasks(plan):
                    findings = self._read_workspace_file(findings_file)
                    if findings:
                        await self._run_replanner(
                            original_question, plan, findings, queue
                        )

            self._reconcile_plan()
            await self._synthesize(original_question, queue)

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

    def _read_report(self) -> str:
        return self._read_workspace_file(REPORT_FILENAME)

    def _read_workspace_file(self, path: str) -> str:
        if not self.workspace_id or not self._workspace_service:
            return ""
        try:
            return self._workspace_service.read_file(self.workspace_id, path)
        except Exception:
            return ""

    async def _run_replanner(
        self,
        original_question: str,
        plan: str,
        findings: str,
        queue: asyncio.Queue,
    ) -> None:
        """After a research task completes, fold its findings back into the
        REMAINING plan tasks so later tasks build on (rather than repeat or
        contradict) what was just learned. Findings are injected inline; the
        replanner only rewords/appends unchecked tasks and writes the plan
        once."""
        user_message = (
            f"Original question: {original_question}\n\n"
            f"Current RESEARCH_PLAN.md:\n{plan}\n\n"
            f"Findings from the task just completed:\n---\n{findings}\n---\n\n"
            f"Revise the remaining unchecked tasks in RESEARCH_PLAN.md now using "
            f"the workspace write tool."
        )
        logger.info(
            "chat_id=%s replanning: %d-char findings inline",
            self.chat_id,
            len(findings),
        )
        await self._spawn(
            REPLANNER_SYSTEM_PROMPT,
            user_message,
            queue,
            tool_servers=[WORKSPACE_SERVER_NAME],
        )

    async def _run_planner(
        self,
        message: str,
        plan: Optional[str],
        report: Optional[str],
        queue: asyncio.Queue,
    ) -> None:
        """Spawn the unified planner. State is fed inline — no plan/report means
        create; both present means append follow-up tasks. The planner only ever
        writes RESEARCH_PLAN.md; control flow (when to plan / research /
        synthesize) stays in _loop."""
        plan_block = plan if plan else "(none yet)"
        report_block = report if report else "(none yet)"
        user_message = (
            f"User's message: {message}\n\n"
            f"Existing RESEARCH_PLAN.md:\n{plan_block}\n\n"
            f"Existing REPORT.md:\n{report_block}\n\n"
            f"Use the workspace write tool to save RESEARCH_PLAN.md now."
        )
        if plan:
            logger.info(
                "chat_id=%s follow-up: extending plan (%d-char report inline)",
                self.chat_id,
                len(report_block),
            )
        await self._spawn(
            PLANNER_SYSTEM_PROMPT,
            user_message,
            queue,
            tool_servers=[WORKSPACE_SERVER_NAME],
        )

    def _reconcile_plan(self) -> None:
        """Check off tasks whose findings file already exists.

        The research agent sometimes writes findings but forgets to update the
        plan; without this, the outer loop would re-research the same task and
        synthesis would miss the findings. Findings-file existence is the source
        of truth.
        """
        if not self.workspace_id or not self._workspace_service:
            return
        plan = self._read_plan()
        if not plan:
            return
        try:
            files = set(self._workspace_service.list_files_flat(self.workspace_id))
        except Exception:
            return

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
            self._workspace_service.write_file(
                self.workspace_id, PLAN_FILENAME, "\n".join(new_lines)
            )

    async def _research_task(
        self,
        prompt: str,
        task_desc: str,
        findings_file: str,
        queue: asyncio.Queue,
    ) -> None:
        if self._workspace_file_exists(findings_file):
            return
        agent = await self._spawn(prompt, task_desc, queue, web=True)
        if self._workspace_file_exists(findings_file):
            return
        logger.warning(
            "chat_id=%s findings file %s not created, sending follow-up nudge",
            self.chat_id,
            findings_file,
        )
        nudge = NUDGE_PROMPT_TEMPLATE.format(findings_file=findings_file)
        filtered = _FilteredQueue(queue)
        await agent._loop(nudge, queue=filtered)
        if self._workspace_file_exists(findings_file):
            return
        logger.warning(
            "chat_id=%s findings file %s still missing after nudge, fresh retry",
            self.chat_id,
            findings_file,
        )
        await self._spawn(prompt, task_desc, queue, web=True)

    def _workspace_file_exists(self, path: str) -> bool:
        if not self.workspace_id or not self._workspace_service:
            return False
        try:
            files = self._workspace_service.list_files_flat(self.workspace_id)
            return path in files
        except Exception:
            return False

    async def _synthesize(
        self, original_question: str, queue: asyncio.Queue
    ) -> None:
        """Write REPORT.md from completed findings, bounding per-call context.

        Fast path: all findings fit the budget -> one synthesis agent writes
        REPORT.md from inline findings. Reduce path: findings exceed budget ->
        summarize batches first (synthesis/batch_NN.md), then synthesize the
        batch summaries into REPORT.md. Either way the LLM never reads files
        itself, so per-call context size is controlled by this outer code.
        """
        if not self.workspace_id or not self._workspace_service:
            return

        plan = self._read_plan() or ""
        paths = [
            p for p in _parse_findings_files(plan) if self._workspace_file_exists(p)
        ]
        if not paths:
            logger.warning(
                "chat_id=%s no findings files found, skipping synthesis",
                self.chat_id,
            )
            return

        items: List[Tuple[str, str, int]] = []
        for path in paths:
            try:
                content = self._workspace_service.read_file(self.workspace_id, path)
            except Exception as e:
                logger.warning(
                    "chat_id=%s failed to read %s: %s", self.chat_id, path, e
                )
                continue
            items.append((path, content, _count_tokens(content)))

        if not items:
            logger.warning(
                "chat_id=%s all findings files unreadable, skipping synthesis",
                self.chat_id,
            )
            return

        total_tokens = sum(t for _, _, t in items)
        context_window = self.context_window or DEFAULT_CONTEXT_WINDOW
        budget = _synthesis_budget(context_window)

        if total_tokens <= budget:
            logger.info(
                "chat_id=%s synthesis fast-path: %d findings, %d tokens (budget %d)",
                self.chat_id,
                len(items),
                total_tokens,
                budget,
            )
            await self._run_synthesis_agent(
                SYNTHESIS_SYSTEM_PROMPT,
                _synthesis_user_prompt(original_question, _format_material_block(items)),
                REPORT_FILENAME,
                queue,
            )
            return

        logger.info(
            "chat_id=%s synthesis reduce-path: %d findings, %d tokens, budget %d",
            self.chat_id,
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
                    original_question, _format_material_block(batch)
                ),
                batch_file,
                queue,
            )

        try:
            all_files = self._workspace_service.list_files_flat(self.workspace_id)
        except Exception:
            all_files = []
        batch_paths = sorted(
            p
            for p in all_files
            if p.startswith("synthesis/batch_") and p.endswith(".md")
        )
        summary_items: List[Tuple[str, str, int]] = []
        for path in batch_paths:
            try:
                content = self._workspace_service.read_file(self.workspace_id, path)
            except Exception as e:
                logger.warning(
                    "chat_id=%s failed to read %s: %s", self.chat_id, path, e
                )
                continue
            summary_items.append((path, content, _count_tokens(content)))

        if not summary_items:
            logger.warning(
                "chat_id=%s no batch summaries produced, skipping report",
                self.chat_id,
            )
            return

        summary_tokens = sum(t for _, _, t in summary_items)
        if summary_tokens > budget:
            logger.warning(
                "chat_id=%s batch summaries (%d tokens) exceed budget (%d); "
                "writing best-effort report",
                self.chat_id,
                summary_tokens,
                budget,
            )

        block = _format_material_block(summary_items)
        await self._run_synthesis_agent(
            SYNTHESIS_SYSTEM_PROMPT,
            _synthesis_user_prompt(original_question, block, from_summaries=True),
            REPORT_FILENAME,
            queue,
        )

    async def _run_synthesis_agent(
        self,
        system_prompt: str,
        user_message: str,
        output_path: str,
        queue: asyncio.Queue,
    ) -> None:
        """Run a no-tool synthesis/summary agent and persist its text response.

        Synthesis output is fundamentally text, and the model produces it most
        reliably as a response (not via a write-tool call). So the agent gets no
        tools, emits the report/summary as its response, and this outer code
        writes the file. The response also streams live to the user."""
        agent = await self._spawn(
            system_prompt, user_message, queue, tool_servers=[]
        )
        content = agent.last_response
        if not content:
            logger.warning(
                "chat_id=%s synthesis agent produced no response; %s not written",
                self.chat_id,
                output_path,
            )
            return
        self._workspace_service.write_file(
            self.workspace_id, output_path, content
        )
        logger.info(
            "chat_id=%s wrote %s (%d chars)",
            self.chat_id,
            output_path,
            len(content),
        )

    async def _spawn(
        self,
        system_prompt: str,
        user_message: str,
        queue: asyncio.Queue,
        *,
        web: bool = False,
        tool_servers: Optional[List[str]] = None,
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
        )
        filtered = _FilteredQueue(queue)
        await agent._loop(user_message, queue=filtered)
        return agent


class ResearchAgentPlugin(ResearchAgent, AgentPluginBase):
    pass
