import os
from enum import Enum
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel


class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class FilterCondition(BaseModel):
    field: str  # JSONPath expression to the field (e.g., "id", "architecture", "pricing.prompt")
    contains: Optional[str] = None
    excludes: Optional[str] = None
    equals: Optional[Any] = None


class ModelFilter(BaseModel):
    conditions: List[FilterCondition] = []
    endpoint: str = "/models"  # Endpoint to append to api_base


class ProviderConfig(BaseModel):
    model_ids: Optional[List[str]] = None
    model_filter: Optional[ModelFilter] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    type: ProviderType = ProviderType.OPENAI


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class MCPType(Enum):
    STDIO = "stdio"
    SSE = "sse"


class MCPConfig(BaseModel):
    command: str
    args: List[str] = []
    type: MCPType
    env: Dict[str, str] = {}


class PluginConfig(BaseModel):
    agents_dir: str = "agents"
    tools_dir: str = "tools"
    skills_dir: str = "skills"


class ConnectorType(str, Enum):
    GITHUB = "github"
    FORGEJO = "forgejo"


class ConnectorsConfig(BaseModel):
    type: ConnectorType = ConnectorType.GITHUB
    token: str
    base_url: Optional[str] = None


class TranscriptionConfig(BaseModel):
    model: str = "whisper-1"
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class TTSConfig(BaseModel):
    model: str = "tts-1"
    voice: str = "alloy"
    response_format: Optional[str] = None
    speed: Optional[float] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class AudioConfig(BaseModel):
    transcription: TranscriptionConfig = TranscriptionConfig()
    tts: TTSConfig = TTSConfig()


class LoggingConfig(BaseModel):
    target: str = "mikoshi.log"  # file path, or "stdout"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    level: str = "INFO"


class TitleGenerationConfig(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None


class WorkspaceConfig(BaseModel):
    git_user_name: str = "Mikoshi Agent"
    git_user_email: str = "agent@mikoshi"

class SearchConfig(BaseModel):
    searxng_url: str
    max_results: int = 10
    rate_limit: float = 1.0
    firecrawl_api_key: Optional[str] = None
    firecrawl_api_url: str = "https://api.firecrawl.de"


class MemoryConfig(BaseModel):
    embed_provider: str = ""
    embed_model: str = ""
    vector_size: int = 0
    qdrant_url: str
    collection: str = "memories"


class TracingConfig(BaseModel):
    endpoint: Optional[str] = None


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    providers: Dict[str, ProviderConfig] = {}
    mcps: Dict[str, MCPConfig] = {}
    plugins: PluginConfig = PluginConfig()
    history_db_path: str = "mikoshi.db"
    uploads_dir: str = "uploads"
    data_dir: str = "data"
    mcp_timeout: int = 60
    connectors: Dict[str, ConnectorsConfig] = {}
    audio: AudioConfig = AudioConfig()
    logging: LoggingConfig = LoggingConfig()
    file_retention_hours: int = 24
    title_generation: TitleGenerationConfig = TitleGenerationConfig()
    workspace: WorkspaceConfig = WorkspaceConfig()
    search: Optional[SearchConfig] = None
    memory: Optional[MemoryConfig] = None
    tracing: Optional[TracingConfig] = None


def load_config(path: str) -> AppConfig:
    with open(path, "r") as f:
        content = os.path.expandvars(f.read())
        data = yaml.safe_load(content)

    return AppConfig(**data)
