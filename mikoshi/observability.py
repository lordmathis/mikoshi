"""OpenTelemetry-based observability for agent tracing.

Exports traces via OTLP to any compatible backend (Phoenix, Jaeger,
Tempo, etc.). The provider is wired up through ``arize-phoenix-otel``'s
``register()`` helper, which reads standard ``OTEL_*`` env vars. When
tracing is disabled, all decorators and helpers are harmless no-ops —
OTel returns non-recording spans when no TracerProvider is configured.
"""

import contextlib
import functools
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from openinference.semconv.trace import (
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from phoenix.otel import register

from mikoshi.config import TracingConfig

logger = logging.getLogger(__name__)

__all__ = [
    "flush_observability",
    "init_observability",
    "observe",
    "start_embedding_span",
    "start_retriever_span",
    "start_tool_span",
]

_tracer = trace.get_tracer("mikoshi")

# OpenInference span-kind values (recognized by Phoenix)
_KIND_CHAIN = OpenInferenceSpanKindValues.CHAIN.value
_KIND_TOOL = OpenInferenceSpanKindValues.TOOL.value
_KIND_EMBEDDING = OpenInferenceSpanKindValues.EMBEDDING.value
_KIND_RETRIEVER = OpenInferenceSpanKindValues.RETRIEVER.value


def _safe_json(obj: Any) -> Optional[str]:
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return None


def init_observability(config: Optional[TracingConfig]) -> None:
    """Initialize the OTel tracer provider via arize-phoenix-otel.

    Standard ``OTEL_*`` environment variables are respected by ``register()``.
    No config or no endpoint → tracing stays as no-op spans.
    """
    if not config or not config.endpoint:
        logger.info("Tracing disabled")
        return

    resource_attrs: Dict[str, Any] = {}
    if config.service_version:
        resource_attrs["service.version"] = config.service_version
    if config.deployment_environment:
        resource_attrs["deployment.environment"] = config.deployment_environment

    register_kwargs: Dict[str, Any] = {
        "project_name": config.project_name,
        "endpoint": config.endpoint,
        "batch": config.batch,
        "auto_instrument": False,
        "verbose": False,
    }
    if config.headers:
        register_kwargs["headers"] = dict(config.headers)
    if resource_attrs:
        register_kwargs["resource"] = Resource.create(resource_attrs)

    register(**register_kwargs)

    # Auto-instrument the LLM SDKs so every chat completion becomes a
    # structured LLM span (messages, invocation params, token usage).
    # Registered after the provider is set as global; they patch the
    # underlying SDKs, so OpenAIClient/AnthropicClient are traced for free.
    _instrument_llm_sdks()

    logger.info(
        "Tracing enabled (endpoint=%s, project=%s)",
        config.endpoint,
        config.project_name,
    )


def _instrument_llm_sdks() -> None:
    """Register OpenInference auto-instrumentors for the LLM SDKs in use."""
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    OpenAIInstrumentor().instrument()
    AnthropicInstrumentor().instrument()


def flush_observability() -> None:
    """Flush pending traces before shutdown."""
    try:
        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
    except Exception:
        logger.warning("Failed to flush tracing data", exc_info=True)


def observe(func=None, *, name=None, as_type=None):
    """Decorator that creates an OTel span around an async function.

    as_type "tool" → TOOL span, else CHAIN. Captures input (stripping
    self) and output automatically.
    """

    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__name__
        kind = _KIND_TOOL if as_type == "tool" else _KIND_CHAIN
        params = inspect.signature(fn).parameters
        is_method = "self" in params or "cls" in params

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            with _tracer.start_as_current_span(span_name) as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, kind)

                logged_args = args[1:] if is_method else args
                input_json = _safe_json({"args": logged_args, "kwargs": kwargs})
                if input_json:
                    span.set_attribute(SpanAttributes.INPUT_VALUE, input_json)
                    span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")

                try:
                    result = await fn(*args, **kwargs)
                    if result is not None:
                        output_json = _safe_json(result)
                        if output_json:
                            span.set_attribute(SpanAttributes.OUTPUT_VALUE, output_json)
                            span.set_attribute(
                                SpanAttributes.OUTPUT_MIME_TYPE, "application/json"
                            )
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


@contextlib.contextmanager
def start_tool_span(name: str):
    """Open a TOOL-kind span for an individual tool call.

    Sets the OpenInference span kind and ``tool.name``. The caller sets
    ``INPUT_VALUE``/``OUTPUT_VALUE`` (and any events) on the yielded span.
    """
    with _tracer.start_as_current_span(name) as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, _KIND_TOOL)
        span.set_attribute(SpanAttributes.TOOL_NAME, name)
        yield span


@contextlib.contextmanager
def start_embedding_span(model: str, text: str):
    """Open an EMBEDDING-kind span around an embedding call.

    Sets the OpenInference span kind, ``embedding.model_name`` and the
    input text. The raw vector is intentionally not recorded to avoid
    span bloat (see spec gotcha). Exceptions propagate and are
    auto-recorded with ERROR status by the OTel SDK.
    """
    with _tracer.start_as_current_span("embedding") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, _KIND_EMBEDDING)
        span.set_attribute(SpanAttributes.EMBEDDING_MODEL_NAME, model)
        span.set_attribute(SpanAttributes.INPUT_VALUE, text)
        yield span


@contextlib.contextmanager
def start_retriever_span(name: str, query: str):
    """Open a RETRIEVER-kind span around a vector search.

    Sets the OpenInference span kind and the query as input. The caller
    sets ``RETRIEVAL_DOCUMENTS`` (JSON list of ``document.content`` /
    ``document.score`` objects) on the yielded span after searching.
    """
    with _tracer.start_as_current_span(name) as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, _KIND_RETRIEVER)
        span.set_attribute(SpanAttributes.INPUT_VALUE, query)
        yield span
