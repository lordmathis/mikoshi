import pytest

from mikoshi.agents.context.skills import (
    apply_skill_context,
    build_skill_context,
    parse_mentions,
)


class TestParseMentions:
    def test_single_mention(self):
        assert parse_mentions("hello @world") == ["world"]

    def test_multiple_mentions(self):
        assert parse_mentions("@foo and @bar") == ["foo", "bar"]

    def test_no_mentions(self):
        assert parse_mentions("hello world") == []

    def test_adjacent_mentions(self):
        assert parse_mentions("@foo@bar") == ["foo", "bar"]

    def test_mention_with_numbers(self):
        assert parse_mentions("@tool123") == ["tool123"]

    def test_mention_with_underscores(self):
        assert parse_mentions("@my_tool") == ["my_tool"]

    def test_hyphen_not_matched(self):
        assert parse_mentions("@my-tool") == ["my"]

    def test_email_not_matched(self):
        assert parse_mentions("user@example.com") == ["example"]

    def test_empty_string(self):
        assert parse_mentions("") == []


class TestBuildSkillContext:
    def test_empty_names_returns_empty(self):
        ctx, servers = build_skill_context([], None)
        assert ctx == ""
        assert servers == []

    def test_none_registry_returns_empty(self):
        ctx, servers = build_skill_context(["foo"], None)
        assert ctx == ""
        assert servers == []

    def test_skill_not_found_returns_empty(self):
        class FakeRegistry:
            def get_skill(self, name):
                return None

        ctx, servers = build_skill_context(["missing"], FakeRegistry())
        assert ctx == ""
        assert servers == []

    def test_found_skill_returns_content(self):
        class FakeSkill:
            def read_content(self):
                return "skill instructions here"
            def get_required_tool_servers(self):
                return []

        class FakeRegistry:
            def get_skill(self, name):
                if name == "mytool":
                    return FakeSkill()
                return None

        ctx, servers = build_skill_context(["mytool"], FakeRegistry())
        assert "mytool" in ctx
        assert "skill instructions here" in ctx
        assert servers == []

    def test_skill_with_required_tools(self):
        class FakeSkill:
            def read_content(self):
                return "content"
            def get_required_tool_servers(self):
                return ["mcp-server-1", "mcp-server-2"]

        class FakeRegistry:
            def get_skill(self, name):
                return FakeSkill()

        _, servers = build_skill_context(["x"], FakeRegistry())
        assert servers == ["mcp-server-1", "mcp-server-2"]

    def test_multiple_skills_collected(self):
        class FakeSkill:
            def __init__(self, content):
                self._content = content
            def read_content(self):
                return self._content
            def get_required_tool_servers(self):
                return []

        class FakeRegistry:
            def get_skill(self, name):
                return FakeSkill(f"content for {name}")

        ctx, _ = build_skill_context(["a", "b"], FakeRegistry())
        assert "content for a" in ctx
        assert "content for b" in ctx

    def test_mixed_found_and_not_found(self):
        class FakeSkill:
            def read_content(self):
                return "ok"
            def get_required_tool_servers(self):
                return []

        class FakeRegistry:
            def get_skill(self, name):
                if name == "exists":
                    return FakeSkill()
                return None

        ctx, _ = build_skill_context(["exists", "missing"], FakeRegistry())
        assert "exists" in ctx
        assert "missing" not in ctx

    def test_skill_read_error_returns_empty(self):
        class FakeSkill:
            def read_content(self):
                raise RuntimeError("disk error")
            def get_required_tool_servers(self):
                return []

        class FakeRegistry:
            def get_skill(self, name):
                return FakeSkill()

        ctx, servers = build_skill_context(["bad"], FakeRegistry())
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
