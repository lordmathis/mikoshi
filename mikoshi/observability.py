"""Langfuse observability integration.
"""

import logging
from typing import Optional

from langfuse import (
    Langfuse,
    LangfuseOtelSpanAttributes,
    get_client,
    observe,
)
from opentelemetry.trace import get_current_span

from mikoshi.config import LangfuseConfig

logger = logging.getLogger(__name__)

__all__ = [
    "flush_observability",
    "init_observability",
    "observe",
    "record_generation",
    "trace_session",
]


def init_observability(config: Optional[LangfuseConfig]) -> None:
    """Initialize the Langfuse singleton from config.

    API keys are read from config (which supports ${ENV_VAR} expansion).
    Call once at startup before any @observe-decorated function runs.
    """
    if not config or not config.enabled:
        logger.info("Langfuse tracing disabled")
        return

    kwargs: dict = {}
    if config.public_key:
        kwargs["public_key"] = config.public_key
    if config.secret_key:
        kwargs["secret_key"] = config.secret_key
    if config.host:
        kwargs["base_url"] = config.host
    if config.environment:
        kwargs["environment"] = config.environment
    if config.sample_rate is not None:
        kwargs["sample_rate"] = config.sample_rate

    client = Langfuse(**kwargs)
    if client.tracing_enabled:
        logger.info(
            "Langfuse tracing enabled (host=%s)", config.host or "default"
        )
    else:
        logger.warning(
            "Langfuse enabled in config but client is disabled — "
            "check public_key / secret_key"
        )


def flush_observability() -> None:
    """Flush pending traces before shutdown."""
    try:
        get_client().flush()
    except Exception:
        pass


def trace_session(session_id: str, *, name: Optional[str] = None) -> None:
    """Set trace-level attributes on the current trace.

    Call inside the root @observe-decorated function to group traces
    by session (chat_id) in the Langfuse UI.
    """
    span = get_current_span()
    if span is None or not span.is_recording():
        return
    span.set_attribute(LangfuseOtelSpanAttributes.TRACE_SESSION_ID, session_id)
    if name:
        span.set_attribute(LangfuseOtelSpanAttributes.TRACE_NAME, name)


def record_generation(model: str, usage: Optional[dict] = None) -> None:
    """Enrich the current @observe(as_type="generation") span with model
    and token usage. The response dict from both OpenAIClient and
    AnthropicClient contains a 'usage' key in OpenAI format."""
    kwargs: dict = {"model": model}
    if usage:
        kwargs["usage_details"] = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
        }
    get_client().update_current_generation(**kwargs)
