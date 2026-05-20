import json

import pytest

from mikoshi.agents.structured import StructuredAgent


def _parse(content: str):
    agent = StructuredAgent.__new__(StructuredAgent)
    return agent._parse_final_response(content)


class TestParseFinalResponse:
    def test_clean_json(self):
        msg, state = _parse(json.dumps({
            "user_message": "Done!",
            "new_state": {"count": 1},
        }))
        assert msg == "Done!"
        assert state == {"count": 1}

    @pytest.mark.parametrize("fence", [
        "```json\n{payload}\n```",
        "```\n{payload}\n```",
        "  ```\n  {payload}  \n  ```  ",
    ])
    def test_json_in_code_block(self, fence):
        payload = json.dumps({"user_message": "ok", "new_state": {}})
        msg, state = _parse(fence.format(payload=payload))
        assert msg == "ok"
        assert state == {}

    def test_json_embedded_in_prose(self):
        obj = {"user_message": "hello", "new_state": {"k": "v"}}
        raw = f'Some text before {json.dumps(obj)} and after'
        msg, state = _parse(raw)
        assert msg == "hello"
        assert state == {"k": "v"}

    def test_missing_user_message_falls_back_to_full_content(self):
        raw = json.dumps({"new_state": {"a": 1}})
        msg, state = _parse(raw)
        assert msg == raw
        assert state == {"a": 1}

    def test_missing_new_state_defaults_empty(self):
        raw = json.dumps({"user_message": "hi"})
        msg, state = _parse(raw)
        assert msg == "hi"
        assert state == {}

    def test_empty_content_returns_empty(self):
        msg, state = _parse("")
        assert msg == ""
        assert state == {}

    def test_none_content_returns_empty(self):
        msg, state = _parse(None)
        assert msg is None
        assert state == {}

    def test_unparseable_text_returns_as_is(self):
        msg, state = _parse("just plain text with no json")
        assert msg == "just plain text with no json"
        assert state == {}

    def test_new_state_non_object_returned_as_is(self):
        raw = json.dumps({"user_message": "hi", "new_state": "not an object"})
        msg, state = _parse(raw)
        assert msg == "hi"
        assert state == "not an object"
