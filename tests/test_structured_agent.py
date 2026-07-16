import asyncio
import json
from unittest.mock import MagicMock

import pytest

from mikoshi.agents.structured import StructuredAgent


def _parse(content: str):
    agent = StructuredAgent.__new__(StructuredAgent)
    return agent._parse_final_response(content)


class _FakeProvider:
    def get_llm_client(self):
        return MagicMock()


def _make_structured_agent(db, chat_id):
    return StructuredAgent(
        chat_id=chat_id,
        db=db,
        provider=_FakeProvider(),
        tool_manager=MagicMock(),
        model_id="m",
        data_dir="/tmp",
    )


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


class TestProcessFinalResponse:
    """The state merge is what actually keeps (or loses) a running workout."""

    @pytest.mark.asyncio
    async def test_partial_new_state_merges_and_persists(self, db):
        chat = db.create_chat()
        agent = _make_structured_agent(db, chat.id)
        db.update_chat_state(
            chat.id,
            {
                "status": "active",
                "date": "2026-01-01",
                "exercises": [
                    {"name": "squat", "sets": [{"weight": "60kg", "reps": "5"}]}
                ],
            },
        )
        # new_state re-emits the FULL exercises array but omits status/date;
        # the omitted keys must survive, the updated key must replace wholesale.
        content = json.dumps(
            {
                "user_message": "logged set 2",
                "new_state": {
                    "exercises": [
                        {
                            "name": "squat",
                            "sets": [
                                {"weight": "60kg", "reps": "5"},
                                {"weight": "60kg", "reps": "5"},
                            ],
                        }
                    ]
                },
            }
        )

        queue = asyncio.Queue()
        result = await agent._process_final_response(
            {}, {"content": content}, queue
        )

        state = db.get_chat_state(chat.id)
        assert state["status"] == "active"
        assert state["date"] == "2026-01-01"
        assert len(state["exercises"][0]["sets"]) == 2
        assert result["user_message"] == "logged set 2"
