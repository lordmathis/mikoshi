import logging
from typing import Dict, Optional, Type

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.react import ReActAgent, ReActAgentPlugin
from mikoshi.agents.research import ResearchAgentPlugin
from mikoshi.agents.workspace import WorkspaceAgent, WorkspaceAgentPlugin
from mikoshi.agents.structured import StructuredAgentPlugin
from mikoshi.config import TitleGenerationConfig, WorkspaceConfig
from mikoshi.db.db import Database
from mikoshi.plugins import discover_plugins
from mikoshi.providers.registry import ProviderRegistry
from mikoshi.skills.registry import SkillRegistry
from mikoshi.tools.manager import ToolManager
from mikoshi.tools.workspace import WORKSPACE_SERVER_NAME
from mikoshi.workspace import WorkspaceService

logger = logging.getLogger(__name__)

_PLUGIN_BASES = (
    ReActAgentPlugin,
    StructuredAgentPlugin,
    WorkspaceAgentPlugin,
    ResearchAgentPlugin,
)


class AgentRegistry:
    """Discovers and registers agent plugin classes from a directory."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        tool_manager: ToolManager,
        agents_dir: str,
    ):
        self.provider_registry = provider_registry
        self.tool_manager = tool_manager
        self.agents_dir = agents_dir
        self._agent_classes: Dict[
            str,
            Type[
                ReActAgentPlugin
                | StructuredAgentPlugin
                | WorkspaceAgentPlugin
                | ResearchAgentPlugin
            ],
        ] = discover_plugins(
            agents_dir,
            _PLUGIN_BASES,
            exclude_bases=_PLUGIN_BASES,
            required_attrs=["provider_id", "model_id"],
        )

    def get_agent_class(
        self, name: str
    ) -> Optional[
        Type[
            ReActAgentPlugin
            | StructuredAgentPlugin
            | WorkspaceAgentPlugin
            | ResearchAgentPlugin
        ]
    ]:
        return self._agent_classes.get(name)

    def list_agent_names(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agent_classes.keys())

    def get_default_agent_name(self, workspace: bool = False) -> Optional[str]:
        """Return the name of the default agent. Prefers WorkspaceAgentPlugin subclasses when workspace=True."""
        for name, cls in self._agent_classes.items():
            if not getattr(cls, "default", False):
                continue
            is_workspace = issubclass(cls, WorkspaceAgentPlugin)
            if workspace == is_workspace:
                return name
        for name, cls in self._agent_classes.items():
            if getattr(cls, "default", False):
                return name
        return None


class AgentManager:
    """Manages agent instances per chat. Handles instantiation and lifecycle."""

    def __init__(
        self,
        db: Database,
        provider_registry: ProviderRegistry,
        agent_registry: AgentRegistry,
        tool_manager: ToolManager,
        data_dir: str,
        workspace_config: WorkspaceConfig,
        skill_registry: Optional[SkillRegistry] = None,
        title_generation: Optional[TitleGenerationConfig] = None,
        workspace_service: Optional[WorkspaceService] = None,
    ):
        self.db = db
        self.provider_registry = provider_registry
        self.agent_registry = agent_registry
        self.tool_manager = tool_manager
        self.skill_registry = skill_registry
        self.title_generation = title_generation
        self.data_dir = data_dir
        self.workspace_config = workspace_config
        self.workspace_service = workspace_service
        self._agents: Dict[str, BaseAgent] = {}

    def _resolve_agent_params(
        self,
        config: dict,
        defaults: Optional[Dict] = None,
    ) -> Dict:
        """Extract and resolve agent constructor params from config dict.

        Args:
            config: Configuration dictionary with model, system_prompt, tool_servers, model_params
            defaults: Optional defaults from agent class attributes

        Returns:
            Dict with resolved constructor params
        """
        model_params = config.get("model_params") or {}
        d = defaults or {}

        return {
            "system_prompt": config.get("system_prompt") or d.get("system_prompt", ""),
            "tool_servers": config.get("tool_servers") or d.get("tool_servers", []),
            "temperature": model_params.get("temperature", d.get("temperature")),
            "max_tokens": model_params.get("max_tokens", d.get("max_tokens")),
            "max_iterations": model_params.get(
                "max_iterations", d.get("max_iterations", 5)
            ),
        }

    def _resolve_title_params(self) -> Dict:
        if not self.title_generation:
            return {}

        title_provider = None
        if self.title_generation.provider:
            title_provider = self.provider_registry.get_provider(
                self.title_generation.provider
            )
            if not title_provider:
                logger.warning(
                    f"Title generation provider '{self.title_generation.provider}' not found, "
                    f"falling back to default"
                )
                return {}

        return {
            "title_provider": title_provider,
            "title_model_id": self.title_generation.model,
        }

    @staticmethod
    def _inject_workspace_tools(params: Dict, workspace_id: Optional[str]) -> None:
        if workspace_id:
            servers = list(params.get("tool_servers", []))
            if WORKSPACE_SERVER_NAME not in servers:
                servers.append(WORKSPACE_SERVER_NAME)
            params["tool_servers"] = servers

    def _construct_agent(
        self,
        agent_cls: Type[BaseAgent],
        chat_id: str,
        provider,
        model_id: str,
        workspace_id: Optional[str],
        connector_name: Optional[str],
        params: Dict,
    ) -> BaseAgent:
        kwargs = {
            "chat_id": chat_id,
            "db": self.db,
            "provider": provider,
            "tool_manager": self.tool_manager,
            "model_id": model_id,
            "skill_registry": self.skill_registry,
            "workspace_id": workspace_id,
            "data_dir": self.data_dir,
            "connector_name": connector_name,
            "workspace_config": self.workspace_config,
            "workspace_service": self.workspace_service,
            **params,
            **self._resolve_title_params(),
        }
        agent = agent_cls(**kwargs)
        if hasattr(agent, "post_init"):
            agent.post_init()
        return agent

    def _hydrate(self, chat_id: str, config: dict) -> BaseAgent:
        """Instantiate agent from config dict without persisting."""
        chat = self.db.get_chat(chat_id)
        workspace_id = chat.workspace_id if chat else None

        model = config.get("model")
        if not model:
            model = self.agent_registry.get_default_agent_name(
                workspace=bool(workspace_id)
            )

        if not model:
            raise ValueError("Model is required and no default agent found")

        connector_name = None
        if workspace_id:
            workspace = self.db.get_workspace(workspace_id)
            if workspace:
                connector_name = workspace.connector

        if ":" in model:
            provider_name, model_id = model.split(":", 1)
            provider = self.provider_registry.get_provider(provider_name)
            if not provider:
                raise ValueError(f"Provider '{provider_name}' not found")

            params = self._resolve_agent_params(config)
            self._inject_workspace_tools(params, workspace_id)
            agent_cls = WorkspaceAgent if workspace_id else ReActAgent
            return self._construct_agent(
                agent_cls,
                chat_id,
                provider,
                model_id,
                workspace_id,
                connector_name,
                params,
            )

        agent_class = self.agent_registry.get_agent_class(model)
        if not agent_class:
            raise ValueError(f"Agent '{model}' not found in registry")

        provider = self.provider_registry.get_provider(agent_class.provider_id)
        if not provider:
            raise ValueError(f"Provider '{agent_class.provider_id}' not found")

        defaults = {
            "system_prompt": agent_class.system_prompt,
            "tool_servers": agent_class.tool_servers,
            "temperature": agent_class.temperature,
            "max_tokens": agent_class.max_tokens,
            "max_iterations": agent_class.max_iterations,
        }
        params = self._resolve_agent_params(config, defaults)
        self._inject_workspace_tools(params, workspace_id)
        return self._construct_agent(
            agent_class,
            chat_id,
            provider,
            agent_class.model_id,
            workspace_id,
            connector_name,
            params,
        )

    def create(self, chat_id: str, config: dict) -> BaseAgent:
        """Create an agent for a chat and persist config to DB."""
        if chat_id in self._agents:
            raise ValueError(f"Agent for chat '{chat_id}' already exists")

        chat = self.db.get_chat(chat_id)
        if not chat:
            raise ValueError(f"Chat '{chat_id}' not found")

        agent = self._hydrate(chat_id, config)
        self._agents[chat_id] = agent

        model = config.get("model")

        if model is None:
            raise ValueError("Model is required in config")

        system_prompt = config.get("system_prompt")
        tool_servers = config.get("tool_servers") or []
        model_params = config.get("model_params") or {}
        self.db.save_chat_config(
            chat_id=chat_id,
            model=model,
            system_prompt=system_prompt,
            tool_servers=tool_servers,
            model_params=model_params,
        )

        return agent

    def get(self, chat_id: str) -> BaseAgent:
        """Get agent for chat, hydrating from DB config if not in memory."""
        agent = self._agents.get(chat_id)
        if agent:
            return agent

        config_dict = self.db.get_chat_config(chat_id)
        if not config_dict:
            raise ValueError(f"Chat '{chat_id}' not found")

        agent = self._hydrate(chat_id, config_dict)
        self._agents[chat_id] = agent
        return agent

    def remove(self, chat_id: str) -> None:
        """Remove agent from memory."""
        if chat_id in self._agents:
            del self._agents[chat_id]
