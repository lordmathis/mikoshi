import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def auth_header_value(token: str) -> str:
    """Build an `Authorization` header value for git-over-HTTPS.

    GitHub's git smart-HTTP endpoint requires HTTP Basic auth with the
    token as the password. The username is ignored by GitHub but must be
    present, otherwise GitHub responds with "invalid credentials".
    """
    raw = f"x-access-token:{token}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"Authorization: Basic {encoded}"


def auth_env(token: str) -> dict[str, str]:
    """Git config for HTTPS token auth, passed via the environment.

    Equivalent to `git -c http.extraHeader=...`, but env vars are only
    readable by the owning user, unlike `/proc/<pid>/cmdline` which is
    world-readable.
    """
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": auth_header_value(token),
    }


class GitTimeout(Exception):
    """git subprocess exceeded its timeout and was killed."""


async def run_git(
    args: list[str],
    cwd: str | None = None,
    env: dict | None = None,
    timeout: float = 30,
) -> tuple[int, str, str]:
    """Run git asynchronously. Returns (returncode, stdout, stderr).

    ``env`` entries are overlaid on the current environment, not a
    replacement for it.
    """
    if env:
        full_env = os.environ.copy()
        full_env.update(env)
        env = full_env
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise GitTimeout(f"git {args[0]} timed out after {timeout}s")
    return (
        proc.returncode or 0,
        stdout_b.decode(errors="replace"),
        stderr_b.decode(errors="replace"),
    )


@dataclass
class GitStatus:
    branch: str
    staged: int
    unstaged: int
    untracked: int
    ahead: int | None = None
    behind: int | None = None


def _parse_status_header(header: str) -> tuple[str, int | None, int | None]:
    """Parse the `## ...` line of `git status --porcelain -b`.

    Returns (branch, ahead, behind). ahead/behind are None when there is
    no upstream to compare against, including `[gone]` and detached HEAD.
    """
    if not header.startswith("## "):
        return "(unknown)", None, None
    rest = header[3:]
    if rest.startswith("No commits yet on "):
        return rest[len("No commits yet on ") :], None, None
    if rest.startswith("HEAD (no branch)"):
        return "HEAD", None, None

    branch, _, upstream = rest.partition("...")
    ahead: int | None = None
    behind: int | None = None
    if upstream:
        if "[gone]" in upstream:
            return branch, None, None
        ahead = 0
        behind = 0
        match = re.search(r"ahead (\d+)", upstream)
        if match:
            ahead = int(match.group(1))
        match = re.search(r"behind (\d+)", upstream)
        if match:
            behind = int(match.group(1))
    return branch, ahead, behind


@dataclass
class GitResult:
    success: bool
    output: str
    head_hash: str | None = None


class GitService:
    def __init__(self, workspace_dir: str, workspace_id: str):
        self._dir = workspace_dir
        self._workspace_id = workspace_id

    async def _run_git(
        self, args: list[str], timeout: int = 30, env: dict | None = None
    ) -> tuple[bool, str]:
        try:
            rc, stdout, stderr = await run_git(
                args, cwd=self._dir, env=env, timeout=timeout
            )
        except GitTimeout as e:
            return False, str(e)
        if rc != 0:
            return False, stderr.strip() or f"exit code {rc}"
        output = stdout.strip()
        return True, output if output else stderr.strip() or "(no output)"

    async def https_auth_env(self, token: str | None) -> dict[str, str]:
        """Env vars for HTTPS token auth, if the origin remote is https."""
        if not token:
            return {}
        ok, url = await self._run_git(["remote", "get-url", "origin"], timeout=10)
        if ok and url.startswith("https://"):
            return auth_env(token)
        return {}

    async def status(self) -> GitStatus:
        ok, output = await self._run_git(["status", "--porcelain", "-b"])
        if not ok:
            return GitStatus(branch="(unknown)", staged=0, unstaged=0, untracked=0)

        lines = output.splitlines()
        branch, ahead, behind = _parse_status_header(lines[0] if lines else "")

        staged = 0
        unstaged = 0
        untracked = 0
        for line in lines[1:]:
            if not line:
                continue
            x = line[0]
            y = line[1] if len(line) > 1 else " "
            if x == "?" and y == "?":
                untracked += 1
            else:
                if x in ("M", "A", "D", "R", "C"):
                    staged += 1
                if y in ("M", "D"):
                    unstaged += 1

        return GitStatus(
            branch=branch,
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            ahead=ahead,
            behind=behind,
        )

    async def status_porcelain(self) -> str:
        """Raw `git status --porcelain` output (or the error message)."""
        return (await self._run_git(["status", "--porcelain"]))[1]

    async def diff(self) -> str:
        """Raw `git diff` output (or the error message)."""
        return (await self._run_git(["diff"]))[1]

    async def commit(
        self,
        message: str,
        git_user_name: str = "Mikoshi Agent",
        git_user_email: str = "agent@mikoshi",
    ) -> GitResult:
        ok, output = await self._run_git(["add", "-A"])
        if not ok:
            return GitResult(False, f"Error staging files: {output}")

        env = {
            "GIT_AUTHOR_NAME": git_user_name,
            "GIT_AUTHOR_EMAIL": git_user_email,
            "GIT_COMMITTER_NAME": git_user_name,
            "GIT_COMMITTER_EMAIL": git_user_email,
        }

        ok, output = await self._run_git(["commit", "-m", message], env=env)
        head_hash = None
        if ok:
            _, head_hash = await self._run_git(["rev-parse", "HEAD"])
        return GitResult(ok, output, head_hash)

    async def pull(self, auth_env_vars: dict[str, str] | None = None) -> GitResult:
        ok, output = await self._run_git(["pull"], timeout=120, env=auth_env_vars)
        return GitResult(ok, output)

    async def push(self, auth_env_vars: dict[str, str] | None = None) -> GitResult:
        ok, output = await self._run_git(["push"], timeout=120, env=auth_env_vars)
        return GitResult(ok, output)
