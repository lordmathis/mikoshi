import logging
from typing import List

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.context.messages import extract_text_content
from mikoshi.db.db import Database
from mikoshi.providers.clients import LLMClient

logger = logging.getLogger(__name__)

_pending_titles: set[str] = set()

SYSTEM_PROMPT = """You are a high-level intent-extraction engine. Your task is to generate a concise, 3-5 word title for a conversation.

CRITICAL GUIDELINE: Focus on the User's Goal, not the system's technical response. Even if a tool fails, an error occurs, or the AI cannot fulfill a request, the title must reflect what the user was attempting to do.

Tone: Functional, technical, and terse. Cyberpunk edge. 
Style: Drop articles (a, an, the). Use "Objective: [Topic]" or "[Topic] Analysis/Query" structures.

Examples:
- User wants a recipe but gets a 403 error -> "Recipe Extraction: [Dish Name]"
- User asks about a broken server -> "Server Connectivity Troubleshooting"
- User asks for a workout -> "Physical Conditioning Protocol"

DO NOT: Reference errors, status codes, or "Log" unless the user specifically asked for a log.
DO NOT: Use quotes.
Output ONLY the title."""

USER_PROMPT_TEMPLATE = """Review the following exchange and identify the user's primary objective. Generate a 3-5 word title:
{conversation}"""


async def generate_title(
    chat_id: str,
    db: Database,
    llm_client: LLMClient,
    model_id: str,
) -> None:
    """Generate a title for the chat if it's still 'Untitled Chat'.

    This is meant to be run as a background task after the first exchange.
    """
    try:
        chat = db.get_chat(chat_id)
        if not chat or chat.title not in (None, "", "Untitled Chat"):
            return

        if chat_id in _pending_titles:
            return
        _pending_titles.add(chat_id)
        try:
            history = db.get_chat_history(chat_id)
            if not history or len(history) < 1:
                return

            conversation_text = ""
            for msg in history[:6]:
                if msg.role in ["user", "assistant"]:
                    content_str = extract_text_content(msg.content)
                    conversation_text += f"{msg.role.capitalize()}: {content_str}\n"

            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        conversation=conversation_text
                    ),
                },
            ]

            response = await llm_client.chat_completion(
                model=model_id,
                messages=messages,
                tools=None,
                temperature=0.2,
            )

            if "error" not in response:
                choices = response.get("choices", [])
                if choices:
                    title = choices[0].get("message", {}).get("content", "").strip()
                    if title:
                        logger.info(f"Generated chat title: '{title}'")
                        db.update_chat(chat_id, title=title)
        finally:
            _pending_titles.discard(chat_id)
    except Exception as e:
        logger.warning(f"Failed to generate title for chat {chat_id}: {e}")
