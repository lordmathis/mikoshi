import logging
from typing import List

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.agents.context.messages import extract_text_content
from mikoshi.db.db import Database
from mikoshi.providers.clients import LLMClient

logger = logging.getLogger(__name__)

_pending_titles: set[str] = set()

SYSTEM_PROMPT = """Generate a short, natural-sounding title for this conversation. 3-6 words. Title case.

The title should reflect what the user is trying to do, not any errors or technical details in the response.

Think of it like naming a blog post or a YouTube video — clear, casual, and descriptive.

Examples:
- User asks about granola vs protein bars -> "Granola to Protein Bars Guide"
- User wants to organize Firefox bookmarks with AI -> "Sort Firefox Bookmarks With LLMs"
- User tracks their 5K running progress -> "5K Runner's Progress Analysis"
- User asks about metal music inspired by literature -> "Metal Music Inspired By Books"

Do not reference errors or status codes. Do not use quotes.
Output only the title."""

USER_PROMPT_TEMPLATE = """Generate a short title for this conversation:

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
