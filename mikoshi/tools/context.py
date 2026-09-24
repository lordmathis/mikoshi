import asyncio
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from mikoshi.providers import Provider


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


@dataclass(frozen=True)
class ToolCallContext:
    provider: Provider
    model_id: str
    chat_id: str
    workspace: Optional[WorkspaceContext] = None
    message_id: Optional[str] = None
    on_approval_requested: Optional[ApprovalCallback] = None
    # The agent's SSE queue; lets a tool stream sub-agent events to the UI.
    stream_queue: Optional[asyncio.Queue] = None
