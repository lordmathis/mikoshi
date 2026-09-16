import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from mikoshi.providers.clients import OpenAIClient


def _completion(status, text="hello"):
    body = {
        "id": "chatcmpl_1",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }
    return SimpleNamespace(
        id="chatcmpl_1",
        status=status,
        choices=body["choices"],
        model_dump=lambda: body,
    )


def _queued_stub(status=None):
    return SimpleNamespace(id="chatcmpl_1", status=status, choices=[])


def _native_client(create_response, retrieve_responses):
    native = MagicMock()
    native.chat.completions.create = AsyncMock(return_value=create_response)
    native.chat.completions.retrieve = AsyncMock(side_effect=retrieve_responses)
    return native


@patch("mikoshi.providers.clients.asyncio.sleep", new_callable=AsyncMock)
class TestBackgroundPolling:
    @pytest.mark.asyncio
    async def test_submits_with_background_and_polls_to_completion(self, _sleep):
        native = _native_client(
            _completion("queued"),
            [_completion("in_progress"), _completion("completed")],
        )
        client = OpenAIClient(native, service_tier="flex")

        result = await client.chat_completion("test-model", [{"role": "user", "content": "hi"}])

        native.chat.completions.create.assert_awaited_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            service_tier="flex",
            extra_body={"background": True},
        )
        assert native.chat.completions.retrieve.await_count == 2
        native.chat.completions.retrieve.assert_awaited_with("chatcmpl_1")
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_failed_status_raises_non_retryable(self, _sleep):
        native = _native_client(
            _completion("queued"),
            [_completion("failed")],
        )
        client = OpenAIClient(native, service_tier="flex")

        with pytest.raises(RuntimeError, match="chatcmpl_1.*failed"):
            await client.chat_completion("test-model", [{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_immediately_completed_skips_polling(self, _sleep):
        native = _native_client(_completion("completed"), [])
        client = OpenAIClient(native, service_tier="flex")

        result = await client.chat_completion("test-model", [{"role": "user", "content": "hi"}])

        native.chat.completions.retrieve.assert_not_awaited()
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_statusless_stub_polled_until_choices_arrive(self, _sleep):
        native = _native_client(
            _queued_stub(),
            [_queued_stub(), _completion(None)],
        )
        client = OpenAIClient(native, service_tier="flex")

        result = await client.chat_completion("test-model", [{"role": "user", "content": "hi"}])

        assert native.chat.completions.retrieve.await_count == 2
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_blocking_response_without_status_skips_polling(self, _sleep):
        native = _native_client(_completion(None), [])
        client = OpenAIClient(native, service_tier="flex")

        result = await client.chat_completion("test-model", [{"role": "user", "content": "hi"}])

        native.chat.completions.retrieve.assert_not_awaited()
        assert result["choices"][0]["message"]["content"] == "hello"


class TestRealtimePath:
    @pytest.mark.asyncio
    async def test_no_service_tier_sends_plain_request(self):
        native = _native_client(_completion("completed"), [])
        client = OpenAIClient(native)

        await client.chat_completion("test-model", [{"role": "user", "content": "hi"}])

        kwargs = native.chat.completions.create.await_args.kwargs
        assert "service_tier" not in kwargs
        assert "extra_body" not in kwargs
