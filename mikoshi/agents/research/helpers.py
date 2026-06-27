import re
from typing import List, Tuple

import tiktoken

from mikoshi.agents.streaming import STREAM_DONE, StreamEvent

DEFAULT_CONTEXT_WINDOW = 64000
SYNTHESIS_OUTPUT_RESERVE = 2048
SYNTHESIS_RESERVE_FRACTION = 0.30

# cl100k_base is an approximation for non-OpenAI models; callers budget
# conservatively (SYNTHESIS_RESERVE_FRACTION) to absorb the mismatch.
_ENCODER = tiktoken.get_encoding("cl100k_base")


class _FilteredQueue:
    def __init__(self, queue):
        self._queue = queue

    async def put(self, item):
        if item is STREAM_DONE or (
            isinstance(item, StreamEvent) and item.type == "done"
        ):
            return
        await self._queue.put(item)


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
