"""OpenTelemetry-based observability for agent tracing.

Exports traces via OTLP to any compatible backend (Phoenix, Jaeger,
Tempo, etc.). When tracing is disabled, all decorators and helpers
are harmless no-ops — OTel returns non-recording spans when no
TracerProvider is configured.
"""

import functools
import inspect
import json
import logging
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import get_current_span

from mikoshi.config import TracingConfig

logger = logging.getLogger(__name__)

__all__ = [
    "flush_observability",
    "init_observability",
    "observe",
    "record_generation",
    "trace_session",
]

_tracer = trace.get_tracer("mikoshi")

# OpenInference attribute keys (recognized by Phoenix)
_SPAN_KIND = "openinference.span.kind"
_KIND_CHAIN = "CHAIN"
_KIND_TOOL = "TOOL"
_KIND_LLM = "LLM"

_INPUT_VALUE = "input.value"
_INPUT_MIME_TYPE = "input.mime_type"
_OUTPUT_VALUE = "output.value"
_OUTPUT_MIME_TYPE = "output.mime_type"

_LLM_MODEL_NAME = "llm.model_name"
_LLM_TOKEN_COUNT_PROMPT = "llm.token_count.prompt"
_LLM_TOKEN_COUNT_COMPLETION = "llm.token_count.completion"

_SESSION_ID = "session.id"


def _safe_json(obj: Any) -> Optional[str]:
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return None


def init_observability(config: Optional[TracingConfig]) -> None:
    """Initialize the OTel tracer provider with an OTLP exporter.

    No config or no endpoint → tracing stays as no-op spans.
    """
    if not config or not config.endpoint:
        logger.info("Tracing disabled")
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": "mikoshi"})
    )
    exporter = OTLPSpanExporter(endpoint=config.endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    logger.info("Tracing enabled (endpoint=%s)", config.endpoint)


def flush_observability() -> None:
    """Flush pending traces before shutdown."""
    try:
        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
    except Exception:
        pass


def observe(func=None, *, name=None, as_type=None):
    """Decorator that creates an OTel span around an async function.

    as_type "generation" → LLM span, "tool" → TOOL span, else CHAIN.
    Captures input (stripping self) and output automatically.
    """

    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__name__
        kind = (
            _KIND_LLM
            if as_type == "generation"
            else _KIND_TOOL if as_type == "tool" else _KIND_CHAIN
        )
        params = inspect.signature(fn).parameters
        is_method = "self" in params or "cls" in params

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            with _tracer.start_as_current_span(span_name) as span:
                span.set_attribute(_SPAN_KIND, kind)

                logged_args = args[1:] if is_method else args
                input_json = _safe_json({"args": logged_args, "kwargs": kwargs})
                if input_json:
                    span.set_attribute(_INPUT_VALUE, input_json)
                    span.set_attribute(_INPUT_MIME_TYPE, "application/json")

                try:
                    result = await fn(*args, **kwargs)
                    if result is not None:
                        output_json = _safe_json(result)
                        if output_json:
                            span.set_attribute(_OUTPUT_VALUE, output_json)
                            span.set_attribute(_OUTPUT_MIME_TYPE, "application/json")
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    raise

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def trace_session(session_id: str, *, name: Optional[str] = None) -> None:
    """Tag the current trace with a session ID for grouping in the UI."""
    span = get_current_span()
    if not span.is_recording():
        return
    span.set_attribute(_SESSION_ID, session_id)


def record_generation(model: str, usage: Optional[dict] = None) -> None:
    """Enrich the current LLM span with model name and token usage."""
    span = get_current_span()
    if not span.is_recording():
        return
    span.set_attribute(_LLM_MODEL_NAME, model)
    if usage:
        span.set_attribute(
            _LLM_TOKEN_COUNT_PROMPT, usage.get("prompt_tokens", 0)
        )
        span.set_attribute(
            _LLM_TOKEN_COUNT_COMPLETION, usage.get("completion_tokens", 0)
        )
