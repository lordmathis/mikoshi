from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    repo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    connector: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="Untitled Chat")

    # Configuration fields for storing chat settings
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_servers: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array as string
    model_params: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON object as string
    workspace_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # Order within chat
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    reasoning_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array as string
    tool_call_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_ids: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array as string
    status: Mapped[str] = mapped_column(
        String, default="completed"
    )  # completed, awaiting_tool_approval, tool_approval_denied
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("chat_id", "sequence", name="uq_chat_sequence"),
        Index("idx_chat_sequence", "chat_id", "sequence"),
    )


class File(Base):
    __tablename__ = "files"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (Index("idx_file_status", "status"),)


class ChatState(Base):
    __tablename__ = "chat_states"
    chat_id: Mapped[str] = mapped_column(
        String, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )


class PendingToolApproval(Base):
    __tablename__ = "pending_tool_approvals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    message_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tool_name: Mapped[str] = mapped_column(String)
    arguments: Mapped[str] = mapped_column(Text)  # JSON
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending, approved, denied
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC))

    __table_args__ = (
        Index("idx_chat_approvals", "chat_id"),
        Index("idx_message_approvals", "message_id"),
    )
