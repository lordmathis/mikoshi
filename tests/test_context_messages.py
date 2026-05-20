import json

import pytest

from mikoshi.agents.context.messages import (
    extract_assistant_content,
    extract_text_content,
    parse_content,
)


class TestParseContent:
    @pytest.mark.parametrize("input_val,expected", [
        ("hello", "hello"),
        ('{"type": "text", "text": "hi"}', {"type": "text", "text": "hi"}),
        ('[{"type": "text", "text": "hi"}]', [{"type": "text", "text": "hi"}]),
        ("{broken json", "{broken json"),
        ("", ""),
        (None, None),
    ])
    def test_parse_content(self, input_val, expected):
        assert parse_content(input_val) == expected


class TestExtractTextContent:
    def test_plain_string(self):
        assert extract_text_content("hello world") == "hello world"

    def test_content_list_with_text_parts(self):
        raw = json.dumps([
            {"type": "text", "text": "hello "},
            {"type": "image_url", "image_url": {"url": "data:..."}},
            {"type": "text", "text": "world"},
        ])
        assert extract_text_content(raw) == "hello  world"

    def test_non_text_parts_skipped(self):
        raw = json.dumps([
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ])
        assert extract_text_content(raw) == ""


class TestExtractAssistantContent:
    def test_simple_text_response(self):
        response = {
            "choices": [
                {"message": {"content": "Hello there", "role": "assistant"}}
            ]
        }
        content, reasoning, tool_calls = extract_assistant_content(response)
        assert content == "Hello there"
        assert reasoning is None
        assert tool_calls is None

    @pytest.mark.parametrize("response", [
        {"choices": []},
        {},
        {"choices": [{"message": {"content": None}}]},
    ])
    def test_empty_or_null_content(self, response):
        content, reasoning, tool_calls = extract_assistant_content(response)
        assert content == ""
        assert reasoning is None

    def test_tool_calls_parsed(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path": "/tmp/f.txt"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        content, _, tool_calls = extract_assistant_content(response)
        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "read_file"
        assert tool_calls[0]["id"] == "call_abc"
        assert tool_calls[0]["arguments"] == {"path": "/tmp/f.txt"}

    def test_tool_call_missing_id_gets_generated(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "test",
                                    "arguments": "{}",
                                }
                            }
                        ],
                    }
                }
            ]
        }
        _, _, tool_calls = extract_assistant_content(response)
        assert tool_calls[0]["id"] == "call_0"

    def test_reasoning_content_preserved(self):
        response = {
            "choices": [
                {"message": {"content": "answer", "reasoning_content": "let me think"}}
            ]
        }
        _, reasoning, _ = extract_assistant_content(response)
        assert reasoning == "let me think"

    def test_multiple_tool_calls(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_0",
                                "function": {"name": "read", "arguments": "{}"},
                            },
                            {
                                "id": "call_1",
                                "function": {"name": "write", "arguments": "{}"},
                            },
                        ],
                    }
                }
            ]
        }
        _, _, tool_calls = extract_assistant_content(response)
        assert len(tool_calls) == 2
        assert tool_calls[0]["name"] == "read"
        assert tool_calls[1]["name"] == "write"
