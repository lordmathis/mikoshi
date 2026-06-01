import pytest

from mikoshi.agents.context.skills import (
    apply_skill_context,
    build_skill_context,
    parse_mentions,
)
from tests.conftest import FakeRegistry, FakeSkill


class TestParseMentions:
    @pytest.mark.parametrize("text,expected", [
        ("hello /world", ["world"]),
        ("/foo and /bar", ["foo", "bar"]),
        ("hello world", []),
        ("/foo/bar", ["foo", "bar"]),
        ("/my-tool", ["my-tool"]),
        ("user/example.com", ["example"]),
    ])
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
