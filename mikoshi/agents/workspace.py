import logging
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.react import ReActAgent
from mikoshi.db.db import Database
from mikoshi.providers.provider import Provider
from mikoshi.skills.registry import SkillRegistry
from mikoshi.tools.manager import ToolManager
from mikoshi.workspace import WorkspaceService

logger = logging.getLogger(__name__)


def format_file_tree(files: List[str]) -> str:
    """Format a flat list of file paths into a tree structure string."""
    if not files:
        return "Empty workspace"

    tree = {}
    for path in files:
        parts = path.split("/")
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

    lines = []

    def _render(node, prefix=""):
        # Sort keys: directories first, then alphabetically
        sorted_keys = sorted(node.keys(), key=lambda k: (len(node[k]) == 0, k.lower()))
        for i, key in enumerate(sorted_keys):
            is_last = i == len(sorted_keys) - 1
            connector = "└── " if is_last else "├── "
            
            if node[key]:  # Directory
                lines.append(f"{prefix}{connector}{key}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                _render(node[key], new_prefix)
            else:  # File
                lines.append(f"{prefix}{connector}{key}")

    _render(tree)
    return "\n".join(lines)


class WorkspaceAgent(ReActAgent):
    """Agent specialized for workspaces with automatic tree injection."""

    def __init__(
        self,
        chat_id: str,
        db: Database,
        provider: Provider,
        tool_manager: ToolManager,
        model_id: str,
        data_dir: str,
        system_prompt: str = "",
        tool_servers: List[str] = [],
        skill_registry: Optional[SkillRegistry] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_iterations: int = 5,
        title_provider: Optional[Provider] = None,
        title_model_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        connector_name: Optional[str] = None,
        workspace_config=None,
        workspace_service: Optional[WorkspaceService] = None,
    ):
        super().__init__(
            chat_id=chat_id,
            db=db,
            provider=provider,
            tool_manager=tool_manager,
            model_id=model_id,
            data_dir=data_dir,
            system_prompt=system_prompt,
            tool_servers=tool_servers,
            skill_registry=skill_registry,
            temperature=temperature,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            title_provider=title_provider,
            title_model_id=title_model_id,
            workspace_id=workspace_id,
            connector_name=connector_name,
            workspace_config=workspace_config,
            workspace_service=workspace_service,
        )

    async def _get_iteration_context(
        self, message: str
    ) -> List[ChatCompletionMessageParam]:
        messages = await super()._get_iteration_context(message)

        if self.workspace_id and self._workspace_service:
            try:
                files = self._workspace_service.list_files_flat(self.workspace_id)
                tree_string = format_file_tree(files)
                
                context_msg = {
                    "role": "system",
                    "content": f"Current Workspace Structure:\n{tree_string}",
                }
                
                # Insert after system prompt (index 0) if it exists, otherwise at the start
                if messages and messages[0].get("role") == "system":
                    messages.insert(1, context_msg)
                else:
                    messages.insert(0, context_msg)
            except Exception as e:
                logger.warning(f"Failed to fetch workspace tree for context: {e}")

        return messages


class WorkspaceAgentPlugin(WorkspaceAgent):
    """Base class for Workspace agent plugins."""

    default: bool = False
    name: str = ""
    provider_id: str = ""
    model_id: str = ""
    system_prompt: str = ""
    tool_servers: List[str] = []
    max_iterations: int = 5
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def post_init(self) -> None:
        """Called after all dependencies are injected."""
        pass
