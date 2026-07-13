# Mikoshi Tracing — Future Ideas

Phoenix capabilities that go **beyond** OpenTelemetry tracing. These are not part
of the current implementation plan (`tracing-enhancement-spec.md`) but become
high-value once the richer span data from that spec is flowing. They require the
`arize-phoenix` client SDK and a live Phoenix server connection, not just OTLP
export.

Listed roughly in order of dependency / recommended sequencing.

## 1. Projects

Route traces into separate Phoenix projects to isolate environments and agent
types. Set via `register(project_name=...)` (already parameterized in Phase 1 of
the enhancement spec). Candidate split:

- `mikoshi-dev` vs `mikoshi-prod` — driven by `deployment_environment` config
- `mikoshi-base-agent` vs `mikoshi-research-agent` — driven by agent class

Letting you compare latency/tokens/errors per agent type without cross-contamination.
**Lowest effort** of these ideas since the plumbing arrives in Phase 1.

## 2. Evaluations (LLM-as-a-judge)

Phoenix's highest-value feature. Use `phoenix.Client` to fetch spans and run
evaluators; results attach as annotations and populate quality dashboards.
Strong candidates given mikoshi's shape:

- **Tool-selection correctness** — did the agent pick the right tool for the
  user's intent? (judge against the user message + available tool descriptions)
- **Response helpfulness** — generic quality score on the final assistant turn
- **Hallucination / QA** — for the research agent's synthesis stage
- **Context relevance / retrieval quality** — once RETRIEVER spans exist
  (Phase 4), score whether retrieved memories were actually useful

Integrations to consider: Phoenix's built-in eval templates, or bring-your-own
from Ragas / DeepEval / Cleanlab. Human annotations can be added in-UI as ground
truth.

## 3. Prompt Playground + Span Replay

Once LLM spans are structured (enhancement Phase 2), Phoenix's playground can
**replay** any captured LLM call with different prompts, models, or
temperatures — debugging failures without touching code. Natural fit for
diagnosing bad tool selections or weak research synthesis after the fact.

## 4. Prompt Management

Store and version mikoshi's system prompts in Phoenix; sync them into the app
via the SDK ("prompts in code"). Agent system prompts become versioned,
comparable across changes, and editable in the UI without a deploy. Pairs with
experiments (#5) to prove a prompt change improves quality before rollout.

## 5. Datasets & Experiments

Collect real traces into datasets, rerun them through prompt/model changes, and
compare evaluation scores side-by-side to confirm a change actually improved
quality. Particularly valuable for iterating on the research agent's stages
(`research_stage`, `synthesis`) where regression risk is highest.

## 6. PXI (Phoenix Built-in Agent)

Phoenix's in-product agent can inspect your traces and suggest prompt/context
improvements in context. Becomes useful once a meaningful volume of structured
traces + evals exist.

---

## Prerequisites

All of the above assume the work in `tracing-enhancement-spec.md` is complete
(especially Phase 2 structured LLM spans and Phase 3 context propagation), since
Phoenix's evaluation, replay, and prompt tooling read OpenInference span
attributes that the current hand-rolled spans do not populate.

## When to revisit

Revisit this document once the enhancement spec's Phase 2 (LLM
auto-instrumentation) and Phase 3 (tool/session semantics) are shipped and
real traffic is flowing into Phoenix. At that point the data needed to make
evals, replay, and experiments worthwhile will exist.
