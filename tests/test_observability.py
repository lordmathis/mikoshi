"""Tests for mikoshi.observability.

Covers the meaningful code paths of the tracing layer:
- the disabled-guard in ``init_observability`` (no provider when unconfigured)
- the exception path of ``@observe`` (re-raise + ERROR status)
- the success path of ``@observe`` (OpenInference kind + input/output capture)
- ``start_tool_span`` / ``start_embedding_span`` / ``start_retriever_span``
  produce correctly-kinded spans with the OpenInference attributes Phoenix needs
"""

import json

import pytest
from openinference.semconv.trace import SpanAttributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace.status import StatusCode

import mikoshi.observability as obs
from mikoshi.observability import (
    init_observability,
    observe,
    start_embedding_span,
    start_retriever_span,
    start_tool_span,
)


@pytest.fixture
def span_exporter():
    """Wire a fresh in-memory exporter into the module-level ``_tracer``.

    ``@observe`` reads the module global ``_tracer`` at call time, so
    monkeypatching it gives isolated, capturable spans without touching
    the global OTel provider.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    original_tracer = obs._tracer
    obs._tracer = provider.get_tracer("test")
    try:
        yield exporter
    finally:
        obs._tracer = original_tracer
        provider.shutdown()


def test_init_observability_with_none_config_does_not_register(monkeypatch):
    """Disabled tracing must not register a provider."""
    calls = []
    monkeypatch.setattr(
        "mikoshi.observability.register", lambda **kw: calls.append(kw)
    )
    init_observability(None)
    assert calls == []


@pytest.mark.asyncio
async def test_observe_propagates_exceptions_and_marks_error(span_exporter):
    """The decorator must re-raise and set the span status to ERROR."""

    @observe(as_type="tool", name="boom_tool")
    async def boom_tool():
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        await boom_tool()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert any(ev.name == "exception" for ev in spans[0].events)


@pytest.mark.asyncio
async def test_observe_captures_kind_input_output_on_success(span_exporter):
    """A successful call records the OpenInference span kind and I/O."""

    @observe(as_type="tool", name="add_tool")
    async def add_tool(a, b):
        return {"sum": a + b}

    result = await add_tool(2, 3)
    assert result == {"sum": 5}

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == "TOOL"
    assert SpanAttributes.INPUT_VALUE in attrs
    assert SpanAttributes.OUTPUT_VALUE in attrs


def test_start_tool_span_records_kind_name_and_io(span_exporter):
    """A tool span carries the TOOL kind, tool.name, and caller-set I/O."""
    with start_tool_span("search_web") as span:
        span.set_attribute(SpanAttributes.INPUT_VALUE, '{"q": "cats"}')
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, "results")

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == "TOOL"
    assert attrs[SpanAttributes.TOOL_NAME] == "search_web"
    assert attrs[SpanAttributes.INPUT_VALUE] == '{"q": "cats"}'
    assert attrs[SpanAttributes.OUTPUT_VALUE] == "results"


def test_start_embedding_span_records_kind_model_and_text(span_exporter):
    """An embedding span carries the EMBEDDING kind, model name, and input text."""
    with start_embedding_span("text-embedding-3-small", "hello world"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == "EMBEDDING"
    assert attrs[SpanAttributes.EMBEDDING_MODEL_NAME] == "text-embedding-3-small"
    assert attrs[SpanAttributes.INPUT_VALUE] == "hello world"


def test_start_retriever_span_records_kind_query_and_documents(span_exporter):
    """A retriever span carries the RETRIEVER kind, query, and result docs."""
    docs = [
        {"document.content": "cats are great", "document.score": 0.9},
        {"document.content": "dogs too", "document.score": 0.4},
    ]
    with start_retriever_span("recall_memory", "pets") as span:
        span.set_attribute(
            SpanAttributes.RETRIEVAL_DOCUMENTS, json.dumps(docs)
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == "RETRIEVER"
    assert attrs[SpanAttributes.INPUT_VALUE] == "pets"
    assert json.loads(attrs[SpanAttributes.RETRIEVAL_DOCUMENTS]) == docs
