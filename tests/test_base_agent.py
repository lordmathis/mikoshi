import asyncio
from unittest.mock import MagicMock

import httpx
import pytest
from openai import AuthenticationError, InternalServerError, RateLimitError

from mikoshi.agents.react import ReActAgent


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


class TestChatTitleSkippedOnFailedTurn:
    @pytest.mark.asyncio
    async def test_failed_turn_emits_error_and_skips_title(self, db, monkeypatch):
        await monkeypatch_asyncio_sleep(monkeypatch)
        chat = db.create_chat()
        llm = _ScriptedLLM(failures=99, error=_rate_limit())
        agent = _make_agent(db, chat.id, llm)
        title_calls = []

        async def fake_generate_title():
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

        async def fake_generate_title():
            title_calls.append(True)

        agent._generate_title = fake_generate_title
        queue = asyncio.Queue()

        await agent.chat("hello", queue)

        assert title_calls == [True]
        events = _drain(queue)
        assert events[-1].type == "done"
