import logging
import re
from typing import List, Optional, Tuple

from openai.types.chat import ChatCompletionMessageParam

from mikoshi.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


def parse_mentions(message: str) -> List[str]:
    """Extract /skill mentions from a message."""
    pattern = r"/([a-zA-Z0-9_-]+)"
    return re.findall(pattern, message)


def build_skill_context(
    skill_names: List[str], skill_registry: Optional[SkillRegistry]
) -> Tuple[str, List[str]]:
    """Build context text from mentioned skills and collect required tool servers.

    Returns:
        Tuple of (skill_context_string, list of required tool servers)
    """
    if not skill_registry or not skill_names:
        return "", []

    skill_context_parts = []
    required_tool_servers = []

    for skill_name in skill_names:
        skill = skill_registry.get_skill(skill_name)
        if skill:
            try:
                content = skill.read_content()
                skill_context_parts.append(
                    f"\n\n--- Skill /{skill_name} ---\n{content}"
                )
                logger.info(f"Loaded skill /{skill_name} for context")
                tool_servers = skill.get_required_tool_servers()
                if tool_servers:
                    required_tool_servers.extend(tool_servers)
                    logger.info(
                        f"Skill /{skill_name} requires tool servers: {tool_servers}"
                    )
            except Exception as e:
                logger.error(f"Error loading skill /{skill_name}: {e}")
        else:
            logger.debug(f"Skill /{skill_name} not found, treating as plain text")

    context_str = "\n".join(skill_context_parts) if skill_context_parts else ""
    return context_str, required_tool_servers


def apply_skill_context(
    messages: List[ChatCompletionMessageParam], skill_context: str
) -> List[ChatCompletionMessageParam]:
    """Apply skill context to message list by augmenting system prompt."""
    if not skill_context:
        return messages

    if messages and messages[0].get("role") in ("system", "developer"):
        existing_content = messages[0].get("content", "")
        if isinstance(existing_content, str):
            messages[0]["content"] = existing_content + skill_context
        else:
            messages[0]["content"] = str(existing_content) + skill_context
    else:
        messages.insert(0, {"role": "system", "content": skill_context.strip()})

    return messages
