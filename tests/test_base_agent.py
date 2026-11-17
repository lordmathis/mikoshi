import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import AuthenticationError, InternalServerError, RateLimitError

from mikoshi.agents.react import ReActAgent
from tests.conftest import FakeRegistry, FakeSkill


def _response(content="ok"):
    return {"choices": [{"message": {"content": content, "role": "assistant"}}]}


class _ScriptedLLM:
    def __init__(self, failures=0, error=None, response=None):
        self.failures = failures
        self.error = error
        self.response = response or _response()
        self.calls = 0

    async def chat_completion(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return self.response


class _FakeProvider:
    def __init__(self, llm):
        self._llm = llm

    def get_llm_client(self):
        return self._llm


def _make_agent(db, chat_id, llm):
    return ReActAgent(
        chat_id=chat_id,
        db=db,
        provider=_FakeProvider(llm),
        tool_manager=MagicMock(),
        model_id="m",
        data_dir="/tmp",
        max_iterations=1,
    )


def _drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def _rate_limit(retry_after=None):
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "http://x"))
    return RateLimitError("rate limited", response=response, body=None)


def _internal_error():
    response = httpx.Response(500, request=httpx.Request("POST", "http://x"))
    return InternalServerError("boom", response=response, body=None)


class TestLLMRetries:
    @pytest.mark.asyncio
    async def test_retries_rate_limit_then_succeeds(self, db, monkeypatch):
        await monkeypatch_asyncio_sleep(monkeypatch)
        chat = db.create_chat()
        llm = _ScriptedLLM(failures=1, error=_rate_limit())
        agent = _make_agent(db, chat.id, llm)

        result = await agent._llm([{"role": "user", "content": "hi"}])

        assert result["choices"][0]["message"]["content"] == "ok"
        assert llm.calls == 2

    @pytest.mark.asyncio
    async def test_retries_internal_server_error_then_succeeds(self, db, monkeypatch):
        await monkeypatch_asyncio_sleep(monkeypatch)
        chat = db.create_chat()
        llm = _ScriptedLLM(failures=1, error=_internal_error())
        agent = _make_agent(db, chat.id, llm)

        result = await agent._llm([{"role": "user", "content": "hi"}])

        assert result == _response()
        assert llm.calls == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self, db):
        chat = db.create_chat()
        response = httpx.Response(401, request=httpx.Request("POST", "http://x"))
        llm = _ScriptedLLM(
            failures=3, error=AuthenticationError("bad key", response=response, body=None)
        )
        agent = _make_agent(db, chat.id, llm)

        with pytest.raises(AuthenticationError):
            await agent._llm([{"role": "user", "content": "hi"}])
        assert llm.calls == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raise(self, db, monkeypatch):
        await monkeypatch_asyncio_sleep(monkeypatch)
        chat = db.create_chat()
        llm = _ScriptedLLM(failures=99, error=_rate_limit())
        agent = _make_agent(db, chat.id, llm)

        with pytest.raises(RateLimitError):
            await agent._llm([{"role": "user", "content": "hi"}])
        assert llm.calls == 3

    @pytest.mark.asyncio
    async def test_retry_after_header_extends_delay(self, db, monkeypatch):
        delays = []

        async def fake_sleep(delay):
            delays.append(delay)

        monkeypatch.setattr("mikoshi.agents.base.asyncio.sleep", fake_sleep)
        chat = db.create_chat()
        llm = _ScriptedLLM(failures=1, error=_rate_limit(retry_after="7"))
        agent = _make_agent(db, chat.id, llm)

        await agent._llm([{"role": "user", "content": "hi"}])

        assert delays == [7.0]


async def monkeypatch_asyncio_sleep(monkeypatch):
    """Skip real backoff sleeps; the retry logic under test doesn't need them."""

    async def fake_sleep(delay):
        pass

    monkeypatch.setattr("mikoshi.agents.base.asyncio.sleep", fake_sleep)


class TestPrepareRetry:
    def test_keeps_unanswered_user_message(self, db):
        # Failed turn: trailing user message with no assistant reply after it.
        chat = db.create_chat()
        db.save_message(chat.id, "user", "first question")
        db.save_message(chat.id, "assistant", "first answer")
        db.save_message(chat.id, "user", "second question")
        agent = _make_agent(db, chat.id, _ScriptedLLM())

        message = agent._prepare_retry()

        assert message == "second question"
        remaining = [m.content for m in db.get_chat_history(chat.id)]
        assert remaining == ["first question", "first answer", "second question"]

    def test_deletes_last_assistant_reply(self, db):
        # Normal retry: last exchange answered, reply should be regenerated.
        chat = db.create_chat()
        db.save_message(chat.id, "user", "question")
        db.save_message(chat.id, "assistant", "bad answer")
        agent = _make_agent(db, chat.id, _ScriptedLLM())

        message = agent._prepare_retry()

        assert message == "question"
        remaining = [m.content for m in db.get_chat_history(chat.id)]
        assert remaining == ["question"]


class TestToolErrorReturnedToLLM:
    @pytest.mark.asyncio
    async def test_unknown_tool_error_appended_as_tool_message(self, db):
        chat = db.create_chat()
        agent = _make_agent(db, chat.id, _ScriptedLLM())
        agent.tool_manager.call_tool.side_effect = ValueError(
            "Tool server 'nope' not found"
        )
        messages = []
        queue = asyncio.Queue()
        tool_call = {"id": "tc1", "function": {"name": "nope__tool", "arguments": "{}"}}

        await agent._execute_tool_calls([tool_call], messages, queue)

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"
        assert messages[0]["tool_call_id"] == "tc1"
        assert "Error executing tool 'nope__tool'" in messages[0]["content"]
        assert "not found" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_tool_exception_error_appended_as_tool_message(self, db):
        chat = db.create_chat()
        agent = _make_agent(db, chat.id, _ScriptedLLM())
        agent.tool_manager.call_tool.side_effect = TimeoutError("MCP timed out")
        messages = []
        queue = asyncio.Queue()
        tool_call = {"id": "tc2", "function": {"name": "srv__slow", "arguments": "{}"}}

        await agent._execute_tool_calls([tool_call], messages, queue)

        assert messages[0]["role"] == "tool"
        assert "Error executing tool 'srv__slow'" in messages[0]["content"]
        assert "MCP timed out" in messages[0]["content"]


class TestChatTitleSkippedOnFailedTurn:
    @pytest.mark.asyncio
    async def test_failed_turn_emits_error_and_skips_title(self, db, monkeypatch):
        await monkeypatch_asyncio_sleep(monkeypatch)
        chat = db.create_chat()
        llm = _ScriptedLLM(failures=99, error=_rate_limit())
        agent = _make_agent(db, chat.id, llm)
        title_calls = []

        async def fake_generate_title(queue):
            title_calls.append(True)

        agent._generate_title = fake_generate_title
        queue = asyncio.Queue()

        await agent.chat("hello", queue)

        assert title_calls == []
        events = _drain(queue)
        assert [e.type for e in events][-2:] == ["error", "done"]

    @pytest.mark.asyncio
    async def test_successful_turn_generates_title(self, db):
        chat = db.create_chat()
        llm = _ScriptedLLM()
        agent = _make_agent(db, chat.id, llm)
        title_calls = []

        async def fake_generate_title(queue):
            title_calls.append(True)

        agent._generate_title = fake_generate_title
        queue = asyncio.Queue()

        await agent.chat("hello", queue)

        assert title_calls == [True]
        events = _drain(queue)
        assert events[-1].type == "done"

    @pytest.mark.asyncio
    async def test_successful_turn_emits_chat_renamed_before_done(self, db):
        chat = db.create_chat()
        llm = _ScriptedLLM(response=_response("Fix Login Bug"))
        agent = _make_agent(db, chat.id, llm)
        queue = asyncio.Queue()

        await agent.chat("hello", queue)

        events = _drain(queue)
        types = [e.type for e in events]
        assert "chat_renamed" in types
        assert types.index("chat_renamed") < types.index("done")
        renamed = next(e for e in events if e.type == "chat_renamed")
        assert renamed.data == {"chat_id": chat.id, "title": "Fix Login Bug"}
        assert db.get_chat(chat.id).title == "Fix Login Bug"

    @pytest.mark.asyncio
    async def test_already_titled_chat_emits_no_rename_event(self, db):
        chat = db.create_chat(title="Named already")
        llm = _ScriptedLLM(response=_response("New Title"))
        agent = _make_agent(db, chat.id, llm)
        queue = asyncio.Queue()

        await agent.chat("hello", queue)

        events = _drain(queue)
        assert all(e.type != "chat_renamed" for e in events)
        assert db.get_chat(chat.id).title == "Named already"


class TestToolFileAttachment:
    def _make_tool_agent(self, db, chat_id, tmp_dir, side_effect):
        agent = ReActAgent(
            chat_id=chat_id,
            db=db,
            provider=_FakeProvider(_ScriptedLLM()),
            tool_manager=MagicMock(),
            model_id="m",
            data_dir=tmp_dir,
            uploads_dir=os.path.join(tmp_dir, "uploads"),
            max_iterations=1,
        )
        agent.tool_manager.call_tool = AsyncMock(side_effect=side_effect)
        return agent

    @staticmethod
    def _write_report(tmp_dir):
        path = os.path.join(tmp_dir, "report.txt")
        with open(path, "w") as f:
            f.write("data")
        return path

    @pytest.mark.asyncio
    async def test_tool_saved_files_attach_to_tool_message(self, db, tmp_dir):
        async def save_then_return(name, args, ctx):
            ctx.save_file("report.txt", self._write_report(tmp_dir), "text/plain")
            return "Created report.txt."

        chat = db.create_chat()
        agent = self._make_tool_agent(db, chat.id, tmp_dir, save_then_return)
        tool_call = {"id": "tc1", "function": {"name": "report__make", "arguments": "{}"}}

        await agent._execute_tool_calls([tool_call], [], asyncio.Queue())

        msg = next(m for m in db.get_chat_history(chat.id) if m.tool_call_id == "tc1")
        file_ids = json.loads(msg.file_ids)
        assert len(file_ids) == 1
        row = db.get_files(file_ids)[file_ids[0]]
        assert row.status == "attached"
        assert row.filename == "report.txt"

    @pytest.mark.asyncio
    async def test_tool_saved_files_attach_after_approval(self, db, tmp_dir):
        async def save_then_request_approval(name, args, ctx):
            ctx.save_file("report.txt", self._write_report(tmp_dir), "text/plain")
            await ctx.on_approval_requested("appr-1", name, args)
            return "Created report.txt."

        chat = db.create_chat()
        agent = self._make_tool_agent(db, chat.id, tmp_dir, save_then_request_approval)
        tool_call = {"id": "tc2", "function": {"name": "report__make", "arguments": "{}"}}

        await agent._execute_tool_calls([tool_call], [], asyncio.Queue())

        msg = next(m for m in db.get_chat_history(chat.id) if m.tool_call_id == "tc2")
        assert msg.status == "completed"
        file_ids = json.loads(msg.file_ids)
        assert len(file_ids) == 1
        row = db.get_files(file_ids)[file_ids[0]]
        assert row.status == "attached"


class TestBuildContextSkillServers:
    def _make_skill_agent(self, db, chat_id, tool_servers):
        registry = FakeRegistry(
            {"deploy": FakeSkill(content="deploy steps", tool_servers=["k8s"])}
        )
        return ReActAgent(
            chat_id=chat_id,
            db=db,
            provider=_FakeProvider(_ScriptedLLM()),
            tool_manager=MagicMock(),
            model_id="m",
            data_dir="/tmp",
            max_iterations=1,
            tool_servers=tool_servers,
            skill_registry=registry,
        )

    @pytest.mark.asyncio
    async def test_skill_servers_stay_discoverable_when_discovery_enabled(self, db):
        chat = db.create_chat()
        agent = self._make_skill_agent(db, chat.id, ["workspace", "discovery"])

        await agent._build_context("/deploy the api")

        assert agent.tool_servers == ["workspace", "discovery"]
        assert db.get_chat(chat.id).tool_servers is None

    @pytest.mark.asyncio
    async def test_skill_servers_appended_when_discovery_disabled(self, db):
        chat = db.create_chat()
        agent = self._make_skill_agent(db, chat.id, ["workspace"])

        await agent._build_context("/deploy the api")

        assert agent.tool_servers == ["workspace", "k8s"]
        assert db.get_chat(chat.id).tool_servers == json.dumps(["workspace", "k8s"])
