from dataclasses import dataclass


@dataclass(frozen=True)
class StreamEvent:
    type: str
    data: dict


STREAM_DONE = StreamEvent(type="done", data={})


def error_event(message: str) -> StreamEvent:
    """User-visible error event; emitters follow it with STREAM_DONE."""
    return StreamEvent(type="error", data={"message": message})


class FilteredQueue:
    """Queue wrapper that swallows STREAM_DONE from inner agents so only
    the outer agent can end the stream."""

    def __init__(self, queue):
        self._queue = queue

    async def put(self, item):
        if item is STREAM_DONE or (
            isinstance(item, StreamEvent) and item.type == "done"
        ):
            return
        await self._queue.put(item)
