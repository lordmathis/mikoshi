from types import SimpleNamespace

from mikoshi.providers.clients import AnthropicClient, coerce_tool_arguments


def _client() -> AnthropicClient:
    return AnthropicClient(None)


class TestCoerceToolArguments:
    def test_dict_passthrough(self):
        assert coerce_tool_arguments({"a": 1}) == {"a": 1}

    def test_valid_json_string_parsed(self):
        assert coerce_tool_arguments('{"a": 1}') == {"a": 1}

    def test_truncated_json_string_degrades_to_empty(self):
        assert coerce_tool_arguments('{"path": "fo') == {}

    def test_non_object_json_degrades_to_empty(self):
        assert coerce_tool_arguments("[1, 2]") == {}

    def test_none_degrades_to_empty(self):
        assert coerce_tool_arguments(None) == {}


class TestConvertMessages:
    def test_consecutive_tool_results_grouped_into_one_user_message(self):
        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "t1", "function": {"name": "a", "arguments": "{}"}},
                    {"id": "t2", "function": {"name": "b", "arguments": "{}"}},
                ],
            },
            {"role": "tool", "tool_call_id": "t1", "content": "r1"},
            {"role": "tool", "tool_call_id": "t2", "content": "r2"},
        ]

        _, msgs = _client()._convert_messages(messages)

        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
        assert [b["tool_use_id"] for b in msgs[2]["content"]] == ["t1", "t2"]

    def test_tool_results_across_turns_not_merged(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "t1", "function": {"name": "a", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "t1", "content": "r1"},
            {"role": "user", "content": "next turn"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "t2", "function": {"name": "b", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "t2", "content": "r2"},
        ]

        _, msgs = _client()._convert_messages(messages)

        assert [m["role"] for m in msgs] == [
            "assistant",
            "user",
            "user",
            "assistant",
            "user",
        ]
        assert msgs[1]["content"][0]["tool_use_id"] == "t1"
        assert msgs[4]["content"][0]["tool_use_id"] == "t2"

    def test_truncated_tool_arguments_degrade_to_empty_input(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "t1",
                        "function": {"name": "a", "arguments": '{"path": "fo'},
                    }
                ],
            },
        ]

        _, msgs = _client()._convert_messages(messages)

        assert msgs[0]["content"][0]["input"] == {}

    def test_system_messages_extracted_and_joined(self):
        messages = [
            {"role": "system", "content": "one"},
            {"role": "system", "content": "two"},
            {"role": "user", "content": "hi"},
        ]

        system, msgs = _client()._convert_messages(messages)

        assert system == "one\n\ntwo"
        assert len(msgs) == 1

    def test_user_image_parts_converted_to_anthropic_format(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "look"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,QUJD"},
                    },
                ],
            }
        ]

        _, msgs = _client()._convert_messages(messages)

        content = msgs[0]["content"]
        assert content[0] == {"type": "text", "text": "look"}
        assert content[1] == {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"},
        }

    def test_remote_image_url_converted_to_url_source(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/cat.png"},
                    },
                ],
            }
        ]

        _, msgs = _client()._convert_messages(messages)

        assert msgs[0]["content"][0] == {
            "type": "image",
            "source": {"type": "url", "url": "https://example.com/cat.png"},
        }

    def test_plain_string_user_content_untouched(self):
        messages = [{"role": "user", "content": "hello"}]
        _, msgs = _client()._convert_messages(messages)
        assert msgs[0] == {"role": "user", "content": "hello"}


class TestConvertResponse:
    @staticmethod
    def _response(stop_reason: str):
        return SimpleNamespace(
            id="msg_1",
            model="claude-x",
            content=[
                SimpleNamespace(type="text", text="hello"),
                SimpleNamespace(type="tool_use", id="t1", name="a", input={"x": 1}),
            ],
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=5, output_tokens=7),
        )

    def test_stop_reason_tool_use_maps_to_tool_calls(self):
        out = _client()._convert_response_to_openai(self._response("tool_use"))
        assert out["choices"][0]["finish_reason"] == "tool_calls"
        assert out["choices"][0]["message"]["tool_calls"][0]["id"] == "t1"

    def test_stop_reason_end_turn_maps_to_stop(self):
        out = _client()._convert_response_to_openai(self._response("end_turn"))
        assert out["choices"][0]["finish_reason"] == "stop"

    def test_stop_reason_max_tokens_maps_to_length(self):
        out = _client()._convert_response_to_openai(self._response("max_tokens"))
        assert out["choices"][0]["finish_reason"] == "length"

    def test_created_is_current_time(self):
        import time

        out = _client()._convert_response_to_openai(self._response("end_turn"))
        assert abs(out["created"] - int(time.time())) < 5
