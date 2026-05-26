import logging
from typing import List

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.plugin_base import AgentPluginBase
from mikoshi.agents.react import ReActAgent

logger = logging.getLogger(__name__)


def format_file_tree(files: List[str]) -> str:
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
        sorted_keys = sorted(node.keys(), key=lambda k: (len(node[k]) == 0, k.lower()))
        for i, key in enumerate(sorted_keys):
            is_last = i == len(sorted_keys) - 1
            connector = "└── " if is_last else "├── "

            if node[key]:
                lines.append(f"{prefix}{connector}{key}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                _render(node[key], new_prefix)
            else:
                lines.append(f"{prefix}{connector}{key}")

    _render(tree)
    return "\n".join(lines)


class WorkspaceAgent(ReActAgent):
    """Agent specialized for workspaces with automatic tree injection."""

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

                if messages and messages[0].get("role") == "system":
                    messages.insert(1, context_msg)
                else:
                    messages.insert(0, context_msg)

                agents_md_path = next(
                    (f for f in files if f.lower() == "agents.md"), None
                )
                if agents_md_path:
                    agents_md = self._workspace_service.read_file(
                        self.workspace_id, agents_md_path
                    )
                    agents_msg = {
                        "role": "system",
                        "content": f"AGENTS.md instructions:\n{agents_md}",
                    }
                    if messages and messages[0].get("role") == "system":
                        messages.insert(1, agents_msg)
                    else:
                        messages.insert(0, agents_msg)
            except Exception as e:
                logger.warning(f"Failed to fetch workspace tree for context: {e}")

        return messages


class WorkspaceAgentPlugin(WorkspaceAgent, AgentPluginBase):
    """Base class for Workspace agent plugins."""
