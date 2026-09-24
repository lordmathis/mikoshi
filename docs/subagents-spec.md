# Sub-Agent Delegation — Implementation Spec

## Overview

Add a `subagents__delegate` tool that lets the main agent delegate a self-contained
subtask to a named sub-agent persona from the `AgentRegistry`. Sub-agents run with a
fresh in-memory context (the task text is their only input), stream their transcript to
the UI live, persist that transcript to the chat DB tagged with a `phase`, and return
their final response as the tool result. The parent conversation never sees the
sub-agent's transcript in its LLM context.

Core mechanism: a nullable `phase` column on `Message`. One predicate decides what
belongs to the real conversation; everything else is display-only transcript.

## Tech Stack

Unchanged: Python/FastAPI backend, SQLAlchemy + SQLite, React/Tailwind webui.

## Core Principles

1. **`phase IS NULL` = real conversation. Anything else = display-only transcript.**
   A single predicate on `Message` gates every conversation-semantic code path.
2. **Sub-agents are registry personas, not a new concept.** A sub-agent is a
   `SubAgent` instance configured from an existing `AgentPluginBase` class's attrs
   (system_prompt, tool_servers, provider/model, max_iterations). No new config format.
3. **Depth limit is structural.** Spawned sub-agents never receive the `subagents`
   toolset, so delegation below depth 1 is impossible. No counters, no runtime checks.
4. **Blocking, synchronous delegation.** The tool call awaits the sub-agent. No
   background dispatch, no queues, no completion delivery machinery.

## Out of Scope (explicitly rejected)

Background/async delegation, batch parallel tasks, steering, heartbeats, timeouts,
output-schema validation, summary token budgeting, depth > 1, per-call model overrides,
result truncation. Revisit only with a concrete failure caused by their absence.

---

## Phase 1: `Message.phase` and the conversation filter

### Backend

**Model + migration:**
- Add `phase: Mapped[Optional[str]] = mapped_column(String, nullable=True)` to
  `Message` (`db/models.py`).
- Add the single filter predicate on the model:

```python
@property
def in_conversation(self) -> bool:
    """True if this message belongs to the parent conversation (not a
    display-only sub-agent/stage transcript)."""
    return self.phase is None
```

- Add `_migrate_message_phase_column` to `db/migrations.py` following the existing
  idempotent `ALTER TABLE messages ADD COLUMN phase TEXT` pattern, registered in
  `run_migrations`.

**Persistence:**
- `Database.save_message(..., phase: Optional[str] = None)` — include in the INSERT
  (`db/db.py:80`).

**Agent threading:**
- `BaseAgent.__init__`: `self.phase = kwargs.get("phase")` (`agents/base.py:56`).
- `_save_message`, `_save_assistant_message`, `_save_user_message`
  (`agents/base.py:514-559`) pass `phase=self.phase` through to `db.save_message`.
- `BaseAgent._format_message` (`agents/base.py:486`) includes `"phase": msg.phase`
  read from the DB row. This makes phase survive SSE replay and makes
  `_InnerResearchAgent._format_message` obsolete.

**The three filter callers** — each skips messages where `in_conversation` is False:
- `format_history` loop (`agents/context/messages.py:189`)
- `_find_last_exchange` loop (`agents/base.py:427`) — fixes retry/edit treating a
  sub-agent's internal `user` message as the last user turn
- `generate_title` history slice (`agents/context/naming.py:58`)

**API:**
- `serialize_message` (`routes/schemas.py:37`) adds `"phase": msg.phase`.

### Frontend

None required — `phase?: string` already exists on the message type
(`webui/src/lib/api.ts:56`) and the badge renders it (`chat/chat-message.tsx:160-177`).

### Verification

- Existing DB migrates cleanly; `save_message` round-trips phase.
- `format_history`, `_find_last_exchange`, `generate_title` exclude phase-tagged
  messages; DB history endpoints include them.
- Full test suite passes (no behavior change for phase-NULL messages).

**Deliverable:** Phase-tagged messages persist, are visible in the UI after refresh,
and are invisible to LLM context, retry/edit, and title generation.

---

## Phase 2: Shared `SubAgent` class (dedup with research)

### Backend

**New `mikoshi/agents/subagent.py`:**

```python
class SubAgent(WorkspaceAgent):
    """Agent whose transcript lives in memory and in the DB tagged with a
    phase — never in the parent's LLM context. `message` becomes the first
    user turn; a second `_loop(message)` appends and continues."""
```

- Constructor: `phase` handled by `BaseAgent`; `last_response: str = ""`;
  `_messages: List[ChatCompletionMessageParam] = []`.
- `_get_iteration_context(message)`:
  - If `_messages` exists: append `{"role": "user", "content": message}`, return.
  - Else seed: `[{"role": "system", "content": self.system_prompt}]`, then
    `self._insert_workspace_context(self._messages)` (tree + AGENTS.md when the chat
    has a workspace), then persist the task as a phase-tagged user message via
    `self._save_message("user", message)`, append it, return.
- `_process_final_response`: capture `self.last_response` and append the assistant
  message to `_messages` before delegating to `super()` (same as
  `_InnerResearchAgent._process_final_response`, `agents/research/agent.py:63-73`).

**Extract workspace-context injection:** move the tree/AGENTS.md block from
`WorkspaceAgent._get_iteration_context` (`agents/workspace.py:53-71`) into
`_insert_workspace_context(self, messages)` on `WorkspaceAgent`; the original method
calls the helper (behavior unchanged). `SubAgent(WorkspaceAgent)` reuses it so
sub-agents in workspace chats see the file tree and AGENTS.md.

**Promote the filtered queue:** move `_FilteredQueue` from
`agents/research/helpers.py:17` to `agents/streaming.py` as public `FilteredQueue`
(swallows `STREAM_DONE` so the inner agent can't end the outer stream).
`agents/research/helpers.py` re-exports for its existing importers.

**Research dedup:** delete `_InnerResearchAgent` (`agents/research/agent.py:34-73`);
`ResearchAgent.spawn` (`agent.py:293-323`) constructs `SubAgent` instead. Research
stage phases (`research_plan`, `query_00`, …) pass through unchanged. Note: research
inner transcripts now include the stage prompt as a persisted phase-tagged user
message (today it is not persisted) — a display improvement, acceptable.

### Verification

- All existing research agent tests pass unmodified.
- A `SubAgent` seeded twice continues the same in-memory conversation.

**Deliverable:** One inner-agent implementation shared by research stages and (in
Phase 3) the delegate tool; research phase badges now survive page refresh.

---

## Phase 3: `spawn_subagent` and the `subagents` toolset

### Backend

**`AgentManager.spawn_subagent` (`agents/manager.py`):**

```python
def spawn_subagent(self, agent_name: str, chat_id: str) -> SubAgent
```

- `agent_class = self.agent_registry.get_agent_class(agent_name)`; raise
  `ValueError(f"Unknown agent '{agent_name}'. Available: {', '.join(...)}")` when absent.
- Resolve provider via `agent_class.provider_id` (same as `_hydrate`'s plugin branch,
  `manager.py:230-255`); take `workspace_id`/`connector_name` from the chat.
- Params from class attrs: `system_prompt`, `tool_servers` with the `subagents` server
  stripped (structural depth limit), `temperature`, `max_tokens`, `context_window`,
  `max_iterations` (class default, else the existing default of 5).
- Construct via `self._construct_agent(SubAgent, ...)` with
  `phase=f"subagent:{agent_name}"`. Do **not** register in `self._agents` — a
  sub-agent is not the chat's agent.

**New `mikoshi/tools/builtin/subagents.py`:**

```python
class SubagentTools(ToolSetHandler):
    server_name = "subagents"
```

- `@tool` method `delegate(agent: str, task: str)` (declare `context: ToolCallContext`
  for injection; `require_approval=False` — the sub-agent's own dangerous tools gate
  through the normal approval flow, chat-scoped since `chat_id` is shared).
- Flow: `sub = agent_manager.spawn_subagent(agent, context.chat_id)` →
  `await sub._loop(task, queue=FilteredQueue(context.stream_queue))` →
  `return sub.last_response or "Sub-agent produced no output."`
- Parameters schema: `agent` (string), `task` (string).
- Tool description guidance (static part): delegate self-contained subtasks; "The
  sub-agent knows nothing about this conversation — include all context, files, and
  requirements in the task"; the final message is returned verbatim as the tool
  result, so instruct the sub-agent via the task to end with a complete report.
- Dynamic description: override `list_tools()` to append the current agent names from
  the bound registry (`"Available agents: architect, code, …"`), so the model never
  guesses names. Rebuild the description each call; `initialize()` runs before the
  registry exists, so the binding must be late.

**Wiring (late injection — `ToolManager` starts before `AgentManager` exists):**
- Add `(SubagentTools, None)` to `BUILTIN_TOOLS` (`tools/manager.py:29`).
- `ToolManager.bind_agent_manager(agent_manager)`: forwards to the registered
  `SubagentTools` handler (store on the instance). Called from `lifespan.py` right
  after `agent_manager` is created (~line 115).
- Delegate fails with a model-readable error if invoked before binding (cannot happen
  in practice; tools only run during chat turns).

**Streaming plumbing:**
- `ToolCallContext` (`tools/context.py:28`) gains
  `stream_queue: Optional[asyncio.Queue] = None`.
- `BaseAgent._execute_tool_calls` passes `stream_queue=queue` when building the
  context (`agents/base.py:173-179`). The parent's `queue` is already in scope there;
  no other tool uses the field.

**Availability is opt-in:** the `subagents` server appears only for chats/personas
whose `tool_servers` include `"subagents"`. No automatic injection.

### Frontend

None required. Optional cosmetic: render `subagent:{name}` phases as the bare agent
name in the existing badge (strip the prefix).

### Verification

- `spawn_subagent` strips the `subagents` server and uses persona attrs/provider.
- `delegate` with an unknown agent returns a model-readable error listing names.
- Integration: a parent turn that delegates produces, in DB order — parent user
  message, parent assistant message with the `subagents__delegate` tool call, the
  sub-agent's phase-tagged transcript, the parent's `role="tool"` result, the parent's
  next assistant message — and `format_history` for the next turn contains only the
  non-tagged messages (no dangling `tool_calls`, since the parent's tool call and
  result are saved by the parent without phase).
- A sub-agent tool requiring approval surfaces in the existing approval UI and blocks
  until resolved (inherited via shared `tool_manager` + `chat_id` + the sub-agent's
  own `_execute_tool_calls` closure over the filtered queue).

**Deliverable:** The main agent can delegate a subtask to any registered persona;
the result returns as the tool result; the transcript is visible live and after
refresh, but never enters the parent's context.

---

## Homelab impact

To enable delegation for a persona, add `"subagents"` to its `tool_servers` in
`mikoshi/plugins/agents/` (homelab repo). All registered personas are automatically
delegatable targets with no changes. No breaking changes to existing plugins; the
`Message` schema change is a nullable column behind an idempotent migration.
