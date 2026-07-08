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


ApprovalCallback = Callable[[str, str, dict], Awaitable[Optional[str]]]


@dataclass(frozen=True)
class ToolCallContext:
    provider: Provider
    model_id: str
    chat_id: str
    workspace: Optional[WorkspaceContext] = None
    message_id: Optional[str] = None
    on_approval_requested: Optional[ApprovalCallback] = None
