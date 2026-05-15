"""Base class and implementations for different LLM API clients."""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence


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

    async def get_models(self) -> List[str]:
        """Fetch available model IDs.

        Returns:
            List of model ID strings, or empty list if not supported.
        """
        return []


class OpenAIClient(LLMClient):
    """Client for OpenAI-compatible APIs."""

    def __init__(self, client: Any):
        """Initialize with an OpenAI client instance.

        Args:
            client: openai.OpenAI instance
        """
        self.client = client

    async def get_models(self) -> List[str]:
        """Fetch available model IDs using the async client.

        Returns:
            List of model ID strings
        """
        response = await self.client.models.list()
        return [model.id for model in response.data]

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

        response = await self.client.chat.completions.create(**api_params)
        return response.model_dump()


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
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id"),
                        "content": msg.get("content", ""),
                    }],
                })
            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    content_parts: list = []
                    text = msg.get("content")
                    if text:
                        content_parts.append({"type": "text", "text": text})
                    for tc in tool_calls:
                        args = tc["function"]["arguments"]
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        content_parts.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args,
                        })
                    anthropic_messages.append({"role": "assistant", "content": content_parts})
                else:
                    anthropic_messages.append({"role": "assistant", "content": msg.get("content", "")})
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": msg.get("content", "")})

        return system_prompt, anthropic_messages

    @staticmethod
    def _convert_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                result.append({
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "input_schema": func.get("parameters", {}),
                })
        return result

    def _convert_response_to_openai(self, response: Any) -> Dict[str, Any]:
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input)
                        if isinstance(block.input, dict)
                        else block.input,
                    },
                })

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
            "created": int(response.model_dump().get("created_at", 0))
            if hasattr(response, "created_at")
            else 0,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": response.stop_reason,
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
        }
