import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mikoshi.config import ConnectorsConfig, MCPConfig
from mikoshi.db.db import Database
from mikoshi.plugins import discover_plugins
from mikoshi.storage import get_persistent_storage
from mikoshi.tools.approval import PendingApproval, ToolDeniedError
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.handler_base import ToolHandler
from mikoshi.tools.mcp_handler import MCPToolHandler
from mikoshi.tools.toolset_handler import ToolSetHandler
from mikoshi.tools.workspace import WorkspaceToolSetHandler

logger = logging.getLogger(__name__)


def _parse_tool_name(call_name: str) -> tuple[str, str]:
    try:
        server_name, tool_name = call_name.split("__", 1)
    except ValueError:
        raise ValueError(
            f"Invalid tool name format: '{call_name}'. Expected 'server__tool'"
        )
    return server_name, tool_name


class ToolManager:
    def __init__(
        self,
        data_dir: str,
        tools_dir: str,
        servers: Dict[str, MCPConfig],
        connectors_config: Optional[Dict[str, ConnectorsConfig]] = None,
        mcp_timeout: int = 30,
        db: Optional[Database] = None,
    ):
        self._server_map: Dict[str, ToolHandler] = {}
        self._data_dir = data_dir
        self._tools_dir = tools_dir
        self._db = db
        self.mcp_timeout = mcp_timeout
        self.mcp_exit_stack = AsyncExitStack()
        self._pending_approvals: Dict[str, PendingApproval] = {}
        self._connectors_config = connectors_config or {}

        self._mcp_handlers: Dict[str, MCPToolHandler] = {}
        for server_name, config in servers.items():
            mcp_handler = MCPToolHandler(
                server_name, config, mcp_timeout, self.mcp_exit_stack
            )
            self._mcp_handlers[server_name] = mcp_handler

        self._toolset_handlers: Dict[
            str, ToolSetHandler
        ] = {}  # Store discovered toolset handlers

    def _discover_toolset_plugins(self) -> Dict[str, type]:
        return discover_plugins(
            self._tools_dir, ToolSetHandler, exclude_bases=(ToolSetHandler,)
        )

    def get_persistent_storage(self, tool_server_name):
        return get_persistent_storage(self._data_dir, tool_server_name)

    def get_connector_token(self, connector_name: str) -> str | None:
        cfg = self._connectors_config.get(connector_name)
        return cfg.token if cfg else None

    async def start(self):
        """Initialize all handlers"""
        logger.info("Starting ToolManager...")

        # Initialize MCPs
        for mcp_handler in self._mcp_handlers.values():
            try:
                await mcp_handler.initialize()
                self._server_map[mcp_handler.server_name] = mcp_handler
            except Exception as e:
                logger.error(
                    f"Error initializing MCP handler for server '{mcp_handler.server_name}': {e}",
                    exc_info=True,
                )

        # Discover and initialize toolset plugins
        plugin_classes = self._discover_toolset_plugins()
        for class_name, plugin_class in plugin_classes.items():
            try:
                # Instantiate the plugin
                plugin_instance = plugin_class()

                # Set tool_manager reference for cross-tool calls
                plugin_instance.set_tool_manager(self)

                await plugin_instance.initialize()

                # Register in both maps
                self._toolset_handlers[plugin_instance.server_name] = plugin_instance
                self._server_map[plugin_instance.server_name] = plugin_instance

                logger.info(
                    f"Successfully initialized toolset plugin '{class_name}' as '{plugin_instance.server_name}'"
                )
            except Exception as e:
                logger.error(
                    f"Error initializing toolset plugin '{class_name}': {e}",
                    exc_info=True,
                )

        # Register built-in workspace toolset
        try:
            workspace_handler = WorkspaceToolSetHandler()
            workspace_handler.set_tool_manager(self)
            await workspace_handler.initialize()
            self._toolset_handlers[workspace_handler.server_name] = workspace_handler
            self._server_map[workspace_handler.server_name] = workspace_handler
            logger.info("Initialized built-in workspace toolset")
        except Exception as e:
            logger.error(f"Failed to initialize workspace toolset: {e}", exc_info=True)

        logger.info("ToolManager initialization completed successfully")

    async def call_tool(
        self,
        call_name: str,
        arguments: dict,
        context: ToolCallContext,
    ) -> Any:
        """Route tool calls to the appropriate handler"""
        logger.info(
            "call_tool START name=%s chat_id=%s", call_name, context.chat_id
        )
        server_name, tool_name = _parse_tool_name(call_name)

        handler = self._server_map.get(server_name)
        if handler is None:
            raise ValueError(f"Tool server '{server_name}' not found")

        tool_def = self.get_tool_definition(call_name)
        if tool_def and tool_def.require_approval:
            logger.warning(f"Tool '{call_name}' requires approval - auto-denying")
            raise ToolDeniedError(call_name)

        logger.info(
            "call_tool EXECUTING %s via handler %s", call_name, type(handler).__name__
        )
        result = await handler.call_tool(tool_name, arguments, context)
        logger.info(
            "call_tool COMPLETE %s result_type=%s",
            call_name,
            type(result).__name__,
        )
        return result

    async def list_tools(self, server_name: str) -> list:
        """List available tools from a specific server"""
        if server_name in self._server_map:
            return await self._server_map[server_name].list_tools()
        else:
            logger.error(f"Server '{server_name}' not found in registry")
            raise ValueError(f"Unknown server '{server_name}'")

    async def list_tool_servers(self) -> list[str]:
        """List all registered tool servers"""
        return list(self._server_map.keys())

    def get_tool_definition(self, call_name: str):
        try:
            server_name, tool_name = _parse_tool_name(call_name)
        except ValueError:
            logger.warning(f"Invalid tool name format: '{call_name}'. Expected 'server__tool'")
            return None

        # Only ToolSetHandlers have tool definitions with require_approval
        handler = self._toolset_handlers.get(server_name)
        if handler is None:
            return None

        # Access the _tools dictionary directly
        tool_def = handler._tools.get(tool_name)
        return tool_def

    async def approve_tool(self, approval_id: str) -> Any:
        """Approve a pending tool call

        Args:
            approval_id: The id of the approval to approve

        Returns:
            The tool execution result
        """
        approval = self._pending_approvals.get(approval_id)
        if approval is None:
            raise ValueError(f"Approval {approval_id} not found")

        if self._db is not None:
            self._db.update_approval_status(approval_id, "approved")

        handler = self._server_map.get(_parse_tool_name(approval.tool_name)[0])
        if handler is None:
            raise ValueError(f"Tool server not found for {approval.tool_name}")

        tool_name = _parse_tool_name(approval.tool_name)[1]
        result = await handler.call_tool(
            tool_name, approval.arguments, approval.context
        )
        approval.future.set_result(result)
        return result

    async def deny_tool(self, approval_id: str) -> None:
        """Deny a pending tool call

        Args:
            approval_id: The id of the approval to deny
        """
        approval = self._pending_approvals.get(approval_id)
        if approval is None:
            raise ValueError(f"Approval {approval_id} not found")

        if self._db is not None:
            self._db.update_approval_status(approval_id, "denied")

        approval.future.set_result("denied")

    def list_pending_approvals(self, chat_id: str) -> List[dict]:
        """List pending approvals for a chat

        Args:
            chat_id: The chat id to filter by

        Returns:
            List of serializable approval dicts
        """
        return [
            {
                "id": a.approval_id,
                "chat_id": a.chat_id,
                "tool_name": a.tool_name,
                "arguments": a.arguments,
                "created_at": None,
            }
            for a in self._pending_approvals.values()
            if a.chat_id == chat_id
        ]

    async def stop(self):
        """Cleanup all handlers"""
        logger.info("Starting ToolManager cleanup...")

        # 1. Cleanup toolset handlers first
        for name, handler in list(self._toolset_handlers.items()):
            try:
                await handler.cleanup()
            except Exception as e:
                logger.error(
                    f"Error during cleanup of toolset handler '{name}': {e}",
                    exc_info=True,
                )

        # 2. Close the exit stack for MCP handlers
        try:
            logger.debug("Closing shared AsyncExitStack for all MCP handlers...")
            await asyncio.wait_for(
                self.mcp_exit_stack.aclose(), timeout=self.mcp_timeout
            )
            logger.info("Successfully closed all MCP connections")
        except asyncio.TimeoutError:
            logger.error("Timeout closing MCP connections")
        except Exception as e:
            logger.error(f"Error closing MCP connections: {e}", exc_info=True)

        # 3. Call cleanup on individual handlers (they just clear their references)
        for server_name, handler in list(self._mcp_handlers.items()):
            try:
                await handler.cleanup()
            except Exception as e:
                logger.error(
                    f"Error during cleanup of MCP handler '{server_name}': {e}",
                    exc_info=True,
                )

        # Clear all references
        self._server_map.clear()
        self._mcp_handlers.clear()
        self._toolset_handlers.clear()

        logger.info("ToolManager cleanup completed")
