import base64
import fnmatch
import json
import logging
import mimetypes
import os
import re
import subprocess

from mikoshi.git import GitService, auth_header_value
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.edit_utils import EditError, apply_edits
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)

WORKSPACE_SERVER_NAME = "workspace"

MAX_READ_LINES = 2000
MAX_OUTPUT_BYTES = 50000
GREP_MATCH_LIMIT = 100
FIND_RESULT_LIMIT = 100
GREP_LINE_TRUNCATE = 500

def _workspace_result(summary: str, paths: list[str] | None = None) -> str:
    return json.dumps(
        {"__workspace": True, "summary": summary, "paths": paths or []}
    )


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".tiff",
    ".tif",
}


def _resolve_root(context: ToolCallContext) -> str:
    ws = context.workspace
    return os.path.realpath(os.path.join(ws.data_dir, "workspaces", ws.workspace_id))


def _resolve_path(root: str, path: str) -> str:
    full = os.path.realpath(os.path.join(root, path))
    if not full.startswith(root):
        raise ValueError("Path traversal detected")
    return full


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


def _has_git_repo(root: str) -> bool:
    return os.path.isdir(os.path.join(root, ".git"))


def _is_binary(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return True


def _is_image(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in IMAGE_EXTENSIONS


def _truncate_output(
    text: str,
    max_lines: int = MAX_READ_LINES,
    max_bytes: int = MAX_OUTPUT_BYTES,
) -> str:
    lines = text.split("\n")
    truncated = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    result = "\n".join(lines)
    encoded = result.encode("utf-8", errors="replace")
    if len(encoded) > max_bytes:
        result = encoded[:max_bytes].decode("utf-8", errors="replace")
        truncated = True
    if truncated:
        result += f"\n... (output truncated at {max_lines} lines / {max_bytes} bytes)"
    return result


def _collect_files(
    search_root: str, glob_pattern: str | None = None
) -> list[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(search_root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            if glob_pattern:
                rel = os.path.relpath(full_path, search_root)
                if not fnmatch.fnmatch(rel, glob_pattern) and not fnmatch.fnmatch(
                    filename, glob_pattern
                ):
                    continue
            files.append(full_path)
    return files


def _require_workspace(context: ToolCallContext) -> str:
    if not context.workspace:
        raise ValueError("No workspace linked to this chat.")
    return _resolve_root(context)


class WorkspaceToolSetHandler(ToolSetHandler):
    server_name = WORKSPACE_SERVER_NAME

    @tool(
        description="Read the contents of a file. Supports text files with optional line-based offset/limit, and image files (returns base64).",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed, inclusive). Defaults to 1.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Defaults to 2000.",
                },
            },
            "required": ["path"],
        },
    )
    def read(
        self,
        path: str,
        context: ToolCallContext,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        root = _require_workspace(context)
        try:
            full_path = _resolve_path(root, path)
        except ValueError as e:
            return f"Error: {e}"

        if not os.path.isfile(full_path):
            return f"Error: File not found: {path}"

        if _is_image(full_path):
            return self._read_image(full_path, path)

        if _is_binary(full_path):
            mime_type, _ = mimetypes.guess_type(full_path)
            size = os.path.getsize(full_path)
            return f"Binary file: {path} ({mime_type or 'unknown'}, {size} bytes). Use bash to inspect."

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except Exception as e:
            return f"Error reading file: {e}"

        start = (offset or 1) - 1
        if start < 0:
            start = 0
        line_limit = limit or MAX_READ_LINES

        selected = all_lines[start : start + line_limit]

        numbered = []
        for i, line in enumerate(selected):
            line_num = start + i + 1
            content = line.rstrip("\n")
            numbered.append(f"{line_num}: {content}")

        result = "\n".join(numbered)

        total_lines = len(all_lines)
        shown = len(selected)
        if start > 0 or shown < total_lines:
            end_line = start + shown
            result += f"\n(showing lines {start + 1}-{end_line} of {total_lines})"

        return _truncate_output(result)

    def _read_image(self, full_path: str, rel_path: str) -> str:
        mime_type, _ = mimetypes.guess_type(full_path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        try:
            size = os.path.getsize(full_path)
            with open(full_path, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode("ascii")
            return f"Image file: {rel_path} ({mime_type}, {size} bytes)\n[base64 data]\n{encoded}"
        except Exception as e:
            return f"Image file: {rel_path} ({mime_type}) — could not read: {e}"

    @tool(
        description="Create or overwrite a file entirely. Creates parent directories if needed. Use for new files or complete rewrites.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root",
                },
                "content": {
                    "type": "string",
                    "description": "Full content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    )
    def write(self, path: str, content: str, context: ToolCallContext) -> str:
        root = _require_workspace(context)
        try:
            full_path = _resolve_path(root, path)
        except ValueError as e:
            return f"Error: {e}"

        try:
            parent = os.path.dirname(full_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return _workspace_result(
                f"Wrote {len(content)} bytes ({line_count} lines) to {path}",
                paths=[path],
            )
        except Exception as e:
            return f"Error writing file: {e}"

    @tool(
        description="Apply targeted text replacements to a file. Multiple edits per call. Each oldText must match a unique region in the file. Falls back to fuzzy matching (normalizes whitespace, smart quotes, unicode dashes) if exact match fails.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root",
                },
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "oldText": {
                                "type": "string",
                                "description": "Text to find (must match a unique region in the file)",
                            },
                            "newText": {
                                "type": "string",
                                "description": "Replacement text",
                            },
                        },
                        "required": ["oldText", "newText"],
                    },
                    "description": "Array of edit operations. Each edit specifies oldText to find and newText to replace it with.",
                },
            },
            "required": ["path", "edits"],
        },
    )
    def edit(
        self,
        path: str,
        edits: list[dict],
        context: ToolCallContext,
    ) -> str:
        root = _require_workspace(context)
        try:
            full_path = _resolve_path(root, path)
        except ValueError as e:
            return f"Error: {e}"

        if not os.path.isfile(full_path):
            return f"Error: File not found: {path}"

        try:
            if not edits:
                return "Error: No edits provided"

            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()

            result, warnings = apply_edits(original, edits)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(result)

            old_lines = original.count("\n") + (
                1 if original and not original.endswith("\n") else 0
            )
            new_lines = result.count("\n") + (
                1 if result and not result.endswith("\n") else 0
            )

            msg = f"Applied {len(edits)} edit(s) to {path} ({old_lines} → {new_lines} lines)"
            if warnings:
                msg += "\n" + "\n".join(f"Note: {w}" for w in warnings)
            return _workspace_result(msg, paths=[path])

        except EditError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {e}"

    @tool(
        description="Search file contents using regex. Returns matching lines with file paths and line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in (relative to workspace root). Defaults to workspace root.",
                },
                "glob": {
                    "type": "string",
                    "description": "File pattern to include (e.g. '*.py', '*.{ts,tsx}')",
                },
                "ignoreCase": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default: false)",
                },
                "literal": {
                    "type": "boolean",
                    "description": "Treat pattern as a literal string, not regex (default: false)",
                },
                "contextLines": {
                    "type": "integer",
                    "description": "Number of context lines to show around each match (default: 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of matches to return (default: {GREP_MATCH_LIMIT})",
                },
            },
            "required": ["pattern"],
        },
    )
    def grep(
        self,
        pattern: str,
        context: ToolCallContext,
        path: str | None = None,
        glob: str | None = None,
        ignoreCase: bool = False,
        literal: bool = False,
        context_lines: int = 0,
        limit: int = GREP_MATCH_LIMIT,
    ) -> str:
        root = _require_workspace(context)

        if path:
            try:
                search_root = _resolve_path(root, path)
            except ValueError as e:
                return f"Error: {e}"
        else:
            search_root = root

        if not os.path.exists(search_root):
            return f"Error: Path not found: {path or '/'}"

        flags = 0
        if ignoreCase:
            flags |= re.IGNORECASE

        search_pattern = re.escape(pattern) if literal else pattern
        try:
            regex = re.compile(search_pattern, flags)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        if os.path.isfile(search_root):
            files = [search_root]
        else:
            files = _collect_files(search_root, glob)

        match_count = 0
        results: list[str] = []

        for fpath in files:
            if match_count >= limit:
                break
            if _is_binary(fpath):
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    file_lines = f.readlines()
            except Exception:
                continue

            rel_path = os.path.relpath(fpath, root)

            matched_indices: list[int] = []
            for i, line in enumerate(file_lines):
                if regex.search(line):
                    matched_indices.append(i)

            for mi in matched_indices:
                if match_count >= limit:
                    break
                match_count += 1

                if context_lines > 0:
                    start = max(0, mi - context_lines)
                    end = min(len(file_lines), mi + context_lines + 1)
                    block_parts: list[str] = []
                    for j in range(start, end):
                        ln = file_lines[j].rstrip("\n")
                        if len(ln) > GREP_LINE_TRUNCATE:
                            ln = ln[:GREP_LINE_TRUNCATE] + "..."
                        marker = ">" if j == mi else " "
                        block_parts.append(
                            f"{marker}{rel_path}:{j + 1}:{ln}"
                        )
                    results.append("\n".join(block_parts))
                else:
                    ln = file_lines[mi].rstrip("\n")
                    if len(ln) > GREP_LINE_TRUNCATE:
                        ln = ln[:GREP_LINE_TRUNCATE] + "..."
                    results.append(f"{rel_path}:{mi + 1}:{ln}")

        if not results:
            return "No matches found."

        output = "\n".join(results)
        if match_count >= limit:
            output += f"\n... (showing first {limit} matches)"

        return _truncate_output(output)

    @tool(
        description="Find files by glob pattern. Returns matching file paths relative to workspace root.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match file names (e.g. '*.py', '**/*.ts', 'test_*')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to workspace root). Defaults to workspace root.",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of results (default: {FIND_RESULT_LIMIT})",
                },
            },
            "required": ["pattern"],
        },
    )
    def find(
        self,
        pattern: str,
        context: ToolCallContext,
        path: str | None = None,
        limit: int = FIND_RESULT_LIMIT,
    ) -> str:
        root = _require_workspace(context)

        if path:
            try:
                search_root = _resolve_path(root, path)
            except ValueError as e:
                return f"Error: {e}"
        else:
            search_root = root

        if not os.path.isdir(search_root):
            return f"Error: Directory not found: {path or '/'}"

        results: list[str] = []
        search_pattern = pattern
        if "/" not in search_pattern:
            search_pattern = f"**/{search_pattern}"

        seen_dirs = set()
        for dirpath, dirnames, filenames in os.walk(search_root):
            if ".git" in dirnames:
                dirnames.remove(".git")

            for name in filenames + dirnames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, search_root)
                if fnmatch.fnmatch(rel, search_pattern):
                    is_dir = os.path.isdir(full)
                    display = os.path.relpath(full, root)
                    if is_dir:
                        display += "/"
                        abs_dir = os.path.abspath(full)
                        if abs_dir in seen_dirs:
                            continue
                        seen_dirs.add(abs_dir)
                    results.append(display)
                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        if not results:
            return f"No files matching '{pattern}' found."

        output = "\n".join(sorted(results, key=lambda s: s.lower()))
        if len(results) >= limit:
            output += f"\n... (showing first {limit} results)"

        return _truncate_output(output)

    @tool(
        description="List directory contents. Shows files and subdirectories. Directories are suffixed with '/'.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list (relative to workspace root). Defaults to workspace root.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return (default: 200)",
                },
            },
        },
    )
    def ls(
        self,
        context: ToolCallContext,
        path: str | None = None,
        limit: int = 200,
    ) -> str:
        root = _require_workspace(context)

        if path:
            try:
                target = _resolve_path(root, path)
            except ValueError as e:
                return f"Error: {e}"
        else:
            target = root

        if not os.path.isdir(target):
            return f"Error: Not a directory: {path or '/'}"

        entries: list[str] = []
        try:
            items = sorted(os.listdir(target), key=lambda s: s.lower())
        except PermissionError:
            return f"Error: Permission denied: {path or '/'}"

        for name in items:
            if name == ".git":
                continue
            full = os.path.join(target, name)
            if os.path.isdir(full):
                entries.append(f"{name}/")
            else:
                entries.append(name)
            if len(entries) >= limit:
                break

        if not entries:
            return "(empty directory)"

        output = "\n".join(entries)
        if len(entries) >= limit:
            output += f"\n... (showing first {limit} entries)"

        return output

    def _get_git_service(self, context: ToolCallContext) -> GitService:
        root = _require_workspace(context)
        return GitService(root, context.workspace.workspace_id)

    def _get_auth_git_args(self, context: ToolCallContext) -> list[str]:
        if not context.workspace:
            return []
        ws = context.workspace
        token = None
        if ws.connector and self._tool_manager:
            token = self._tool_manager.get_connector_token(ws.connector)
        if not token:
            return []

        root = _resolve_root(context)
        url_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if not url_result.stdout.strip().startswith("https://"):
            return []

        return ["-c", f"http.extraHeader={auth_header_value(token)}"]

    @tool(
        description="Show the git status of the workspace.",
        parameters={
            "type": "object",
            "properties": {},
        },
    )
    def git_status(self, context: ToolCallContext) -> str:
        root = _require_workspace(context)
        if not _has_git_repo(root):
            return "No git repository in this workspace."
        return _run_git(root, ["status", "--porcelain"])

    @tool(
        description="Show the unstaged diff of the workspace.",
        parameters={
            "type": "object",
            "properties": {},
        },
    )
    def git_diff(self, context: ToolCallContext) -> str:
        root = _require_workspace(context)
        if not _has_git_repo(root):
            return "No git repository in this workspace."
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
    )
    def git_commit(self, message: str, context: ToolCallContext) -> str:
        if not context.workspace:
            return "Error: No workspace linked to this chat."
        root = _resolve_root(context)
        if not _has_git_repo(root):
            return "No git repository in this workspace."
        svc = self._get_git_service(context)
        ws = context.workspace
        result = svc.commit(message, ws.git_user_name, ws.git_user_email)
        if not result.success:
            return f"Error committing: {result.output}"

        hash_ok, commit_hash = svc._run_git(["rev-parse", "HEAD"])
        return f"Committed as {commit_hash}" if hash_ok else result.output

    @tool(
        description="Pull latest changes from the remote repository.",
        parameters={
            "type": "object",
            "properties": {},
        },
    )
    def git_pull(self, context: ToolCallContext) -> str:
        root = _require_workspace(context)
        if not _has_git_repo(root):
            return "No git repository in this workspace."
        svc = self._get_git_service(context)
        auth_args = self._get_auth_git_args(context)
        result = svc.pull(auth_args)
        if not result.success:
            return result.output
        return _workspace_result(result.output)

    @tool(
        description="Push commits to the remote repository.",
        parameters={
            "type": "object",
            "properties": {},
        },
    )
    def git_push(self, context: ToolCallContext) -> str:
        root = _require_workspace(context)
        if not _has_git_repo(root):
            return "No git repository in this workspace."
        svc = self._get_git_service(context)
        auth_args = self._get_auth_git_args(context)
        result = svc.push(auth_args)
        return result.output
