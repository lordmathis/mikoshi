import base64
import logging
import os
import subprocess
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


@dataclass
class GitStatus:
    branch: str
    staged: int
    unstaged: int
    untracked: int


@dataclass
class GitResult:
    success: bool
    output: str


class GitService:
    def __init__(self, workspace_dir: str, workspace_id: str):
        self._dir = workspace_dir
        self._workspace_id = workspace_id

    def _run_git(
        self, args: list[str], timeout: int = 30, env: dict | None = None
    ) -> tuple[bool, str]:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=self._dir,
            timeout=timeout,
            env=env,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or f"exit code {result.returncode}"
        output = result.stdout.strip()
        return True, output if output else result.stderr.strip() or "(no output)"

    def status(self) -> GitStatus:
        ok, output = self._run_git(["status", "--porcelain"])
        if not ok:
            return GitStatus(branch="(unknown)", staged=0, unstaged=0, untracked=0)

        branch_ok, branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if not branch_ok:
            branch = "(unknown)"

        staged = 0
        unstaged = 0
        untracked = 0
        for line in output.splitlines():
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

        return GitStatus(branch=branch, staged=staged, unstaged=unstaged, untracked=untracked)

    def commit(
        self,
        message: str,
        git_user_name: str = "Mikoshi Agent",
        git_user_email: str = "agent@mikoshi",
    ) -> GitResult:
        ok, output = self._run_git(["add", "-A"])
        if not ok:
            return GitResult(False, f"Error staging files: {output}")

        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = git_user_name
        env["GIT_AUTHOR_EMAIL"] = git_user_email
        env["GIT_COMMITTER_NAME"] = git_user_name
        env["GIT_COMMITTER_EMAIL"] = git_user_email

        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            cwd=self._dir,
            env=env,
            timeout=30,
        )
        if result.returncode != 0:
            return GitResult(False, result.stderr.strip() or "nothing to commit")

        out = result.stdout.strip()
        return GitResult(True, out if out else result.stderr.strip() or "committed")

    def pull(self, auth_args: list[str] | None = None) -> GitResult:
        args = (auth_args or []) + ["pull"]
        ok, output = self._run_git(args, timeout=120)
        return GitResult(ok, output)

    def push(self, auth_args: list[str] | None = None) -> GitResult:
        args = (auth_args or []) + ["push"]
        ok, output = self._run_git(args, timeout=120)
        return GitResult(ok, output)
