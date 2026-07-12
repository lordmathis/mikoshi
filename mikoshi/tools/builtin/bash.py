import asyncio
import logging
import os
from typing import Any, Dict

from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)


class BashTools(ToolSetHandler):
    server_name = "bash"

    @tool(
        description="Execute a bash command in the workspace directory. Requires user approval before execution.",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
        require_approval=True,
    )
    async def execute(
        self,
        command: str,
        context: ToolCallContext,
        timeout: float = 30,
    ) -> Dict[str, Any]:
        """Execute a bash command and return the output"""
        try:
            if not context.workspace:
                return {
                    "success": False,
                    "error": "No workspace linked to this chat.",
                    "command": command,
                }

            working_dir = os.path.realpath(
                os.path.join(
                    context.workspace.data_dir,
                    "workspaces",
                    context.workspace.workspace_id,
                )
            )

            logger.info(f"Executing bash command in {working_dir}: {command}")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout} seconds",
                    "command": command,
                }

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            result: Dict[str, Any] = {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "command": command,
            }

            if process.returncode != 0:
                result["error"] = (
                    stderr_str
                    if stderr_str
                    else f"Command failed with return code {process.returncode}"
                )
                logger.warning(
                    f"Bash command failed: {command} (exit code: {process.returncode})"
                )
            else:
                logger.info(f"Bash command succeeded: {command}")

            return result

        except Exception as e:
            logger.error(f"Error executing bash command: {e}", exc_info=True)
            return {"success": False, "error": str(e), "command": command}
