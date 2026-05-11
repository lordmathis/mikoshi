import logging
import os
import subprocess

from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)

WORKSPACE_SERVER_NAME = "workspace"


def _resolve_root(context: ToolCallContext) -> str:
    ws = context.workspace
    return os.path.realpath(os.path.join(ws.data_dir, "workspaces", ws.workspace_id))


def _run_git(cwd: str, args: list[str], timeout: int = 30) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )
    if result.returncode != 0:
        return f"Error (exit {result.returncode}): {result.stderr.strip()}"
    output = result.stdout.strip()
    return output if output else result.stderr.strip() or "(no output)"


class WorkspaceToolSetHandler(ToolSetHandler):
    server_name = WORKSPACE_SERVER_NAME

    @tool(
        description="Read the contents of a file in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root",
                },
            },
            "required": ["path"],
        },
        require_approval=False,
    )
    def read_file(self, path: str, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        root = _resolve_root(context)
        full_path = os.path.realpath(os.path.join(root, path))

        if not full_path.startswith(root):
            return "Error: Path traversal detected."
        if not os.path.isfile(full_path):
            return f"Error: File not found: {path}"
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    @tool(
        description="Write content to a file in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
        require_approval=False,
    )
    def write_file(self, path: str, content: str, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        root = _resolve_root(context)
        full_path = os.path.realpath(os.path.join(root, path))
        if not full_path.startswith(root):
            return "Error: Path traversal detected."
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    @tool(
        description="List all files in the workspace.",
        parameters={
            "type": "object",
            "properties": {},
        },
        require_approval=False,
    )
    def list_files(self, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        root = _resolve_root(context)
        if not os.path.isdir(root):
            return "Error: Workspace directory not found."
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            if ".git" in dirnames:
                dirnames.remove(".git")
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)
                files.append(rel_path)
        return "\n".join(sorted(files)) if files else "(empty workspace)"

    @tool(
        description="Show the git status of the workspace.",
        parameters={
            "type": "object",
            "properties": {},
        },
        require_approval=False,
    )
    def git_status(self, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        root = _resolve_root(context)
        return _run_git(root, ["status", "--porcelain"])

    @tool(
        description="Show the unstaged diff of the workspace.",
        parameters={
            "type": "object",
            "properties": {},
        },
        require_approval=False,
    )
    def git_diff(self, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        root = _resolve_root(context)
        return _run_git(root, ["diff"])

    @tool(
        description="Stage all changes and commit with a message.",
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
            },
            "required": ["message"],
        },
        require_approval=False,
    )
    def git_commit(self, message: str, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        ws = context.workspace
        root = _resolve_root(context)

        result = subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if result.returncode != 0:
            return f"Error staging files: {result.stderr.strip()}"

        commit_env = os.environ.copy()
        commit_env["GIT_AUTHOR_NAME"] = ws.git_user_name
        commit_env["GIT_AUTHOR_EMAIL"] = ws.git_user_email
        commit_env["GIT_COMMITTER_NAME"] = ws.git_user_name
        commit_env["GIT_COMMITTER_EMAIL"] = ws.git_user_email

        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            cwd=root,
            env=commit_env,
        )
        if result.returncode != 0:
            return f"Error committing: {result.stderr.strip()}"

        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        commit_hash = hash_result.stdout.strip()
        return f"Committed as {commit_hash}"

    @tool(
        description="Push commits to the remote repository.",
        parameters={
            "type": "object",
            "properties": {},
        },
        require_approval=False,
    )
    def git_push(self, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        ws = context.workspace
        root = _resolve_root(context)

        url_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        original_url = url_result.stdout.strip()

        token = None
        if ws.connector and self._tool_manager:
            token = self._tool_manager.get_connector_token(ws.connector)

        if token and original_url.startswith("https://"):
            auth_url = original_url.replace(
                "https://", f"https://x-access-token:{token}@"
            )
            subprocess.run(
                ["git", "remote", "set-url", "origin", auth_url],
                capture_output=True,
                cwd=root,
            )

        try:
            return _run_git(root, ["push"], timeout=120)
        finally:
            if token and original_url.startswith("https://"):
                subprocess.run(
                    ["git", "remote", "set-url", "origin", original_url],
                    capture_output=True,
                    cwd=root,
                )
