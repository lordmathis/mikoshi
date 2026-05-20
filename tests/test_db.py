import json
from datetime import UTC, datetime, timedelta

import pytest

from mikoshi.db.models import (
    Chat,
    ChatState,
    File,
    Message,
    PendingToolApproval,
    Workspace,
)


class TestChatCRUD:
    def test_create_chat_with_title(self, db):
        chat = db.create_chat(title="My Chat")
        assert chat.title == "My Chat"

    def test_get_chat(self, db):
        created = db.create_chat(title="Find Me")
        found = db.get_chat(created.id)
        assert found is not None
        assert found.title == "Find Me"

    def test_get_chat_not_found(self, db):
        assert db.get_chat("nonexistent") is None

    def test_list_chats_ordered_by_updated(self, db):
        first = db.create_chat(title="First")
        second = db.create_chat(title="Second")
        from sqlalchemy import text as sql_text

        with db.engine.connect() as conn:
            conn.execute(
                sql_text(
                    "UPDATE chats SET updated_at = datetime('now', '-1 hour') WHERE id = :id"
                ),
                {"id": first.id},
            )
            conn.commit()
        chats = db.list_chats()
        assert len(chats) == 2
        assert chats[0].id == second.id
        assert chats[1].id == first.id

    def test_list_chats_respects_limit(self, db):
        for i in range(5):
            db.create_chat(title=f"Chat {i}")
        chats = db.list_chats(limit=3)
        assert len(chats) == 3

    def test_delete_chat(self, db):
        chat = db.create_chat()
        db.delete_chat(chat.id)
        assert db.get_chat(chat.id) is None

    def test_update_chat(self, db):
        chat = db.create_chat(title="Old")
        updated = db.update_chat(chat.id, title="New")
        assert updated.title == "New"
        assert db.get_chat(chat.id).title == "New"

    def test_update_chat_refreshes_timestamp(self, db):
        chat = db.create_chat()
        old_ts = chat.updated_at
        updated = db.update_chat(chat.id, title="Changed")
        assert updated.updated_at >= old_ts


class TestChatConfig:
    def test_save_and_get_config(self, db):
        chat = db.create_chat()
        db.save_chat_config(
            chat.id,
            model="gpt-4",
            system_prompt="You are helpful",
            tool_servers=["server1", "server2"],
            model_params={"temperature": 0.7},
        )
        config = db.get_chat_config(chat.id)
        assert config["model"] == "gpt-4"
        assert config["system_prompt"] == "You are helpful"
        assert config["tool_servers"] == ["server1", "server2"]
        assert config["model_params"] == {"temperature": 0.7}

    def test_get_config_defaults(self, db):
        chat = db.create_chat()
        config = db.get_chat_config(chat.id)
        assert config["model"] is None
        assert config["system_prompt"] is None
        assert config["tool_servers"] == []
        assert config["model_params"] is None

    def test_save_config_not_found(self, db):
        assert db.save_chat_config("nonexistent", model="x") is None


class TestChatState:
    def test_get_state_empty_when_none(self, db):
        chat = db.create_chat()
        assert db.get_chat_state(chat.id) == {}

    def test_update_and_get_state(self, db):
        chat = db.create_chat()
        db.update_chat_state(chat.id, {"key": "value", "count": 42})
        state = db.get_chat_state(chat.id)
        assert state == {"key": "value", "count": 42}

    def test_update_state_overwrites(self, db):
        chat = db.create_chat()
        db.update_chat_state(chat.id, {"a": 1})
        db.update_chat_state(chat.id, {"b": 2})
        assert db.get_chat_state(chat.id) == {"b": 2}


class TestMessages:
    def test_save_message_assigns_sequence(self, db):
        chat = db.create_chat()
        m1 = db.save_message(chat.id, "user", "Hello")
        m2 = db.save_message(chat.id, "assistant", "Hi")
        assert m1.sequence == 1
        assert m2.sequence == 2

    def test_save_message_with_optional_fields(self, db):
        chat = db.create_chat()
        msg = db.save_message(
            chat.id,
            "assistant",
            "result",
            reasoning_content="thinking...",
            tool_calls='[{"id": "tc1"}]',
            tool_call_id="tc1",
            file_ids='["f1"]',
        )
        assert msg.reasoning_content == "thinking..."
        assert msg.tool_calls == '[{"id": "tc1"}]'
        assert msg.tool_call_id == "tc1"
        assert msg.file_ids == '["f1"]'

    def test_get_chat_history_ordered(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "First")
        db.save_message(chat.id, "assistant", "Second")
        db.save_message(chat.id, "user", "Third")
        history = db.get_chat_history(chat.id)
        assert [m.content for m in history] == ["First", "Second", "Third"]

    def test_get_chat_history_empty(self, db):
        chat = db.create_chat()
        assert db.get_chat_history(chat.id) == []

    def test_get_messages_from_sequence(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "A")
        db.save_message(chat.id, "assistant", "B")
        db.save_message(chat.id, "user", "C")
        msgs = db.get_messages_from_sequence(chat.id, 2)
        assert len(msgs) == 2
        assert msgs[0].content == "B"
        assert msgs[1].content == "C"

    def test_get_last_assistant_message(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "Q")
        db.save_message(chat.id, "assistant", "A1")
        db.save_message(chat.id, "user", "Q2")
        db.save_message(chat.id, "assistant", "A2")
        last = db.get_last_assistant_message(chat.id)
        assert last.content == "A2"

    def test_get_last_assistant_message_none(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "Hello")
        assert db.get_last_assistant_message(chat.id) is None

    def test_delete_message(self, db):
        chat = db.create_chat()
        msg = db.save_message(chat.id, "user", "Delete me")
        assert db.delete_message(msg.id) is True
        assert len(db.get_chat_history(chat.id)) == 0

    def test_delete_messages_after(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "Keep")
        db.save_message(chat.id, "assistant", "Keep too")
        db.save_message(chat.id, "user", "Remove me")
        db.delete_messages_after(chat.id, 3)
        history = db.get_chat_history(chat.id)
        assert len(history) == 2
        assert history[-1].content == "Keep too"

    def test_update_message_status(self, db):
        chat = db.create_chat()
        msg = db.save_message(chat.id, "assistant", "ok")
        db.update_message_status(msg.id, "awaiting_tool_approval")
        updated = db.get_chat_history(chat.id)[0]
        assert updated.status == "awaiting_tool_approval"

    def test_update_message_content(self, db):
        chat = db.create_chat()
        msg = db.save_message(chat.id, "user", "old")
        db.update_message_content(msg.id, "new")
        assert db.get_chat_history(chat.id)[0].content == "new"


class TestBranch:
    def test_branch_copies_messages_up_to_target(self, db):
        chat = db.create_chat()
        m1 = db.save_message(chat.id, "user", "A")
        m2 = db.save_message(chat.id, "assistant", "B")
        m3 = db.save_message(chat.id, "user", "C")
        db.save_message(chat.id, "assistant", "D")

        branched = db.branch_chat(chat.id, m2.id, new_title="Branched")
        assert branched is not None
        assert branched.title == "Branched"
        assert branched.id != chat.id

        history = db.get_chat_history(branched.id)
        assert len(history) == 2
        assert history[0].content == "A"
        assert history[1].content == "B"
        for orig, copy in zip(
            db.get_chat_history(chat.id)[:2], history
        ):
            assert copy.role == orig.role
            assert copy.sequence == orig.sequence

    def test_branch_preserves_config(self, db):
        chat = db.create_chat()
        db.save_chat_config(chat.id, model="gpt-4", system_prompt="sys")
        db.save_message(chat.id, "user", "hi")
        m2 = db.save_message(chat.id, "assistant", "hey")

        branched = db.branch_chat(chat.id, m2.id)
        config = db.get_chat_config(branched.id)
        assert config["model"] == "gpt-4"
        assert config["system_prompt"] == "sys"

    def test_branch_new_message_ids(self, db):
        chat = db.create_chat()
        m1 = db.save_message(chat.id, "user", "hi")
        branched = db.branch_chat(chat.id, m1.id)
        branched_msg = db.get_chat_history(branched.id)[0]
        assert branched_msg.id != m1.id

    def test_branch_chat_not_found(self, db):
        assert db.branch_chat("nonexistent", "msg") is None

    def test_branch_message_not_found(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "hi")
        assert db.branch_chat(chat.id, "nonexistent") is None

    def test_branch_message_wrong_chat(self, db):
        chat1 = db.create_chat()
        chat2 = db.create_chat()
        m1 = db.save_message(chat1.id, "user", "hi")
        m2 = db.save_message(chat2.id, "user", "yo")
        assert db.branch_chat(chat1.id, m2.id) is None



class TestFileLifecycle:
    def test_create_file_and_get(self, db):
        f = db.create_file("test.txt", "/tmp/test.txt", "text/plain")
        assert f.id
        assert f.status == "pending"
        assert f.filename == "test.txt"
        found = db.get_file(f.id)
        assert found.filename == "test.txt"

    def test_create_file_with_id(self, db):
        f = db.create_file("a.txt", "/a", "text/plain", file_id="custom-id")
        assert f.id == "custom-id"

    def test_get_files_batch(self, db):
        f1 = db.create_file("a.txt", "/a", "text/plain")
        f2 = db.create_file("b.txt", "/b", "text/plain")
        result = db.get_files([f1.id, f2.id, "nonexistent"])
        assert len(result) == 2
        assert f1.id in result
        assert f2.id in result

    def test_list_pending_files(self, db):
        db.create_file("a.txt", "/a", "text/plain")
        db.create_file("b.txt", "/b", "text/plain")
        pending = db.list_pending_files()
        assert len(pending) == 2

    def test_attach_files(self, db):
        f = db.create_file("a.txt", "/a", "text/plain")
        db.attach_files([f.id])
        assert db.get_file(f.id).status == "attached"
        assert len(db.list_pending_files()) == 0

    def test_delete_file(self, db):
        f = db.create_file("a.txt", "/a", "text/plain")
        db.delete_file(f.id)
        assert db.get_file(f.id) is None

    def test_delete_orphan_files(self, db):
        old = db.create_file("old.txt", "/old", "text/plain", source="upload")
        recent = db.create_file("new.txt", "/new", "text/plain")
        attached = db.create_file("att.txt", "/att", "text/plain")
        db.attach_files([attached.id])

        from sqlalchemy import text as sql_text

        with db.engine.connect() as conn:
            conn.execute(
                sql_text(
                    "UPDATE files SET created_at = datetime('now', '-48 hours') WHERE id = :id"
                ),
                {"id": old.id},
            )
            conn.commit()

        deleted = db.delete_orphan_files(retention_hours=24)
        assert old.id in deleted
        assert recent.id not in deleted
        assert attached.id not in deleted
        assert db.get_file(old.id) is None
        assert db.get_file(recent.id) is not None


class TestApprovalWorkflow:
    def test_create_pending_approval(self, db):
        chat = db.create_chat()
        aid = db.create_pending_approval(
            chat.id, None, "run_code", '{"cmd": "ls"}'
        )
        assert aid

    def test_create_approval_custom_id(self, db):
        chat = db.create_chat()
        aid = db.create_pending_approval(
            chat.id, None, "tool", "{}", approval_id="custom-id"
        )
        assert aid == "custom-id"

    def test_get_pending_approvals(self, db):
        chat = db.create_chat()
        db.create_pending_approval(chat.id, None, "tool_a", "{}")
        db.create_pending_approval(chat.id, None, "tool_b", "{}")
        approvals = db.get_pending_approvals(chat.id)
        assert len(approvals) == 2
        assert approvals[0]["status"] == "pending"

    def test_get_pending_approvals_excludes_resolved(self, db):
        chat = db.create_chat()
        aid = db.create_pending_approval(chat.id, None, "tool", "{}")
        db.update_approval_status(aid, "approved")
        assert db.get_pending_approvals(chat.id) == []

    def test_get_approval_by_id(self, db):
        chat = db.create_chat()
        aid = db.create_pending_approval(
            chat.id, "msg-1", "run_code", '{"cmd": "ls"}'
        )
        approval = db.get_approval_by_id(aid)
        assert approval["tool_name"] == "run_code"
        assert approval["arguments"] == '{"cmd": "ls"}'
        assert approval["message_id"] == "msg-1"

    @pytest.mark.parametrize("status", ["approved", "denied"])
    def test_update_approval_status(self, db, status):
        chat = db.create_chat()
        aid = db.create_pending_approval(chat.id, None, "tool", "{}")
        db.update_approval_status(aid, status)
        assert db.get_approval_by_id(aid)["status"] == status


class TestWorkspaceCRUD:
    def test_create_workspace_and_get(self, db):
        ws = db.create_workspace("proj", "https://github.com/x/proj")
        assert ws.id
        assert ws.name == "proj"
        assert ws.repo_url == "https://github.com/x/proj"
        assert ws.connector is None
        found = db.get_workspace(ws.id)
        assert found.name == "proj"

    def test_create_workspace_with_connector(self, db):
        ws = db.create_workspace("proj", "https://git.example.com/x", connector="forgejo")
        assert ws.connector == "forgejo"

    def test_list_workspaces(self, db):
        db.create_workspace("a", "https://a.com")
        db.create_workspace("b", "https://b.com")
        wss = db.list_workspaces()
        assert len(wss) == 2

    def test_delete_workspace(self, db):
        ws = db.create_workspace("proj", "https://github.com/x/proj")
        db.delete_workspace(ws.id)
        assert db.get_workspace(ws.id) is None

    def test_delete_workspace_sets_chat_workspace_null(self, db):
        ws = db.create_workspace("proj", "https://github.com/x/proj")
        chat = db.create_chat(title="Linked", workspace_id=ws.id)
        db.delete_workspace(ws.id)
        assert db.get_workspace(ws.id) is None
        updated = db.get_chat(chat.id)
        assert updated.workspace_id is None

    def test_get_workspace_by_chat(self, db):
        ws = db.create_workspace("proj", "https://github.com/x/proj")
        chat = db.create_chat(workspace_id=ws.id)
        found = db.get_workspace_by_chat(chat.id)
        assert found.id == ws.id



class TestCascadeDeletes:
    def test_delete_chat_cascades_to_messages(self, db):
        chat = db.create_chat()
        db.save_message(chat.id, "user", "hello")
        db.save_message(chat.id, "assistant", "hi")
        db.delete_chat(chat.id)
        assert db.get_chat_history(chat.id) == []

    def test_delete_chat_cascades_to_state(self, db):
        chat = db.create_chat()
        db.update_chat_state(chat.id, {"x": 1})
        db.delete_chat(chat.id)
        assert db.get_chat_state(chat.id) == {}

    def test_delete_chat_cascades_to_approvals(self, db):
        chat = db.create_chat()
        db.create_pending_approval(chat.id, None, "tool", "{}")
        db.delete_chat(chat.id)
        assert db.get_pending_approvals(chat.id) == []

    def test_delete_chats_by_workspace(self, db):
        ws = db.create_workspace("proj", "https://github.com/x/proj")
        c1 = db.create_chat(workspace_id=ws.id)
        c2 = db.create_chat(workspace_id=ws.id)
        db.save_message(c1.id, "user", "msg")
        db.delete_chats_by_workspace(ws.id)
        assert db.get_chat(c1.id) is None
        assert db.get_chat(c2.id) is None
