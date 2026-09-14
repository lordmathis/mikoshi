from dataclasses import dataclass


@dataclass(frozen=True)
class StreamEvent:
    type: str
    data: dict


STREAM_DONE = StreamEvent(type="done", data={})


def error_event(message: str) -> StreamEvent:
    """User-visible error event; emitters follow it with STREAM_DONE."""
    return StreamEvent(type="error", data={"message": message})
