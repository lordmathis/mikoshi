import json
import os
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from mikoshi.db.migrations import run_migrations
from mikoshi.db.models import (
    Base,
    Chat,
    ChatState,
    File,
    Message,
    PendingToolApproval,
    Workspace,
)


class Database:
    def __init__(self, db_path: str):
        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Enable foreign keys and WAL mode
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("PRAGMA journal_mode = WAL"))
            conn.commit()

        # Create tables
        Base.metadata.create_all(self.engine)

        # Run migrations
        run_migrations(self.engine)

    def create_chat(
        self, title: Optional[str] = None, workspace_id: Optional[str] = None
    ) -> Chat:
        with self.SessionLocal() as session:
            chat = Chat(id=str(uuid.uuid4()), title=title, workspace_id=workspace_id)
            session.add(chat)
            session.commit()
            session.refresh(chat)
            return chat

    def save_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        reasoning_content: Optional[str] = None,
        tool_calls: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        file_ids: Optional[str] = None,
    ) -> Message:
        with self.SessionLocal() as session:
            # Get next sequence number for this chat
            stmt = select(func.coalesce(func.max(Message.sequence), 0) + 1).where(
                Message.chat_id == chat_id
            )
            next_sequence = session.execute(stmt).scalar()

            message = Message(
                id=str(uuid.uuid4()),
                chat_id=chat_id,
                sequence=next_sequence,
                role=role,
                content=content,
                reasoning_content=reasoning_content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                file_ids=file_ids,
            )
            session.add(message)

            # Update chat's updated_at
            chat = session.get(Chat, chat_id)
            if chat:
                chat.updated_at = datetime.now(UTC)

            session.commit()
            session.refresh(message)
            return message

    def get_chat_history(self, chat_id: str) -> List[Message]:
        with self.SessionLocal() as session:
            stmt = (
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.sequence)
            )
            result = session.execute(stmt)
            return list(result.scalars().all())

    def get_messages_from_sequence(
        self, chat_id: str, from_sequence: int
    ) -> List[Message]:
        """Get messages starting from a specific sequence number"""
        with self.SessionLocal() as session:
            stmt = (
                select(Message)
                .where(Message.chat_id == chat_id, Message.sequence >= from_sequence)
                .order_by(Message.sequence)
            )
            result = session.execute(stmt)
            return list(result.scalars().all())

    def get_chat(self, chat_id: str) -> Optional[Chat]:
        with self.SessionLocal() as session:
            return session.get(Chat, chat_id)

    def list_chats(self, limit: int = 20) -> List[Chat]:
        with self.SessionLocal() as session:
            stmt = select(Chat).order_by(Chat.updated_at.desc()).limit(limit)
            result = session.execute(stmt)
            return list(result.scalars().all())

    def delete_chat(self, chat_id: str):
        with self.SessionLocal() as session:
            chat = session.get(Chat, chat_id)
            if chat:
                session.delete(chat)
                session.commit()

    def update_chat(self, chat_id: str, **kwargs) -> Optional[Chat]:
        """Update chat metadata and configuration"""
        with self.SessionLocal() as session:
            chat = session.get(Chat, chat_id)
            if not chat:
                return None

            for key, value in kwargs.items():
                if hasattr(chat, key):
                    setattr(chat, key, value)

            chat.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(chat)
            return chat

    def save_chat_config(
        self,
        chat_id: str,
        model: str,
        system_prompt: Optional[str] = None,
        tool_servers: Optional[List[str]] = None,
        model_params: Optional[Dict] = None,
    ) -> Optional[Chat]:
        """Save chat configuration for restoration"""
        with self.SessionLocal() as session:
            chat = session.get(Chat, chat_id)
            if not chat:
                return None

            chat.model = model
            chat.system_prompt = system_prompt
            chat.tool_servers = (
                json.dumps(tool_servers) if tool_servers is not None else None
            )
            chat.model_params = (
                json.dumps(model_params) if model_params is not None else None
            )
            chat.updated_at = datetime.now(UTC)

            session.commit()
            session.refresh(chat)
            return chat

    def get_chat_config(self, chat_id: str) -> Optional[Dict]:
        """Get chat configuration"""
        with self.SessionLocal() as session:
            chat = session.get(Chat, chat_id)
            if not chat:
                return None

            return {
                "model": chat.model,
                "system_prompt": chat.system_prompt,
                "tool_servers": json.loads(chat.tool_servers)
                if chat.tool_servers
                else [],
                "model_params": json.loads(chat.model_params)
                if chat.model_params
                else None,
            }

    def get_chat_state(self, chat_id: str) -> Dict:
        with self.SessionLocal() as session:
            state = session.get(ChatState, chat_id)
            if not state:
                return {}
            return json.loads(state.state_json) if state.state_json else {}

    def update_chat_state(self, chat_id: str, state: Dict):
        with self.SessionLocal() as session:
            existing = session.get(ChatState, chat_id)
            if existing:
                existing.state_json = json.dumps(state)
                existing.updated_at = datetime.now(UTC)
            else:
                existing = ChatState(
                    chat_id=chat_id,
                    state_json=json.dumps(state),
                )
                session.add(existing)
            session.commit()

    def close(self):
        """Close database connections and dispose of the engine"""
        self.engine.dispose()

    def get_last_assistant_message(self, chat_id: str) -> Optional[Message]:
        """Get the last assistant message in a chat"""
        with self.SessionLocal() as session:
            stmt = (
                select(Message)
                .where(Message.chat_id == chat_id, Message.role == "assistant")
                .order_by(Message.sequence.desc())
                .limit(1)
            )
            result = session.execute(stmt)
            return result.scalars().first()

    def delete_message(self, message_id: str) -> bool:
        """Delete a message"""
        with self.SessionLocal() as session:
            message = session.get(Message, message_id)
            if not message:
                return False

            # Delete message
            session.delete(message)

            # Update chat's updated_at
            chat = session.get(Chat, message.chat_id)
            if chat:
                chat.updated_at = datetime.now(UTC)

            session.commit()
            return True

    def branch_chat(
        self,
        source_chat_id: str,
        up_to_message_id: str,
        new_title: Optional[str] = None,
    ) -> Optional[Chat]:
        with self.SessionLocal() as session:
            # Get source chat
            source_chat = session.get(Chat, source_chat_id)
            if not source_chat:
                return None

            # Get the target message to find its sequence number
            target_message = session.get(Message, up_to_message_id)
            if not target_message or target_message.chat_id != source_chat_id:
                return None

            target_sequence = target_message.sequence

            # Create new chat with same config
            new_chat = Chat(
                id=str(uuid.uuid4()),
                title=new_title or "Untitled Chat",
                model=source_chat.model,
                system_prompt=source_chat.system_prompt,
                tool_servers=source_chat.tool_servers,
                model_params=source_chat.model_params,
                workspace_id=source_chat.workspace_id,
            )
            session.add(new_chat)
            session.flush()  # Get the new chat ID

            # Get messages up to and including target sequence
            stmt = (
                select(Message)
                .where(
                    Message.chat_id == source_chat_id,
                    Message.sequence <= target_sequence,
                )
                .order_by(Message.sequence)
            )
            messages_to_copy = session.execute(stmt).scalars().all()

            # Copy messages
            for old_message in messages_to_copy:
                new_message = Message(
                    id=str(uuid.uuid4()),
                    chat_id=new_chat.id,
                    sequence=old_message.sequence,
                    role=old_message.role,
                    content=old_message.content,
                    reasoning_content=old_message.reasoning_content,
                    tool_calls=old_message.tool_calls,
                    tool_call_id=old_message.tool_call_id,
                    file_ids=old_message.file_ids,
                    status=old_message.status,
                )
                session.add(new_message)

            session.commit()
            session.refresh(new_chat)
            return new_chat

    def create_file(
        self,
        filename: str,
        file_path: str,
        content_type: str,
        file_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> File:
        with self.SessionLocal() as session:
            file_obj = File(
                id=file_id or str(uuid.uuid4()),
                filename=filename,
                file_path=file_path,
                content_type=content_type,
                source=source,
                status="pending",
            )
            session.add(file_obj)
            session.commit()
            session.refresh(file_obj)
            return file_obj

    def get_file(self, file_id: str) -> Optional[File]:
        with self.SessionLocal() as session:
            return session.get(File, file_id)

    def get_files(self, file_ids: List[str]) -> Dict[str, File]:
        with self.SessionLocal() as session:
            if not file_ids:
                return {}
            stmt = select(File).where(File.id.in_(file_ids))
            result = session.execute(stmt)
            return {f.id: f for f in result.scalars().all()}

    def list_pending_files(self) -> List[File]:
        with self.SessionLocal() as session:
            stmt = select(File).where(File.status == "pending")
            result = session.execute(stmt)
            return list(result.scalars().all())

    def attach_files(self, file_ids: List[str]):
        if not file_ids:
            return
        with self.SessionLocal() as session:
            stmt = select(File).where(File.id.in_(file_ids))
            files = session.execute(stmt).scalars().all()
            for f in files:
                f.status = "attached"
            session.commit()

    def delete_file(self, file_id: str):
        with self.SessionLocal() as session:
            file_obj = session.get(File, file_id)
            if file_obj:
                session.delete(file_obj)
                session.commit()

    # Tool Approval Methods

    def create_pending_approval(
        self,
        chat_id: str,
        message_id: Optional[str],
        tool_name: str,
        arguments: str,
        approval_id: Optional[str] = None,
    ) -> str:
        """Create a pending tool approval record. Returns approval_id."""
        with self.SessionLocal() as session:
            approval = PendingToolApproval(
                id=approval_id or str(uuid.uuid4()),
                chat_id=chat_id,
                message_id=message_id,
                tool_name=tool_name,
                arguments=arguments,
                status="pending",
            )
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval.id

    def get_pending_approvals(self, chat_id: str) -> List[Dict]:
        """Get all pending approvals for a chat"""
        with self.SessionLocal() as session:
            stmt = (
                select(PendingToolApproval)
                .where(
                    PendingToolApproval.chat_id == chat_id,
                    PendingToolApproval.status == "pending",
                )
                .order_by(PendingToolApproval.created_at)
            )
            result = session.execute(stmt)
            approvals = result.scalars().all()
            return [
                {
                    "id": a.id,
                    "chat_id": a.chat_id,
                    "message_id": a.message_id,
                    "tool_name": a.tool_name,
                    "arguments": a.arguments,
                    "status": a.status,
                    "created_at": a.created_at,
                }
                for a in approvals
            ]

    def get_approval_by_id(self, approval_id: str) -> Optional[Dict]:
        """Get a single approval record by ID"""
        with self.SessionLocal() as session:
            approval = session.get(PendingToolApproval, approval_id)
            if not approval:
                return None
            return {
                "id": approval.id,
                "chat_id": approval.chat_id,
                "message_id": approval.message_id,
                "tool_name": approval.tool_name,
                "arguments": approval.arguments,
                "status": approval.status,
                "created_at": approval.created_at,
            }

    def update_approval_status(self, approval_id: str, status: str):
        """Update approval status to 'approved' or 'denied'"""
        with self.SessionLocal() as session:
            approval = session.get(PendingToolApproval, approval_id)
            if approval:
                approval.status = status
                session.commit()

    def update_message_status(self, message_id: str, status: str):
        """Update message status column"""
        with self.SessionLocal() as session:
            message = session.get(Message, message_id)
            if message:
                message.status = status
                session.commit()

    def update_message_content(self, message_id: str, content: str):
        """Update message content"""
        with self.SessionLocal() as session:
            message = session.get(Message, message_id)
            if message:
                message.content = content
                session.commit()

    def delete_orphan_files(self, retention_hours: int = 24) -> List[str]:
        """Delete pending files older than retention_hours.

        Returns list of deleted file IDs. Caller is responsible for removing from disk.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
        with self.SessionLocal() as session:
            stmt = select(File).where(
                File.status == "pending", File.created_at < cutoff
            )
            orphans = session.execute(stmt).scalars().all()
            ids = [f.id for f in orphans]
            for f in orphans:
                session.delete(f)
            session.commit()
        return ids

    def create_workspace(
        self, name: str, repo_url: str, connector: Optional[str] = None
    ) -> Workspace:
        with self.SessionLocal() as session:
            workspace = Workspace(
                id=str(uuid.uuid4()), name=name, repo_url=repo_url, connector=connector
            )
            session.add(workspace)
            session.commit()
            session.refresh(workspace)
            return workspace

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        with self.SessionLocal() as session:
            return session.get(Workspace, workspace_id)

    def list_workspaces(self) -> List[Workspace]:
        with self.SessionLocal() as session:
            stmt = select(Workspace).order_by(Workspace.updated_at.desc())
            result = session.execute(stmt)
            return list(result.scalars().all())

    def delete_workspace(self, workspace_id: str):
        with self.SessionLocal() as session:
            workspace = session.get(Workspace, workspace_id)
            if workspace:
                session.delete(workspace)
                session.commit()

    def get_workspace_by_chat(self, chat_id: str) -> Optional[Workspace]:
        with self.SessionLocal() as session:
            chat = session.get(Chat, chat_id)
            if not chat or not chat.workspace_id:
                return None
            return session.get(Workspace, chat.workspace_id)
