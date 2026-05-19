import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mikoshi.config import (
    FilterCondition,
    ModelFilter,
    ProviderConfig,
    ProviderType,
)
from mikoshi.providers.provider import Provider


def _provider(
    model_ids=None, model_filter=None, provider_type=ProviderType.OPENAI, **kwargs
):
    cfg = ProviderConfig(
        model_ids=model_ids, model_filter=model_filter, type=provider_type, **kwargs
    )
    return Provider(cfg, "test")


class TestMatchesFilter:
    def test_contains_match_and_no_match(self):
        p = _provider()
        cond = [FilterCondition(field="id", contains="gpt")]
        assert p._matches_filter({"id": "gpt-4"}, cond) is True
        assert p._matches_filter({"id": "claude-3"}, cond) is False

    def test_excludes_match_and_no_match(self):
        p = _provider()
        cond = [FilterCondition(field="id", excludes="preview")]
        assert p._matches_filter({"id": "gpt-4"}, cond) is True
        assert p._matches_filter({"id": "gpt-4-preview"}, cond) is False

    def test_equals_match_and_no_match(self):
        p = _provider()
        cond = [FilterCondition(field="id", equals="gpt-4")]
        assert p._matches_filter({"id": "gpt-4"}, cond) is True
        assert p._matches_filter({"id": "gpt-3.5"}, cond) is False

    def test_multiple_conditions_and_logic(self):
        p = _provider()
        cond = [
            FilterCondition(field="id", contains="gpt"),
            FilterCondition(field="id", excludes="preview"),
        ]
        assert p._matches_filter({"id": "gpt-4"}, cond) is True
        assert p._matches_filter({"id": "gpt-4-preview"}, cond) is False

    def test_field_is_none_returns_false(self):
        p = _provider()
        cond = [FilterCondition(field="name", contains="x")]
        assert p._matches_filter({"id": "gpt-4"}, cond) is False

    def test_no_conditions_returns_true(self):
        p = _provider()
        assert p._matches_filter({"id": "gpt-4"}, []) is True

    def test_nested_field(self):
        p = _provider()
        cond = [FilterCondition(field="pricing.prompt", contains="0.03")]
        assert (
            p._matches_filter({"pricing": {"prompt": "0.03"}}, cond) is True
        )


class TestGetModelIds:
    @pytest.mark.asyncio
    async def test_static_model_ids_no_api_call(self):
        p = _provider(model_ids=["gpt-4", "gpt-3.5"])
        assert await p.get_model_ids() == ["gpt-4", "gpt-3.5"]

    @pytest.mark.asyncio
    async def test_api_with_filter(self):
        filt = ModelFilter(
            conditions=[
                FilterCondition(field="id", contains="gpt"),
                FilterCondition(field="id", excludes="preview"),
            ]
        )
        p = _provider(model_filter=filt)
        mock_client = MagicMock()
        mock_client.get_models = AsyncMock(
            return_value=["gpt-4", "gpt-4-preview", "claude-3", "gpt-3.5-turbo"]
        )
        p._llm_client = mock_client
        result = await p.get_model_ids()
        assert result == ["gpt-4", "gpt-3.5-turbo"]

    @pytest.mark.asyncio
    async def test_api_no_filter_returns_all(self):
        p = _provider()
        mock_client = MagicMock()
        mock_client.get_models = AsyncMock(return_value=["gpt-4", "claude-3"])
        p._llm_client = mock_client
        assert await p.get_model_ids() == ["gpt-4", "claude-3"]

    @pytest.mark.asyncio
    async def test_api_error_falls_back_to_static(self):
        p = _provider(model_ids=["fallback"])
        mock_client = MagicMock()
        mock_client.get_models = AsyncMock(side_effect=Exception("network"))
        p._llm_client = mock_client
        assert await p.get_model_ids() == ["fallback"]

    @pytest.mark.asyncio
    async def test_api_error_no_static_returns_none(self):
        p = _provider()
        mock_client = MagicMock()
        mock_client.get_models = AsyncMock(side_effect=Exception("fail"))
        p._llm_client = mock_client
        assert await p.get_model_ids() is None

    @pytest.mark.asyncio
    async def test_filter_set_ignores_static_ids(self):
        filt = ModelFilter(
            conditions=[FilterCondition(field="id", contains="gpt")]
        )
        p = _provider(model_ids=["static-gpt"], model_filter=filt)
        mock_client = MagicMock()
        mock_client.get_models = AsyncMock(return_value=["gpt-4", "claude"])
        p._llm_client = mock_client
        assert await p.get_model_ids() == ["gpt-4"]


class TestGetLlmClient:
    @patch("mikoshi.providers.provider.AsyncOpenAI")
    @patch("mikoshi.providers.provider.OpenAIClient")
    def test_openai_with_api_base(self, mock_cls, mock_async):
        p = _provider(api_key="key", api_base="http://localhost:8080")
        c1 = p.get_llm_client()
        c2 = p.get_llm_client()
        assert c1 is c2
        mock_async.assert_called_once_with(api_key="key", base_url="http://localhost:8080")

    @patch("mikoshi.providers.provider.AsyncAnthropic")
    @patch("mikoshi.providers.provider.AnthropicClient")
    def test_anthropic_branch(self, mock_cls, mock_async):
        p = _provider(provider_type=ProviderType.ANTHROPIC, api_key="ant-key")
        p.get_llm_client()
        mock_async.assert_called_once_with(api_key="ant-key")

    @patch("mikoshi.providers.provider.AsyncOpenAI")
    @patch("mikoshi.providers.provider.OpenAIClient")
    def test_none_api_key_uses_empty_string(self, mock_cls, mock_async):
        p = _provider(api_key=None)
        p.get_llm_client()
        mock_async.assert_called_once_with(api_key="")
