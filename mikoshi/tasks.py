"""Fire-and-forget background tasks.

`asyncio.create_task` keeps only a weak reference to the created task, so
an unreferenced task can be garbage-collected mid-execution. These helpers
hold a strong reference until the task completes.
"""

import asyncio
import logging
from typing import Coroutine

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def create_background_task(coro: Coroutine, *, name: str | None = None) -> asyncio.Task:
    """Start a fire-and-forget task that stays referenced until it finishes."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)

    def _done(t: asyncio.Task) -> None:
        _tasks.discard(t)
        if not t.cancelled() and t.exception() is not None:
            logger.error(
                "Background task %s failed",
                t.get_name(),
                exc_info=t.exception(),
            )

    task.add_done_callback(_done)
    return task
