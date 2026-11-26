from abc import ABC, abstractmethod
from typing import Any, Dict

from mikoshi.tools.context import ToolCallContext


def normalize_tool(tool: Any) -> Dict[str, Any]:
    """Normalize a tool object from any handler type into a plain dict.

    ToolSetHandler tools expose ``parameters`` (JSON Schema); MCP ``Tool``
    objects expose ``input_schema``.
    """
    schema = getattr(tool, "input_schema", None) or getattr(tool, "parameters", None)
    return {
        "name": getattr(tool, "name", "unknown"),
        "description": getattr(tool, "description", "") or "",
        "parameters": schema or {},
    }


class ToolHandler(ABC):
    """Base handler for a type of tool"""

    server_name: str

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the handler and register its tools"""
        pass

    @abstractmethod
    async def call_tool(
        self, tool_name: str, arguments: dict, context: ToolCallContext
    ) -> Any:
        """Execute a tool"""
        pass

    @abstractmethod
    async def list_tools(self) -> list:
        """List available tools"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources"""
        pass

    def suggested_rule(self, arguments: dict) -> str | None:
        return None

    def is_auto_approved(self, arguments: dict, rules: set[str]) -> bool:
        return False
