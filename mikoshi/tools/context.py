import asyncio
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Union

from mikoshi.providers.provider import Provider


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: str
    data_dir: str
    connector: str | None
    git_user_name: str
    git_user_email: str

    @property
    def root(self) -> str:
        """Absolute path of the workspace directory on disk."""
        return os.path.realpath(
            os.path.join(self.data_dir, "workspaces", self.workspace_id)
        )


ApprovalCallback = Callable[[str, str, dict], Awaitable[Optional[str]]]

# (filename, content_or_path, content_type) -> file_id. A str content is
# stored as text; an os.PathLike is treated as an on-disk file and copied.
FileSaveCallback = Callable[[str, Union[bytes, str, os.PathLike], Optional[str]], str]


@dataclass(frozen=True)
class ToolCallContext:
    provider: Provider
    model_id: str
    chat_id: str
    workspace: Optional[WorkspaceContext] = None
    message_id: Optional[str] = None
    on_approval_requested: Optional[ApprovalCallback] = None
    save_file: Optional[FileSaveCallback] = None
    # The agent's SSE queue; lets a tool stream sub-agent events to the UI.
    stream_queue: Optional[asyncio.Queue] = None
    # Servers already expanded into the LLM tool array for this chat; lets the
    # discovery toolset compute its catalog as "everything else".
    upfront_tool_servers: Optional[List[str]] = None
