import inspect
import logging
from abc import ABC
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from mikoshi.tools.context import ToolCallContext

if TYPE_CHECKING:
    from mikoshi.tools.manager import ToolManager

logger = logging.getLogger(__name__)


class ToolDefinition(BaseModel):
    """Metadata for a tool function"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    func: Callable
    require_approval: bool = False


class ToolSetHandler(ABC):
    """Base class for function-based tool handlers"""

    server_name: str = ""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._tool_manager: Optional["ToolManager"] = None

    def set_tool_manager(self, tool_manager: "ToolManager") -> None:
        if self._tool_manager is None:
            self._tool_manager = tool_manager
        else:
            logger.warning(
                f"ToolManager already set for toolset '{self.server_name}', ignoring new value"
            )

    def get_persistent_storage(self):
        return self._tool_manager.get_persistent_storage(self.server_name)

    async def initialize(self) -> None:
        for _, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if not hasattr(method, "_tool_definition"):
                continue

            tool_def = method._tool_definition
            bound_tool_def = ToolDefinition(
                name=tool_def.name,
                description=tool_def.description,
                parameters=tool_def.parameters,
                func=method,
                require_approval=tool_def.require_approval,
            )
            self._tools[tool_def.name] = bound_tool_def
            logger.info(
                f"Registered tool '{tool_def.name}' in toolset '{self.server_name}'"
            )

    async def call_tool(
        self, tool_name: str, arguments: dict, context: ToolCallContext
    ) -> Any:
        tool_def = self._tools.get(tool_name)
        if not tool_def:
            raise ValueError(
                f"Tool '{tool_name}' not found in toolset '{self.server_name}'"
            )

        logger.debug(
            f"[{self.server_name}] Calling tool '{tool_name}' with arguments: {arguments}"
        )

        kwargs = dict(arguments)
        sig = inspect.signature(tool_def.func)
        if "context" in sig.parameters:
            kwargs["context"] = context

        if inspect.iscoroutinefunction(tool_def.func):
            result = await tool_def.func(**kwargs)
        else:
            result = tool_def.func(**kwargs)

        logger.debug(
            f"[{self.server_name}] Tool '{tool_name}' returned: type={type(result)}, value={result}"
        )
        return result

    async def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    async def cleanup(self) -> None:
        pass

    async def call_other_tool(
        self, call_name: str, arguments: dict, context: ToolCallContext
    ) -> Any:
        if not self._tool_manager:
            raise RuntimeError("ToolManager not set")

        logger.debug(f"[{self.server_name}] Calling {call_name}")

        result = await self._tool_manager.call_tool(call_name, arguments, context)
        return result


def tool(description: str, parameters: Dict[str, Any], require_approval: bool = False):
    """Decorator to mark a method as a tool

    Args:
        description: Description of what the tool does
        parameters: JSON Schema for parameters (auto-generated from type hints if not provided)
        require_approval: Whether the tool requires user approval before execution (default: False)
    """

    def decorator(func: Callable) -> Callable:
        func._tool_definition = ToolDefinition(
            name=func.__name__,
            description=description,
            parameters=parameters,
            func=func,
            require_approval=require_approval,
        )

        return func

    return decorator
