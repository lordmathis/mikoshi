# Mikoshi

A flexible chat client with Web UI that integrates multiple AI providers, tools, and agent frameworks through a unified plugin architecture.

> **⚠️ Disclaimer**
>
> This is a personal project provided as-is for educational and personal use. No feature requests or support requests will be accepted. Feel free to fork and modify for your own needs.

**Features**:
- OpenAI-compatible and Anthropic API support
- Plugin architecture (agents, tools, skills) and MCP integration
- Four agent base classes: ReAct, Structured, Workspace, and Research agents
- Git-based workspaces with built-in file operations (read/write/edit/grep/find/ls) and git operations (status/diff/commit/pull/push)
- Repository browsing via GitHub and Forgejo/Gitea connectors
- Chat branching, message edit, and retry
- Audio transcription and text-to-speech
- Token estimation for repository files


## Quick Start

### Prerequisites
- Python 3.12+
- Node.js (for Web UI)
- uv (Python package manager)

### Installation

1. **Install Python dependencies:**
   ```bash
   uv sync
   ```

2. **Configure the application:**
   Edit `config.yaml` to set up providers, MCP servers, and plugins (see Configuration section)

### Running the Application

1. **Build the Web UI:**
   ```bash
   cd webui
   npm install
   npm run build
   cd ..
   ```

2. **Start the server:**
   ```bash
   uv run python -m mikoshi.main
   ```

   Server will start on `http://localhost:8000` with the Web UI served at the same address.

   For development, the Web UI can be run separately with hot reload:
   ```bash
   cd webui
   npm run dev
   ```
   The dev server runs on `http://localhost:5173` and proxies API calls to the backend.

### Running with Docker

1. **Build the Docker image:**
    ```bash
    docker build -t mikoshi .
    ```

2. **Run the container:**

   ```bash
   docker run -p 8000:8000 \
     -v $(pwd)/config.yaml:/app/config.yaml \
     -v $(pwd)/mikoshi.db:/app/mikoshi.db \
     mikoshi
   ```

## Configuration

Mikoshi uses a YAML configuration file (`config.yaml`) to set up providers, MCP servers, and plugins. Environment variables can be referenced using `${ENV_VAR}` syntax, which will be automatically expanded with values from your environment (or a local `.env` file loaded on startup).

### Server Configuration

```yaml
server:
  host: "0.0.0.0"
  port: 8000
```

### Provider Configuration

Providers define AI model endpoints (OpenAI-compatible or Anthropic APIs):

```yaml
providers:
  openrouter:
    type: "openai"  # or "anthropic" defaults to "openai"
    api_base: "https://openrouter.ai/api/v1"
    api_key: "${OPENROUTER_API_KEY}"
    model_filter:
      conditions:
        - field: "id"
          contains: ":free"  # Filter for free models
        - field: "id"
          excludes: "beta"  # Exclude beta models

  custom_provider:
    type: "openai"
    api_base: "https://your-api.example.com/v1"
    api_key: "${YOUR_API_KEY}"
    model_ids:  # Explicit model list (alternative to model_filter)
      - "gpt-4"
      - "gpt-3.5-turbo"

  anthropic:
    type: "anthropic"
    api_key: "${ANTHROPIC_API_KEY}"
    model_ids:
      - "claude-3-5-sonnet-20241022"
      - "claude-3-5-haiku-20241022"
```

**Configuration options:**
- `type`: Provider type - `"openai"` (default) or `"anthropic"`
- `api_base`: Base URL for the API endpoint (OpenAI-compatible providers only)
- `api_key`: API authentication key (supports environment variables)
- `model_ids`: Explicit list of model IDs to use (alternative to dynamic discovery)
- `model_filter`: Dynamic model filtering with conditions:
  - `field`: JSON path to field (e.g., "id", "architecture.modality")
  - `contains`: Include models where field contains this substring
  - `excludes`: Exclude models where field contains this substring
  - `equals`: Include models where field exactly matches this value
  - `endpoint`: Endpoint appended to `api_base` when listing models (default: `/models`)

When no `model_ids` and no `model_filter.conditions` are set, all models advertised by the provider's `/models` endpoint are exposed.

### MCP (Model Context Protocol) Configuration

```yaml
mcps:
  time:
    command: uvx
    type: stdio
    args:
      - mcp-server-time

  filesystem:
    command: npx
    type: stdio
    args:
      - -y
      - "@modelcontextprotocol/server-filesystem"
      - /path/to/directory
    env:
      CUSTOM_VAR: "value"
mcp_timeout: 60  # Timeout for MCP operations in seconds
```

**Configuration options:**
- `command`: The command to run the MCP server
- `args`: List of arguments to pass to the command
- `type`: Communication type. Currently only `stdio` is implemented (`sse` is accepted by the config schema but will raise at startup).
- `env`: Environment variables to pass to the MCP server process
- `mcp_timeout` (top-level): Timeout in seconds for MCP initialization, tool calls, and shutdown

### Plugin Configuration

```yaml
plugins:
  agents_dir: "agents"  # Directory for agent plugins
  tools_dir: "tools"    # Directory for tool plugins
  skills_dir: "skills"  # Directory for skill plugins
```

### Connector Configuration

Connectors provide repository browsing capabilities (GitHub and Forgejo/Gitea):

```yaml
connectors:
  forgejo:
    type: "forgejo"
    base_url: "${GITEA_HOST}/api/v1"
    token: "${GITEA_ACCESS_TOKEN}"

  github:
    type: "github"
    token: "${GITHUB_TOKEN}"
```

**Configuration options:**
- `type`: Connector type - `"github"` (default) or `"forgejo"`
- `token`: Authentication token
- `base_url`: API base URL (required for Forgejo)

Connectors power the repository browser in the UI and provide authenticated `git pull`/`git push` for workspaces linked to a connector.

### Audio Configuration

Optional audio transcription (ASR) and text-to-speech (TTS). Both services speak the OpenAI-compatible audio API (`/v1/audio/transcriptions` and `/v1/audio/speech`), so any provider implementing those endpoints works. Audio is disabled unless `base_url` is set.

```yaml
audio:
  transcription:
    model: "<transcription-model>"
    base_url: "https://your-audio-provider.example.com/v1"
    api_key: "${AUDIO_API_KEY}"
  tts:
    model: "<tts-model>"
    voice: "<voice-name>"
    base_url: "https://your-audio-provider.example.com/v1"
    api_key: "${AUDIO_API_KEY}"
```

**Transcription options:**
- `model`: Transcription model to use (default: `"whisper-1"`)
- `base_url`: API base URL for the transcription service (required to enable transcription)
- `api_key`: API key (supports environment variables)

**TTS options:**
- `model`: TTS model to use (default: `"tts-1"`)
- `voice`: Voice to use (default: `"alloy"`)
- `response_format`: Audio format (e.g., `"mp3"`, `"wav"`)
- `speed`: Speech speed (0.25 to 4.0)
- `base_url`: API base URL for the TTS service
- `api_key`: API key (supports environment variables)

### Logging Configuration

```yaml
logging:
  target: "mikoshi.log"  # File path, or "stdout" for console output
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
```

When `target` is a file path, Mikoshi uses a rotating file handler (10 MB per file, 5 backups kept).

### Additional Configuration Options

```yaml
history_db_path: "mikoshi.db"       # SQLite database for conversation history
uploads_dir: "uploads"               # Directory for uploaded files
data_dir: "data"                     # Directory for tool data storage and workspaces
file_retention_hours: 24             # Hours before orphan files are cleaned up
title_generation:                    # Optional: use a separate model for chat titles
  provider: "openrouter"
  model: "openai/gpt-4"
```

### Workspace Configuration

Configure default git identity for workspace commits:

```yaml
workspace:
  git_user_name: "Mikoshi Agent"
  git_user_email: "agent@mikoshi"
```

## Plugins

Mikoshi has a flexible plugin architecture supporting three types of plugins. Plugins are discovered automatically from the directories configured under `plugins` (one Python file per class for agents/tools, one directory per skill).

### 1. Agent Plugins

Agent plugins allow you to create custom chat agents with specific configurations. Four base classes are available, all sharing the same class attributes (`name`, `provider_id`, `model_id`, `system_prompt`, `tool_servers`, `max_iterations`, `temperature`, `max_tokens`, `context_window`, `default`). The first agent with `default = True` is selected for new chats; when a workspace chat is created, a `WorkspaceAgentPlugin` subclass is preferred.

#### ReActAgentPlugin

Standard ReAct-style tool-calling agents. Create a Python file in the configured `agents_dir` (e.g., `agents/my_agent.py`):

```python
from mikoshi.agents import ReActAgentPlugin


class MyAgent(ReActAgentPlugin):
    default = True              # Set as the default agent
    name = "my-agent"           # Unique identifier
    provider_id = "openrouter"  # References a provider from config
    model_id = "openai/gpt-4"
    system_prompt = "You are a helpful assistant."
    tool_servers = ["web_tools", "time"]  # Tool servers to make available
    max_iterations = 5
    temperature = 0.7
    max_tokens = 2000
```

#### StructuredAgentPlugin

Stateful agents that maintain JSON state across conversation turns. Useful for agents that need to track context (e.g., workout logging, task management). The agent reads `CURRENT STATE` from the database, includes it in the system prompt, and expects the final response to be a JSON object with `user_message` (string) and `new_state` (object) keys. The returned state is merged into the persisted state.

```python
from mikoshi.agents import StructuredAgentPlugin


class StatefulAgent(StructuredAgentPlugin):
    name = "stateful-agent"
    provider_id = "openrouter"
    model_id = "openai/gpt-4"
    tool_servers = ["my_tools"]
    max_iterations = 5
```

#### WorkspaceAgentPlugin

Agent specialized for workspace interactions. It inherits from `ReActAgentPlugin` and automatically injects two pieces of context into every iteration:

- A tree view of the workspace files
- The contents of `AGENTS.md` if one exists at the workspace root

The built-in `workspace` tool server is added automatically to the agent's `tool_servers` when a chat is linked to a workspace.

```python
from mikoshi.agents.workspace import WorkspaceAgentPlugin


class RepositoryAssistant(WorkspaceAgentPlugin):
    name = "repo-assistant"
    provider_id = "openrouter"
    model_id = "openai/gpt-4"
    system_prompt = "You are a helpful coding assistant."
    tool_servers = ["workspace"]
```

#### ResearchAgentPlugin

A multi-stage research agent that plans, researches, replans, and synthesizes a final report. It runs an outer control loop driven entirely by workspace file state (no model output is trusted for control flow):

1. **Planner** — produces `RESEARCH_PLAN.md` with a checklist of research tasks
2. **Researcher** — runs an inner ReAct agent for each pending task, writing findings to `findings/NN-slug.md`
3. **Replanner** — inspects plan + latest findings and revises remaining tasks
4. **Synthesizer** — reads all findings and writes `REPORT.md`

The outer loop reconciles the plan against existing findings files each iteration, so completed tasks are never re-researched. It requires a workspace (the workspace is the communication channel between stages) and typically benefits from a `web_tools` tool server.

```python
from mikoshi.agents import ResearchAgentPlugin


class DeepResearch(ResearchAgentPlugin):
    name = "research"
    provider_id = "openrouter"
    model_id = "anthropic/claude-3.5-sonnet"
    tool_servers = ["web_tools"]
    max_iterations = 15  # used as max_inner_iterations
```

`ResearchAgent` also exposes class-level `max_outer_iterations` (default `15`) and `max_inner_iterations` (default `15`).

#### Custom Setup

All agent types support a `post_init()` hook for custom initialization after dependency injection:

```python
class MyAgent(ReActAgentPlugin):
    name = "my-agent"
    provider_id = "openrouter"
    model_id = "openai/gpt-4"

    def post_init(self) -> None:
        self._custom_state = {}
```

### 2. Tool Plugins

Tool plugins extend Mikoshi with custom capabilities. They inherit from `ToolSetHandler` and use the `@tool` decorator to define individual tools. Each tool server gets its own persistent storage directory via `self.get_persistent_storage()`, and tools are exposed to agents as `{server_name}__{tool_name}`. Tools can optionally:

- Access provider, model, and workspace info by accepting a `context: ToolCallContext` parameter
- Call other tools via `self.call_other_tool()`
- Override `initialize()` and `cleanup()` for lifecycle setup

**Creating a Tool Plugin:**

1. Create a Python file in the configured `tools_dir` (e.g., `tools/my_tools.py`)
2. Inherit from `ToolSetHandler`, set `server_name` as a class attribute, and define tools using the `@tool` decorator:

```python
from mikoshi.tools.toolset_handler import ToolSetHandler, tool


class MyTools(ToolSetHandler):
    server_name = "my_tools"

    @tool(
        description="Calculate the sum of two numbers",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    )
    async def calculate_sum(self, a: float, b: float) -> dict:
        result = a + b
        return {
            "success": True,
            "result": result,
            "message": f"The sum of {a} and {b} is {result}"
        }
```

#### Built-in Workspace Toolset

A `workspace` tool server is registered automatically (no plugin required) and is added to any chat linked to a workspace. It exposes the following tools, all scoped to the workspace root with path-traversal protection:

| Tool | Description |
| --- | --- |
| `read` | Read a text file (line-numbered, with optional `offset`/`limit`); images are returned as base64, binaries reported as metadata |
| `write` | Create or overwrite a file (creates parent directories) |
| `edit` | Apply targeted `oldText` → `newText` replacements; multiple edits per call; falls back to whitespace/quote-normalized fuzzy matching |
| `grep` | Regex content search across files with optional `glob`, `ignoreCase`, `literal`, `contextLines`, and `limit` |
| `find` | Glob-based file/directory finder |
| `ls` | List directory contents |
| `git_status` | `git status --porcelain` |
| `git_diff` | `git diff` (unstaged) |
| `git_commit` | Stage all and commit with a message (uses the workspace's configured git identity) |
| `git_pull` / `git_push` | Pull/push using connector credentials when the remote is an HTTPS URL |

### 3. Skill Plugins

Skill plugins provide reusable knowledge and prompt templates that can be injected into conversations via `/skill_name` syntax in the user's message. Mentioned skills are appended to the system prompt for that turn.

**Creating a Skill Plugin:**

1. Create a directory in the configured `skills_dir` (e.g., `skills/code_review/`)
2. Add a `SKILL.md` file with optional YAML frontmatter and the skill content:

```markdown
---
required_tool_servers:
  - web_tools
---

# Code Review Assistant

You are an expert code reviewer. When reviewing code:

1. Check for security vulnerabilities
2. Identify potential bugs
3. Suggest performance improvements
4. Verify code style and best practices
5. Provide constructive feedback

Be thorough but concise in your reviews.
```

The `required_tool_servers` frontmatter key activates additional tool servers for the chat when the skill is mentioned.

## Development

- **Lint / type-check (Python):** `uv run ruff check .`
- **Tests (Python):** `uv run pytest`
- **Web UI:** `cd webui && npm run dev` (dev server), `npm run build` (production build), `npm run lint`, `npm run typecheck`, `npm run test`
