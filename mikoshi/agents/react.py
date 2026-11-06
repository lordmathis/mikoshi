import logging

from mikoshi.agents.base import BaseAgent
from mikoshi.agents.plugin_base import AgentPluginBase

logger = logging.getLogger(__name__)


class ReActAgent(BaseAgent):
    """ReAct agent: iterative think -> act -> observe loop."""


class ReActAgentPlugin(ReActAgent, AgentPluginBase):
    """Base class for ReAct agent plugins."""
