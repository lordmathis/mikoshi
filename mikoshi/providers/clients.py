"""Base class and implementations for different LLM API clients."""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from mikoshi.observability import start_embedding_span

logger = logging.getLogger(__name__)


def coerce_tool_arguments(raw: Any) -> Dict[str, Any]:
    """Coerce persisted tool-call arguments to the dict providers require.

    Arguments are persisted as the model emitted them; when output was
    truncated mid-JSON the stored string is invalid and replaying it to a
    provider would hard-fail the request. Degrade to `{}` — loudly — since
    the matching tool result already recorded a recoverable error for the
    model.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    logger.warning(
        "Replacing malformed tool-call arguments with {}: %.200s", raw
    )
    return {}


class LLMClient(ABC):
    """Abstract base class for LLM API clients."""

    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: Sequence[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chat completion.

        Args:
            model: Model identifier
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            temperature: Optional temperature parameter
            max_tokens: Optional max tokens parameter

        Returns:
            Response dictionary in OpenAI format
        """
        pass

    async def get_models(self) -> List[Dict[str, Any]]:
        """Fetch available models as raw provider model objects.

        Full objects (not just ids) so callers can filter on nested fields
        such as ``pricing.prompt`` (e.g. OpenRouter-style /models payloads).

        Returns:
            List of model dictionaries, or empty list if not supported.
        """
        return []

    async def create_embedding(self, model: str, input: str) -> Optional[List[float]]:
        """Create an embedding vector for the input text.

        Args:
            model: Embedding model identifier
            input: Text to embed

        Returns:
            Embedding vector, or None if the provider does not support embeddings.
        """
        return None


class OpenAIClient(LLMClient):
    """Client for OpenAI-compatible APIs."""

    _POLL_INTERVAL_SECONDS = 2.0
    _ACTIVE_STATUSES = ("queued", "in_progress")

    def __init__(self, client: Any, service_tier: Optional[str] = None):
        """Initialize with an OpenAI client instance.

        Args:
            client: openai.AsyncOpenAI instance
            service_tier: when set (e.g. "flex"), completions run on the
                provider's async tier in background mode
        """
        self.client = client
        self._service_tier = service_tier

    async def get_models(self) -> List[Dict[str, Any]]:
        """Fetch available models using the async client."""
        response = await self.client.models.list()
        return [model.model_dump() for model in response.data]

    async def chat_completion(
        self,
        model: str,
        messages: Sequence[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chat completion using OpenAI API."""
        api_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if temperature is not None:
            api_params["temperature"] = temperature

        if max_tokens is not None:
            api_params["max_tokens"] = max_tokens

        if tools:
            api_params["tools"] = tools

        if self._service_tier:
            api_params["service_tier"] = self._service_tier
            api_params["background"] = True

        response = await self.client.chat.completions.create(**api_params)
        if self._service_tier:
            response = await self._poll_background(response)
        return response.model_dump()

    async def _poll_background(self, response: Any) -> Any:
        """Poll a background-mode completion until it reaches a terminal state."""
        logger.info(
            "Background completion %s submitted (service_tier=%s)",
            response.id,
            self._service_tier,
        )
        while response.status in self._ACTIVE_STATUSES:
            await asyncio.sleep(self._POLL_INTERVAL_SECONDS)
            response = await self.client.chat.completions.retrieve(response.id)
        logger.info("Background completion %s ended with status=%s", response.id, response.status)
        if response.status in ("failed", "cancelled"):
            # Raise non-retryable: agent-loop retries would resubmit and
            # re-bill the job.
            raise RuntimeError(
                f"Background completion {response.id} ended with status '{response.status}'"
            )
        return response

    async def create_embedding(self, model: str, input: str) -> Optional[List[float]]:
        """Create an embedding vector using the OpenAI-compatible embeddings API."""
        with start_embedding_span(model, input):
            response = await self.client.embeddings.create(model=model, input=input)
            if not response.data:
                return None
            return response.data[0].embedding


class AnthropicClient(LLMClient):
    """Client for Anthropic API."""

    def __init__(self, client: Any):
        self.client = client

    async def chat_completion(
        self,
        model: str,
        messages: Sequence[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        system_prompt, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools) if tools else None

        api_params: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,
        }

        if system_prompt:
            api_params["system"] = system_prompt
        if temperature is not None:
            api_params["temperature"] = temperature
        if anthropic_tools:
            api_params["tools"] = anthropic_tools

        response = await self.client.messages.create(**api_params)
        return self._convert_response_to_openai(response)

    def _convert_messages(
        self, messages: Sequence[Any]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        system_parts = [
            m.get("content", "")
            for m in messages
            if m.get("role") in ("system", "developer")
        ]
        system_prompt = "\n\n".join(system_parts) if system_parts else None

        anthropic_messages: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role in ("system", "developer"):
                continue

            if role == "tool":
                # Anthropic expects all tool results of a turn grouped into a
                # single user message.
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id"),
                    "content": msg.get("content", ""),
                }
                last = anthropic_messages[-1] if anthropic_messages else None
                if (
                    last is not None
                    and last.get("role") == "user"
                    and isinstance(last.get("content"), list)
                    and last["content"]
                    and last["content"][0].get("type") == "tool_result"
                ):
                    last["content"].append(tool_result)
                else:
                    anthropic_messages.append(
                        {
                            "role": "user",
                            "content": [tool_result],
                        }
                    )
            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    content_parts: list = []
                    text = msg.get("content")
                    if text:
                        content_parts.append({"type": "text", "text": text})
                    for tc in tool_calls:
                        content_parts.append(
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "input": coerce_tool_arguments(
                                    tc["function"]["arguments"]
                                ),
                            }
                        )
                    anthropic_messages.append(
                        {"role": "assistant", "content": content_parts}
                    )
                else:
                    anthropic_messages.append(
                        {"role": "assistant", "content": msg.get("content", "")}
                    )
            elif role == "user":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": self._convert_user_content(msg.get("content", "")),
                    }
                )

        return system_prompt, anthropic_messages

    @staticmethod
    def _convert_user_content(content: Any) -> Any:
        """Convert OpenAI-style user content to Anthropic's format.

        Text parts pass through unchanged; ``image_url`` parts become
        Anthropic ``image`` blocks (base64 data URLs or remote URLs).
        """
        if not isinstance(content, list):
            return content
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                url = part.get("image_url", {}).get("url", "")
                converted = AnthropicClient._convert_image_url(url)
                if converted is not None:
                    parts.append(converted)
                    continue
            parts.append(part)
        return parts

    @staticmethod
    def _convert_image_url(url: str) -> Optional[Dict[str, Any]]:
        if url.startswith("data:") and ";base64," in url:
            media_type, _, data = url[len("data:") :].partition(";base64,")
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            }
        if url.startswith(("http://", "https://")):
            return {"type": "image", "source": {"type": "url", "url": url}}
        return None

    @staticmethod
    def _convert_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                result.append(
                    {
                        "name": func.get("name"),
                        "description": func.get("description"),
                        "input_schema": func.get("parameters", {}),
                    }
                )
        return result

    _FINISH_REASON_MAP = {
        "tool_use": "tool_calls",
        "end_turn": "stop",
        "stop_sequence": "stop",
        "pause_turn": "stop",
        "refusal": "content_filter",
        "max_tokens": "length",
    }

    def _convert_response_to_openai(self, response: Any) -> Dict[str, Any]:
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input)
                            if isinstance(block.input, dict)
                            else block.input,
                        },
                    }
                )

        content = "\n".join(content_parts) if content_parts else None

        message: Dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }

        if tool_calls:
            message["tool_calls"] = tool_calls

        return {
            "id": response.id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": self._FINISH_REASON_MAP.get(
                        response.stop_reason, response.stop_reason
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
        }
