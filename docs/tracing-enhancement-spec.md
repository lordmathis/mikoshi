# Mikoshi Tracing Enhancement Spec v1.0

## Overview

Expand mikoshi's OpenTelemetry tracing to fully utilize Arize Phoenix's LLM
observability features. The current layer (`mikoshi/observability.py`) is a
minimal hand-rolled implementation: one `@observe` decorator, six spans, opaque
JSON `input.value`/`output.value` blobs, and session/model/token attributes set
directly on the active span. This spec upgrades it to structured OpenInference
spans via SDK auto-instrumentation, per-tool granularity, context-propagated
session/user/metadata, retrieval visibility, and HTTP-layer distributed tracing.

## Tech Stack

- Python, dependency management via `uv`
- OpenTelemetry SDK 1.43+ (already present)
- Arize Phoenix — docker backend (`docker-compose.dev.yaml`), UI on 6006,
  OTLP gRPC on 4317, OTLP HTTP on 4318
- `arize-phoenix-otel` — `register()` helper + `using_session`/`using_user`/
  `using_metadata`/`using_tags`/`using_attributes` context managers
- `openinference-semantic-conventions` — typed attribute constants
- `openinference-instrumentation-openai`, `openinference-instrumentation-anthropic`
  — SDK auto-instrumentors
- `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`
- Underlying SDKs already in use: `openai` (via `OpenAIClient`),
  `anthropic` (via `AnthropicClient`), Qdrant, FastAPI, httpx

## Core Principles

1. **Auto-instrumentation over hand-rolled spans** — let OpenInference
   instrumentors produce structured LLM/tool spans; reserve manual spans for
   CHAIN-level orchestration (agent loop, research stages).
2. **Context propagation, not per-span writes** — session/user/metadata flow via
   the OTel Context so every child span (auto-instrumented or manual) inherits
   them. This is what powers Phoenix Sessions and cross-span filtering.
3. **No-op safety preserved** — when tracing is disabled, all decorators and
   helpers remain harmless (non-recording spans). Business logic must not
   branch on whether a span is recording.
4. **Config-driven, env-aware** — `TracingConfig` expands; standard `OTEL_*`
   env vars are respected via `register()`.
5. **Incremental** — each phase is independently shippable and leaves the system
   in a working state.

## Current State (reference)

| Concern | Location | State |
|---|---|---|
| Provider/exporter wiring | `mikoshi/observability.py:61-77` | manual `TracerProvider` + HTTP OTLP exporter |
| Config schema | `mikoshi/config.py:120-122` | `TracingConfig.endpoint` only |
| Init | `mikoshi/main.py:46` | `init_observability(app_config.tracing)` |
| Shutdown flush | `mikoshi/lifespan.py:155-157` | `flush_observability()` (swallows errors) |
| Span decorator | `mikoshi/observability.py:90-137` | `@observe(name, as_type)` |
| LLM span | `mikoshi/agents/base.py:540` | `@observe(as_type="generation")` |
| Tool span | `mikoshi/agents/base.py:82` | `@observe(as_type="tool")` batches all calls |
| Session tag | `mikoshi/observability.py:140` | writes to current span only |
| Embeddings | `mikoshi/providers/clients.py:42`, `mikoshi/tools/builtin/memory.py:108` | untraced |
| Phoenix compose | `docker-compose.dev.yaml:24-28` | exposes 4317 (gRPC) only |

---

## Phase 1: Tracing Foundation

### Backend

**Dependencies:** add via `uv add`:
- `arize-phoenix-otel`
- `openinference-semantic-conventions`

**Replace manual provider wiring** in `observability.py`. Swap the hand-built
`TracerProvider`/`Resource`/`OTLPSpanExporter`/`BatchSpanProcessor` block
(`observability.py:61-77`) for `phoenix.otel.register(...)`. It returns a
configured `TracerProvider`, reads `OTEL_*` env vars, and supports:

```python
from phoenix.otel import register
provider = register(
    project_name=cfg.project_name,      # default "mikoshi"
    endpoint=cfg.endpoint,              # OTLP HTTP endpoint
    batch=cfg.batch,                    # True in prod, False in dev
    auto_instrument=True,               # leave False; we add instrumentors explicitly
)
```

Keep the no-op guard: no config / no endpoint → do not call `register()`, leave
the default non-recording provider.

**Replace hand-typed attribute constants** (`observability.py:36-51`) with
imports from `openinference.semconv.resource` / `...trace` /
`...trace.SpanAttributes`. Map existing constants:
- `openinference.span.kind` → `SpanAttributes.OPENINFERENCE_SPAN_KIND`
- `input.value` / `input.mime_type` → `SpanAttributes.INPUT_VALUE` / `INPUT_MIME_TYPE`
- `output.value` / `output.mime_type` → `SpanAttributes.OUTPUT_VALUE` / `OUTPUT_MIME_TYPE`
- `llm.model_name` → `SpanAttributes.LLM_MODEL_NAME`
- `llm.token_count.prompt` / `.completion` → `SpanAttributes.LLM_TOKEN_COUNT_PROMPT` / `_COMPLETION`
- `session.id` → `SpanAttributes.SESSION_ID`

**Expand `TracingConfig`** (`config.py:120-122`):

```python
class TracingConfig(BaseModel):
    endpoint: Optional[str] = None
    project_name: str = "mikoshi"
    batch: bool = True
    service_version: Optional[str] = None
    deployment_environment: Optional[str] = None
    headers: Dict[str, str] = {}          # for auth / Phoenix cloud
```

`service_version` and `deployment_environment` are attached to the resource
attributes so Phoenix can filter by version/env.

**Fix `flush_observability`** (`observability.py:80-87`): stop silently
swallowing all exceptions. Log the failure at WARNING instead of bare `pass`.

**Remove dead code:** the unused `name` parameter on `trace_session`
(`observability.py:140`). (Note: `trace_session` itself is retired in Phase 3 in
favor of context propagation — see that phase.)

### Infrastructure

**Fix Phoenix port exposure** (`docker-compose.dev.yaml:24-28`): the HTTP OTLP
exporter (default for `register()`) needs port **4318**, but only **4317**
(gRPC) is exposed. Add `"4318:4318"`. Alternative: keep gRPC only and use the
gRPC exporter — but matching Phoenix's HTTP default is simpler.

### Documentation

- Add a `config.example.yaml` with a commented `tracing:` block showing all new
  fields.
- Add a "Tracing" section to `README.md`: how to enable, the Phoenix endpoint,
  port mapping, and what `project_name` / `batch` do.

### Deliverable

Tracing still produces the same six spans, but the provider is set up via
`arize-phoenix-otel`, attribute keys are drift-proof, config is richer, the
port bug is fixed, and tracing is documented. No behaviour change for end users.

---

## Phase 2: LLM Auto-Instrumentation

### Backend

**Dependencies:** add via `uv add`:
- `openinference-instrumentation-openai`
- `openinference-instrumentation-anthropic`

**Register instrumentors in `init_observability`** (after `register()`):

```python
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.instrumentation.anthropic import AnthropicInstrumentor
OpenAIInstrumentor().instrument()
AnthropicInstrumentor().instrument()
```

These patch the underlying SDKs, so `OpenAIClient`/`AnthropicClient`
(`providers/clients.py`) get traced automatically — no edits to the client
classes. Each LLM call becomes a structured LLM span with `llm.input_messages`,
`llm.output_messages`, `llm.invocation_parameters` (temperature, max_tokens),
message roles/content, tool-call arrays, and token usage.

**Retire the manual LLM span.** Remove `@observe(as_type="generation", ...)`
from `BaseAgent._llm` (`base.py:540`) and the `record_generation(...)`
call at `base.py:556`. Auto-instrumentation already captures model name and
token counts in the correct attributes. Keep `_llm` as a plain async method
(the retry loop logic stays).

**Keep the `@observe` decorator** — it is still used for CHAIN spans
(`agent_turn`, `research_turn`, `research_stage`, `synthesis`) and TOOL spans.
Only the `as_type="generation"` path becomes unused; leave the branch in place
(or remove it — implementer's call) since it harms nothing.

**Span events for retries:** inside the `_llm` retry loop (`base.py:547-569`),
emit a span event on each retry so the timeline shows the failure + backoff:

```python
from opentelemetry.trace import get_current_span
get_current_span().add_event(
    "llm.retry",
    attributes={"retry.attempt": attempt + 1, "retry.delay_s": delay,
                "error.type": "APIConnectionError"},
)
```

### Gotchas

- **Double-tracing risk:** if `@observe(as_type="generation")` is left on `_llm`
  alongside auto-instrumentation, you get a nested manual LLM span inside the
  auto-instrumented one. The manual one must be removed (above).
- **Import order:** instrumentors must be registered after the SDK is imported
  but before the first call. Registering in `init_observability` (run at startup,
  `main.py:46`) satisfies this as long as providers are constructed after init.
- **Anthropic message format:** `AnthropicClient` converts OpenAI-format messages
  to Anthropic format internally (`clients.py:127`, `_convert_messages`). The
  instrumentor captures the **native Anthropic** call, so Phoenix shows Anthropic
  messages — this is correct/desired, not the OpenAI-normalized view.
- `record_generation` is also the only consumer of the `_KIND_LLM` /
  `_LLM_MODEL_NAME` constants on the manual path; confirm nothing else calls it
  before removing.

### Deliverable

Every LLM call (base agent, research agent, title generation via the inherited
client) appears in Phoenix as a richly-structured LLM span with messages,
invocation params, and token usage. Retry attempts are visible as timeline
events.

---

## Phase 3: Tool & Session Semantics

### Backend

**Per-tool spans.** The current `_execute_tool_calls`
(`base.py:82`) wraps the whole batch in one TOOL span. Restructure so each tool
call produces its own TOOL span with OpenInference tool attributes. The
`@observe(as_type="tool")` on the batch method should be removed; instead, open
a child span per iteration:

```python
for tc_idx, tool_call in enumerate(tool_calls_raw):
    tool_name = tool_call["function"]["name"]
    tool_args = parse(tool_call["function"]["arguments"])
    with _tracer.start_as_current_span(tool_name) as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
        span.set_attribute(SpanAttributes.TOOL_NAME, tool_name)
        span.set_attribute(SpanAttributes.TOOL_INPUT, json.dumps(tool_args))
        # ... execute ...
        span.set_attribute(SpanAttributes.TOOL_OUTPUT, result_str)
```

This requires the `_tracer` to be exposed (it is currently module-private in
`observability.py:34` — add it to `__all__` or expose a helper like
`start_tool_span(name)`).

**Context propagation for sessions/users/metadata.** Replace the
`trace_session(self.chat_id)` call at `base.py:235` (and the analogous call in
`research/agent.py:105`) with the context-manager form so session/user/metadata
propagate to **all** child spans (the auto-instrumented LLM spans and the new
per-tool spans), not just the top `agent_turn` span:

```python
from phoenix.otel import using_attributes

@observe(name="agent_turn")
async def _loop(self, message, queue):
    with using_attributes(
        session_id=self.chat_id,
        user_id=self.workspace_id,          # or whichever user identifier exists
        metadata={"agent": type(self).__name__, "model": self.model_id},
    ):
        # ...existing loop body...
```

Add a `using_tags(["research"])` / `["base"]` tag so the two agent types are
filterable in Phoenix. After this change, `trace_session()` in
`observability.py:140` is no longer called anywhere — remove it.

**Span events for approvals:** the tool-execution flow has an approval-request
callback (`base.py:124` onwards, `_on_approval_requested`). Emit events on the
relevant tool span: `tool.approval.requested`, `tool.approval.granted`,
`tool.approval.denied` — with the tool name and approval message id as
attributes. This makes human-in-the-loop latency visible in the timeline.

### Gotchas

- `using_attributes` sets values on the OTel **Context**, which only propagates
  to spans opened within the `with` block. Ensure no part of the loop escapes
  the context (e.g. background tasks via `asyncio.create_task`, like
  `_generate_title` at `base.py:571`, do **not** inherit the context unless
  explicitly passed). Title generation tracing is addressed in Phase 5.
- If a user identifier is unavailable (some flows may not have workspace/user
  context), omit `user_id` rather than passing `None` — the context managers
  require non-empty strings.
- `TOOL_INPUT`/`TOOL_OUTPUT` should be strings; JSON-encode structured args.

### Deliverable

Each tool call is an individual TOOL span with `tool.name`/`tool.input`/
`tool.output`, visible and filterable in Phoenix. Session/user/metadata/tags
propagate across the whole turn, so Phoenix's Sessions view groups multi-turn
conversations and every span is filterable by agent type and model.

---

## Phase 4: Retrieval Observability

### Backend

**Embedding spans.** `LLMClient.create_embedding`
(`providers/clients.py:42`, implemented at `:103` for OpenAI) is untraced. Wrap
the embedding call in an EMBEDDING span. Two options:

- **Option A (preferred):** instrument at the `create_embedding` call site in
  `OpenAIClient.create_embedding` (`clients.py:103`) — but note the OpenAI
  instrumentor from Phase 2 instruments `chat.completions`, **not**
  `embeddings`. So embeddings need a manual span:

```python
with _tracer.start_as_current_span("embedding") as span:
    span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "EMBEDDING")
    span.set_attribute(SpanAttributes.EMBEDDING_MODEL_NAME, model)
    span.set_attribute(SpanAttributes.EMBEDDING_TEXT, input)
    response = await self.client.embeddings.create(model=model, input=input)
    span.set_attribute(SpanAttributes.EMBEDDING_EMBEDDING_VECTORS,
                       response.data[0].embedding)  # mind size — see gotcha
    return response.data[0].embedding
```

- Apply the same to `AnthropicClient` if it ever gains embedding support (it
  currently returns `None`).

**Retriever spans for Qdrant.** The memory tool (`tools/builtin/memory.py`)
embeds a query (`_embed` at `memory.py:95`) then searches Qdrant. Wrap the
Qdrant search call in a RETRIEVER span. Locate the search call (in the
`recall`/search method of `MemoryTools`) and add:

```python
with _tracer.start_as_current_span("recall_memory") as span:
    span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "RETRIEVER")
    span.set_attribute(SpanAttributes.RETRIEVAL_QUERIES, json.dumps([query]))
    # ... qdrant search ...
    span.set_attribute(SpanAttributes.RETRIEVAL_DOCUMENTS, json.dumps(docs))
```

Where `docs` is a list of `{"document.content": ..., "document.score": ...}`
per OpenInference retrieval conventions. This unlocks Phoenix's retrieval
analysis view (query → retrieved docs with scores/order).

### Gotchas

- **Embedding vector size:** writing the full embedding vector as an attribute
  bloats spans. Set it only if the vector is small, or omit it and record just
  the model name + input text + vector dimensionality. Phoenix can render
  embeddings without the raw vector if dimensionality is set.
- **Retrieval document format:** Phoenix expects each retrieved doc as a JSON
  object with at least `document.content` and `document.score`. Qdrant returns
  `payload` + `score` — map accordingly.
- The embedding call already has try/except error handling (`memory.py:111`)
  that returns `None` on failure; ensure the span records the exception before
  swallowing (use `span.record_exception(e)` + `set_status(ERROR)` so the
  failure is visible in Phoenix rather than silently absent).

### Deliverable

The semantic-memory pipeline (embed query → Qdrant search → results) is visible
in Phoenix as EMBEDDING + RETRIEVER spans with model names, query text, and
retrieved documents + scores.

---

## Phase 5: HTTP-Layer & Infrastructure Instrumentation

### Backend

**Dependencies:** add via `uv add`:
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-httpx`

**Register in `init_observability`:**

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
```

`FastAPIInstrumentor.instrument_app(app)` needs the FastAPI `app` instance, so
`init_observability`'s signature must accept `app` (or it is instrumented where
`app` is created in `main.py` after `init_observability` runs). Prefer keeping
`init_observability(config)` focused on the provider/instrumentors and adding a
small `instrument_app(app)` call in `main.py` right after app creation — keeps
the no-op-safe init unchanged.

This gives you server entry spans (with route, method, status) and client spans
for every outbound httpx call (LLM providers, tool servers, Qdrant, SearXNG),
stitched into the same traces as the LLM/tool spans from prior phases.

**Trace title generation.** `_generate_title` (`base.py:571`) spawns a
background task via `asyncio.create_task` that does **not** inherit the OTel
context (flagged in Phase 3 gotchas). Wrap the title-generation LLM call so it
produces its own trace: either explicitly attach the session context in the
background task, or accept that it stands as a standalone trace tagged with
`session_id` via `using_attributes`. Standalone-but-tagged is acceptable and
simpler — it still groups under the same session in Phoenix.

### Gotchas

- **FastAPI app timing:** `instrument_app(app)` must run after the app object
  exists and before it starts serving. The current `main.py:46` calls
  `init_observability` before `uvicorn.run`; ensure app instrumentation happens
  in the same window.
- **Noise:** httpx instrumentation will create spans for **every** outbound
  call, including health checks or non-LLM traffic. If this is too noisy, use
  request hooks to drop/sample irrelevant routes. Start unfiltered and revisit.
- **Context loss in `create_task`:** any other `asyncio.create_task` usage in
  the codebase (search for it) will similarly lose the parent context. Audit
  and either pass context explicitly or tag the new task with `using_attributes`.

### Deliverable

End-to-end distributed traces: FastAPI request → agent loop → LLM calls → tool
calls → outbound httpx calls, all stitched together. Title generation appears as
a (standalone, session-tagged) trace.

---

## Out of Scope (tracked separately in `tracing-future-ideas.md`)

The following Phoenix capabilities are **not** part of this implementation spec.
They depend on the richer span data produced here and are documented as future
ideas:

- Phoenix Projects (routing traces into separate projects per environment/agent)
- Evaluations (LLM-as-a-judge, code-based, human annotations)
- Prompt Playground + Span Replay
- Prompt management (versioned prompts synced via SDK)
- Datasets & Experiments
- PXI (Phoenix's built-in debugging agent)

## Testing & Validation

Per phase, validate by:
1. Run mikoshi locally with Phoenix (`docker compose -f docker-compose.dev.yaml
   up phoenix`) and a `tracing:` block in `config.yaml`.
2. Trigger the relevant flow (send a chat message, trigger a tool call, save +
   recall a memory).
3. Open Phoenix UI at `http://localhost:6006` and confirm:
   - Phase 1: traces arrive (port fix works), project name is correct.
   - Phase 2: LLM spans show structured messages, invocation params, tokens;
     retry events appear.
   - Phase 3: each tool call is a separate span; session/user/metadata/tags
     appear on **all** spans in a turn; Sessions view groups turns.
   - Phase 4: EMBEDDING + RETRIEVER spans appear with docs + scores.
   - Phase 5: FastAPI + httpx spans stitch into the full trace.
4. Confirm tracing-disabled mode still works (no config → no errors, no-op spans).

Add unit tests for `mikoshi/observability` (none exist today): at minimum, test
that `init_observability(None)` is a no-op and that `@observe` propagates
exceptions and sets status ERROR.
