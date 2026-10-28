from unittest.mock import MagicMock

import pytest

from mikoshi.config import AppConfig
from mikoshi.db import Database
from mikoshi.tools.manager import ToolManager


def _make_manager(db: Database | None) -> ToolManager:
    return ToolManager(AppConfig(), MagicMock(), db=db)


class TestSetChatTitle:
    def test_renames_untitled_chat(self, db):
        chat = db.create_chat()  # title defaults to None
        tm = _make_manager(db)

        tm.set_chat_title(chat.id, "Workout 2026-10-28")

        assert db.get_chat(chat.id).title == "Workout 2026-10-28"

    def test_noop_when_chat_has_custom_title(self, db):
        chat = db.create_chat(title="My Workout")
        tm = _make_manager(db)

        tm.set_chat_title(chat.id, "Workout 2026-10-28")

        assert db.get_chat(chat.id).title == "My Workout"

    def test_noop_on_empty_or_whitespace_title(self, db):
        chat = db.create_chat()
        tm = _make_manager(db)

        tm.set_chat_title(chat.id, "")
        tm.set_chat_title(chat.id, "   ")

        assert db.get_chat(chat.id).title in (None, "", "Untitled Chat")

    def test_noop_when_db_is_none(self):
        tm = _make_manager(None)

        # Must not raise despite the missing database.
        tm.set_chat_title("any-chat", "Workout 2026-10-28")

    def test_noop_when_chat_does_not_exist(self, db):
        tm = _make_manager(db)

        tm.set_chat_title("bogus-chat", "Workout 2026-10-28")

        assert db.get_chat("bogus-chat") is None

    def test_strips_surrounding_whitespace(self, db):
        chat = db.create_chat()
        tm = _make_manager(db)

        tm.set_chat_title(chat.id, "  Workout 2026-10-28  ")

        assert db.get_chat(chat.id).title == "Workout 2026-10-28"
