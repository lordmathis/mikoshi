# Mikoshi

A flexible chat client with Web UI that integrates multiple AI providers, tools, and agent frameworks through a unified plugin architecture.

> **⚠️ Disclaimer**
>
> This is a personal project provided as-is for educational and personal use. No feature requests or support requests will be accepted. Feel free to fork and modify for your own needs.

**Features**:
- OpenAI-compatible and Anthropic API support
- Plugin architecture (agents, tools, skills) and MCP integration
- Git-based workspaces with file management
- Audio transcription and text-to-speech
- Tool approval system


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

   Server will start on `http://localhost:8000` with the Web UI served at the same address

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

Mikoshi uses a YAML configuration file (`config.yaml`) to set up providers, MCP servers, and plugins. Environment variables can be referenced using `${ENV_VAR}` syntax, which will be automatically expanded with values from your environment.

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

**MCP Types:**
- `stdio`: Standard input/output communication
- `sse`: Server-sent events

**Configuration options:**
- `command`: The command to run the MCP server
- `args`: List of arguments to pass to the command
- `type`: Communication type (`stdio` or `sse`)
- `env`: Environment variables to pass to the MCP server process

### Plugin Configuration

```yaml
plugins:
  agents_dir: "agents"  # Directory for agent plugins
  tools_dir: "tools"  # Directory for tool plugins
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

### Audio Configuration

Configure audio transcription and text-to-speech services (optional):

```yaml
audio:
  transcription:
    model: "whisper-1"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
  tts:
    model: "tts-1"
    voice: "alloy"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
```

**Transcription options:**
- `model`: Transcription model to use (default: `"whisper-1"`)
- `base_url`: API base URL for the transcription service
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

### Additional Configuration Options

```yaml
history_db_path: "mikoshi.db"       # SQLite database for conversation history
uploads_dir: "uploads"               # Directory for uploaded files
data_dir: "data"                     # Directory for tool data storage
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

Mikoshi has a flexible plugin architecture supporting three types of plugins:

### 1. Agent Plugins

Agent plugins allow you to create custom chat agents with specific configurations. Three base classes are available:

#### ReActAgentPlugin

Standard ReAct-style tool-calling agents. Create a Python file in the configured `agents_dir` (e.g., `plugins/agents/my_agent.py`):

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

Stateful agents that maintain JSON state across conversation turns. Useful for agents that need to track context (e.g., workout logging, task management):

```python
from mikoshi.agents import StructuredAgentPlugin


class StatefulAgent(StructuredAgentPlugin):
    name = "stateful-agent"
    provider_id = "openrouter"
    model_id = "openai/gpt-4"
    tool_servers = ["my_tools"]
    max_iterations = 5

    system_prompt = """You are a stateful assistant. When ready to respond,
output a JSON object with two keys:
- "user_message": the response to show the user
- "new_state": updated state object to persist
"""
```

#### Custom Setup

Both agent types support a `post_init()` hook for custom initialization after dependency injection:

```python
class MyAgent(ReActAgentPlugin):
    name = "my-agent"
    provider_id = "openrouter"
    model_id = "openai/gpt-4"

    def post_init(self) -> None:
        self._custom_state = {}
```

#### WorkspaceAgentPlugin

Agent specialized for workspace interactions that automatically injects the workspace file tree into the LLM context on each iteration:

```python
from mikoshi.agents.workspace import WorkspaceAgentPlugin


class RepositoryAssistant(WorkspaceAgentPlugin):
    name = "repo-assistant"
    provider_id = "openrouter"
    model_id = "openai/gpt-4"
    system_prompt = "You are a helpful coding assistant."
    tool_servers = ["workspace"]
```

### 2. Tool Plugins

Tool plugins extend Mikoshi with custom capabilities. They inherit from `ToolSetHandler` and use the `@tool` decorator to define individual tools. Each tool server gets its own persistent storage directory via `self.get_persistent_storage()`, and tools are exposed to agents as `{server_name}__{tool_name}`. Tools can optionally access provider, model, and workspace info by accepting a `context: ToolCallContext` parameter, call other tools via `self.call_other_tool()`, or require explicit user approval before execution by passing `require_approval=True` to the decorator. Override `initialize()` and `cleanup()` for lifecycle setup.

**Creating a Tool Plugin:**

1. Create a Python file in the configured `tools_dir` (e.g., `plugins/tools/my_tools.py`)
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

### 3. Skill Plugins

Skill plugins provide reusable knowledge and prompt templates that can be injected into conversations via `@mention` syntax.

**Creating a Skill Plugin:**

1. Create a directory in the configured `skills_dir` (e.g., `plugins/skills/code_review/`)
2. Add a `SKILL.md` file with the skill content:

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
