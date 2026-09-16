import logging
from typing import Any, Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from mikoshi.config import ProviderConfig, ProviderType
from mikoshi.providers.clients import AnthropicClient, LLMClient, OpenAIClient

logger = logging.getLogger(__name__)


class Provider:
    def __init__(self, config: ProviderConfig, name: str):
        self.config = config
        self._name = name
        self._llm_client: Optional[LLMClient] = None

    def name(self) -> str:
        return self._name

    def get_llm_client(self) -> LLMClient:
        """Get or create the appropriate LLM client based on provider type."""
        if self._llm_client is None:
            kwargs: dict = {"api_key": self.config.api_key or ""}
            if self.config.api_base:
                kwargs["base_url"] = self.config.api_base

            if self.config.type == ProviderType.ANTHROPIC:
                native_client = AsyncAnthropic(**kwargs)
                self._llm_client = AnthropicClient(native_client)

            else:
                native_client = AsyncOpenAI(**kwargs)
                self._llm_client = OpenAIClient(
                    native_client, service_tier=self.config.service_tier
                )

        return self._llm_client

    async def get_model_ids(self) -> list[str] | None:
        """Query the /models endpoint to get available model IDs.

        If model_filter is configured, fetches and filters models from the
        API. Filter conditions match against the full model objects, so
        nested fields like "pricing.prompt" work. If model_ids is
        configured, returns the static list. Otherwise, fetches all models
        from the provider.

        Returns:
            List of model IDs if successful, None if an error occurs
        """
        if self.config.model_ids and not self.config.model_filter:
            return self.config.model_ids

        try:
            llm_client = self.get_llm_client()
            models = await llm_client.get_models()

            if not models:
                return self.config.model_ids

            if self.config.model_filter and self.config.model_filter.conditions:
                return [
                    m["id"]
                    for m in models
                    if m.get("id")
                    and self._matches_filter(m, self.config.model_filter.conditions)
                ]

            return [m["id"] for m in models if m.get("id")]

        except Exception as e:
            logger.warning("Error fetching models from %s: %s", self._name, e)
            return self.config.model_ids

    def _matches_filter(self, model_dict: dict, conditions: list) -> bool:
        """Check if a model matches all filter conditions.

        Args:
            model_dict: The model data as a dictionary
            conditions: List of FilterCondition objects

        Returns:
            True if the model matches all conditions, False otherwise
        """
        for condition in conditions:
            # Get the field value using JSONPath-like notation (e.g., "pricing.prompt")
            value = self._get_nested_value(model_dict, condition.field)

            if value is None:
                return False

            value_str = str(value)

            # Check contains condition
            if condition.contains is not None:
                if condition.contains not in value_str:
                    return False

            # Check excludes condition
            if condition.excludes is not None:
                if condition.excludes in value_str:
                    return False

            # Check equals condition
            if condition.equals is not None:
                if value != condition.equals:
                    return False

        return True

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get a nested value from a dictionary using dot notation.

        Args:
            data: The dictionary to search
            path: Dot-separated path (e.g., "pricing.prompt" or "id")

        Returns:
            The value at the path, or None if not found
        """
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return None
            else:
                return None

        return current
