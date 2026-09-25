import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mikoshi.config import MCPConfig, MCPType
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.handler_base import ToolHandler

logger = logging.getLogger(__name__)


def _extract_mcp_result(result: Any) -> Any:
    """Extract usable content from MCP CallToolResult.

    MCP returns CallToolResult with a content list of ContentBlock objects.
    This function extracts the actual data in a usable format.
    """
    if not hasattr(result, "content"):
        return result

    content = result.content

    # Handle single content block
    if len(content) == 1:
        block = content[0]

        if hasattr(block, "text"):
            try:
                parsed = json.loads(block.text)

                # Unwrap common MCP response patterns
                # Some MCP servers wrap their response in {'Result': ...}
                if isinstance(parsed, dict) and len(parsed) == 1 and "Result" in parsed:
                    logger.debug("Unwrapping MCP 'Result' wrapper")
                    return parsed["Result"]

                return parsed
            except (json.JSONDecodeError, TypeError):
                # Not JSON, return as plain text
                return block.text
        elif hasattr(block, "resource"):
            return block.resource

    # Handle multiple content blocks - return list of extracted content
    extracted = []
    for block in content:
        if hasattr(block, "text"):
            extracted.append(block.text)
        elif hasattr(block, "resource"):
            extracted.append(block.resource)
        else:
            extracted.append(str(block))

    return extracted


class MCPToolHandler(ToolHandler):
    """Handles a single MCP server connection and tool calls"""

    def __init__(
        self,
        server_name: str,
        config: MCPConfig,
        timeout: int,
        exit_stack: AsyncExitStack,
    ):
        self.server_name = server_name
        self._config = config
        self._timeout = timeout
        self._exit_stack = exit_stack
        self._session: Optional[ClientSession] = None

    async def initialize(self):
        """Connect to the MCP server and register its tools"""
        logger.info(f"Starting MCPToolHandler with server '{self.server_name}'")

        logger.info(
            f"Initializing MCP server '{self.server_name}' (type: {self._config.type})"
        )
        logger.debug(
            f"Server '{self.server_name}' - Command: {self._config.command}, Args: {self._config.args}"
        )
        if self._config.type == MCPType.STDIO:
            server_params = StdioServerParameters(
                command=self._config.command,
                args=self._config.args,
                env=self._config.env,
            )
        else:
            raise ValueError(f"Unsupported MCP type: {self._config.type}")

        logger.debug(f"Creating stdio client for '{self.server_name}'...")
        read_stream, write_stream = await asyncio.wait_for(
            self._exit_stack.enter_async_context(stdio_client(server_params)),
            timeout=self._timeout,
        )

        logger.debug(
            f"Connected to stdio client for '{self.server_name}', creating session..."
        )
        session = ClientSession(read_stream, write_stream)
        await asyncio.wait_for(
            self._exit_stack.enter_async_context(session), timeout=self._timeout
        )

        logger.debug(f"Initializing session for '{self.server_name}'...")
        await asyncio.wait_for(session.initialize(), timeout=self._timeout)

        logger.info(f"Session initialized successfully for '{self.server_name}'")
        self._session = session

        logger.debug(f"Listing tools for '{self.server_name}'...")
        tools_result = await asyncio.wait_for(
            session.list_tools(), timeout=self._timeout
        )
        for tool in tools_result.tools:
            logger.debug(f"Found tool in '{self.server_name}': {tool.name}")
            logger.debug(f"  Description: {tool.description}")
            logger.debug(f"  Parameters: {tool.input_schema}")
        logger.info(f"Successfully initialized MCP server '{self.server_name}'")

    async def call_tool(
        self, tool_name: str, arguments: dict, context: ToolCallContext
    ) -> Any:
        """Execute an MCP tool"""
        if self._session is None:
            logger.error(f"MCP session for server '{self.server_name}' not found")
            raise ValueError(f"MCP session for server '{self.server_name}' not found")

        logger.debug(
            f"Calling MCP tool '{self.server_name}__{tool_name}' with arguments: {arguments}"
        )
        raw_result = await asyncio.wait_for(
            self._session.call_tool(tool_name, arguments), timeout=self._timeout
        )

        # Extract usable content from MCP result
        extracted_result = _extract_mcp_result(raw_result)
        logger.debug(
            f"MCP tool '{self.server_name}__{tool_name}' returned: {type(extracted_result).__name__}"
        )

        return extracted_result

    async def list_tools(self) -> list:
        """List available tools from the MCP server"""
        if self._session is None:
            logger.error(f"MCP session for server '{self.server_name}' not found")
            raise ValueError(f"MCP session for server '{self.server_name}' not found")

        logger.debug(f"Listing tools for MCP server '{self.server_name}'")
        tools_result = await asyncio.wait_for(
            self._session.list_tools(), timeout=self._timeout
        )
        logger.debug(
            f"Found {len(tools_result.tools)} tools for MCP server '{self.server_name}'"
        )
        return tools_result.tools

    async def cleanup(self):
        """Clean up MCP session"""
        self._session = None
        logger.info(f"MCPToolHandler for server '{self.server_name}' cleaned up")
