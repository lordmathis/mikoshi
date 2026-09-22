import json

import pytest
from unittest.mock import MagicMock

from mikoshi.agents.context.skills import (
    apply_skill_context,
    build_skill_context,
    parse_mentions,
)
from mikoshi.agents.react import ReActAgent
from tests.conftest import FakeRegistry, FakeSkill


class TestParseMentions:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("hello /world", ["world"]),
            ("/foo and /bar", ["foo", "bar"]),
            ("hello world", []),
            ("/foo/bar", ["foo", "bar"]),
            ("/my-tool", ["my-tool"]),
            ("user/example.com", ["example"]),
        ],
    )
    def test_parse_mentions(self, text, expected):
        assert parse_mentions(text) == expected


class TestBuildSkillContext:
    def test_empty_or_missing_returns_empty(self):
        for ctx, servers in [
            build_skill_context([], None),
            build_skill_context(["foo"], None),
        ]:
            assert ctx == ""
            assert servers == []

    def test_skill_not_found_returns_empty(self):
        ctx, servers = build_skill_context(["missing"], FakeRegistry())
        assert ctx == ""
        assert servers == []

    def test_found_skill_returns_content(self):
        registry = FakeRegistry(
            skills={"mytool": FakeSkill(content="skill instructions here")}
        )
        ctx, servers = build_skill_context(["mytool"], registry)
        assert "mytool" in ctx
        assert "skill instructions here" in ctx
        assert servers == []

    def test_skill_with_required_tools(self):
        registry = FakeRegistry(
            default_skill=FakeSkill(
                content="content", tool_servers=["mcp-server-1", "mcp-server-2"]
            )
        )
        _, servers = build_skill_context(["x"], registry)
        assert servers == ["mcp-server-1", "mcp-server-2"]

    def test_multiple_skills_collected(self):
        registry = FakeRegistry(
            default_skill=None,
        )
        registry.get_skill = lambda name: FakeSkill(content=f"content for {name}")
        ctx, _ = build_skill_context(["a", "b"], registry)
        assert "content for a" in ctx
        assert "content for b" in ctx

    def test_mixed_found_and_not_found(self):
        registry = FakeRegistry(skills={"exists": FakeSkill()})
        ctx, _ = build_skill_context(["exists", "missing"], registry)
        assert "exists" in ctx
        assert "missing" not in ctx

    def test_skill_read_error_returns_empty(self):
        registry = FakeRegistry(
            default_skill=FakeSkill(read_error=RuntimeError("disk error"))
        )
        ctx, servers = build_skill_context(["bad"], registry)
        assert ctx == ""
        assert servers == []


class TestApplySkillContext:
    def test_empty_context_returns_unchanged(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = apply_skill_context(msgs, "")
        assert result == msgs

    def test_appends_to_existing_system_prompt(self):
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        result = apply_skill_context(msgs, "\nSkill context")
        assert result[0]["content"] == "You are helpful.\nSkill context"

    def test_prepends_system_if_none_exists(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = apply_skill_context(msgs, "skill context")
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "skill context"
        assert result[1]["role"] == "user"

    def test_developer_role_treated_as_system(self):
        msgs = [
            {"role": "developer", "content": "instructions"},
        ]
        result = apply_skill_context(msgs, " extra")
        assert result[0]["content"] == "instructions extra"


class _FakeProvider:
    def get_llm_client(self):
        return MagicMock()


class TestBuildContextOrdering:
    """Regression: a /skill mention on the first message must not drop the
    configured system prompt."""

    @pytest.mark.asyncio
    async def test_skill_mention_keeps_persona_system_prompt(self, db):
        chat = db.create_chat()
        agent = ReActAgent(
            chat_id=chat.id,
            db=db,
            provider=_FakeProvider(),
            tool_manager=MagicMock(),
            model_id="m",
            data_dir="/tmp",
            system_prompt="You are Mikoshi.",
            skill_registry=FakeRegistry(
                skills={"foo": FakeSkill(content="Foo skill instructions.")}
            ),
        )
        db.save_message(chat.id, "user", "/foo do X")

        messages = await agent._build_context("/foo do X")

        assert messages[0]["role"] == "system"
        assert messages[0]["content"].startswith("You are Mikoshi.")
        assert "Foo skill instructions." in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "/foo do X"

    @pytest.mark.asyncio
    async def test_skill_without_persona_uses_skill_as_system(self, db):
        chat = db.create_chat()
        agent = ReActAgent(
            chat_id=chat.id,
            db=db,
            provider=_FakeProvider(),
            tool_manager=MagicMock(),
            model_id="m",
            data_dir="/tmp",
            skill_registry=FakeRegistry(
                skills={"foo": FakeSkill(content="Foo skill instructions.")}
            ),
        )
        db.save_message(chat.id, "user", "/foo do X")

        messages = await agent._build_context("/foo do X")

        assert messages[0]["role"] == "system"
        assert "Foo skill instructions." in messages[0]["content"]


class TestSkillPersistence:
    """Regression: a mentioned skill must stay in the system prompt for the
    whole chat, not only the turn where it was mentioned."""

    def _make_agent(self, db, chat, registry):
        return ReActAgent(
            chat_id=chat.id,
            db=db,
            provider=_FakeProvider(),
            tool_manager=MagicMock(),
            model_id="m",
            data_dir="/tmp",
            system_prompt="You are Mikoshi.",
            skill_registry=registry,
        )

    @pytest.mark.asyncio
    async def test_followup_turn_keeps_skill(self, db):
        chat = db.create_chat()
        agent = self._make_agent(
            db,
            chat,
            FakeRegistry(skills={"foo": FakeSkill(content="Foo skill instructions.")}),
        )
        db.save_message(chat.id, "user", "/foo do X")
        await agent._build_context("/foo do X")

        db.save_message(chat.id, "assistant", "done")
        db.save_message(chat.id, "user", "now do Y")
        messages = await agent._build_context("now do Y")

        assert messages[0]["content"].startswith("You are Mikoshi.")
        assert "Foo skill instructions." in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_skill_survives_agent_rehydration(self, db):
        chat = db.create_chat()
        registry = FakeRegistry(
            skills={"foo": FakeSkill(content="Foo skill instructions.")}
        )
        agent = self._make_agent(db, chat, registry)
        db.save_message(chat.id, "user", "/foo do X")
        await agent._build_context("/foo do X")

        rehydrated = self._make_agent(db, chat, registry)
        db.save_message(chat.id, "assistant", "done")
        db.save_message(chat.id, "user", "now do Y")
        messages = await rehydrated._build_context("now do Y")

        assert "Foo skill instructions." in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_unresolvable_mention_not_persisted(self, db):
        chat = db.create_chat()
        agent = self._make_agent(db, chat, FakeRegistry(skills={"foo": FakeSkill()}))
        db.save_message(chat.id, "user", "/missing and /foo go")

        await agent._build_context("/missing and /foo go")

        assert json.loads(db.get_chat(chat.id).skills) == ["foo"]

    @pytest.mark.asyncio
    async def test_skills_accumulate_across_turns(self, db):
        chat = db.create_chat()
        registry = FakeRegistry(
            skills={
                "foo": FakeSkill(content="Foo content."),
                "bar": FakeSkill(content="Bar content."),
            }
        )
        agent = self._make_agent(db, chat, registry)
        db.save_message(chat.id, "user", "/foo go")
        await agent._build_context("/foo go")

        db.save_message(chat.id, "user", "/bar also")
        messages = await agent._build_context("/bar also")

        assert "Foo content." in messages[0]["content"]
        assert "Bar content." in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_stale_persisted_skill_pruned(self, db):
        chat = db.create_chat()
        agent = self._make_agent(
            db, chat, FakeRegistry(skills={"foo": FakeSkill(content="Foo content.")})
        )
        db.save_message(chat.id, "user", "/foo go")
        await agent._build_context("/foo go")

        successor = self._make_agent(db, chat, FakeRegistry(skills={}))
        db.save_message(chat.id, "user", "now do Y")
        messages = await successor._build_context("now do Y")

        assert "Foo content." not in messages[0]["content"]
        assert db.get_chat(chat.id).skills == json.dumps([])
