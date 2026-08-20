from unittest.mock import AsyncMock, patch

import pytest

from mikoshi.git import GitService, GitTimeout


def _svc() -> GitService:
    return GitService("/tmp/ws", "ws")


class TestRunGitMethod:
    @pytest.mark.asyncio
    async def test_success_returns_stdout(self):
        with patch("mikoshi.git.run_git", new=AsyncMock(return_value=(0, "out\n", ""))):
            assert await _svc()._run_git(["status"]) == (True, "out")

    @pytest.mark.asyncio
    async def test_failure_returns_stderr(self):
        with patch(
            "mikoshi.git.run_git", new=AsyncMock(return_value=(1, "", "boom\n"))
        ):
            assert await _svc()._run_git(["push"]) == (False, "boom")

    @pytest.mark.asyncio
    async def test_timeout_returned_as_error(self):
        with patch(
            "mikoshi.git.run_git",
            new=AsyncMock(side_effect=GitTimeout("git pull timed out")),
        ):
            ok, output = await _svc()._run_git(["pull"])
            assert ok is False
            assert "timed out" in output

    @pytest.mark.asyncio
    async def test_empty_output_falls_back_to_stderr(self):
        with patch("mikoshi.git.run_git", new=AsyncMock(return_value=(0, "", "note"))):
            assert await _svc()._run_git(["x"]) == (True, "note")


class TestHttpsAuthArgs:
    @pytest.mark.asyncio
    async def test_https_origin_returns_auth_args(self):
        with patch(
            "mikoshi.git.run_git",
            new=AsyncMock(return_value=(0, "https://github.com/o/r\n", "")),
        ):
            args = await _svc().https_auth_args("tok")
        assert args[0] == "-c"
        assert "Authorization: Basic" in args[1]

    @pytest.mark.asyncio
    async def test_ssh_origin_returns_empty(self):
        with patch(
            "mikoshi.git.run_git",
            new=AsyncMock(return_value=(0, "git@github.com:o/r.git\n", "")),
        ):
            assert await _svc().https_auth_args("tok") == []

    @pytest.mark.asyncio
    async def test_no_token_returns_empty_without_git_call(self):
        with patch("mikoshi.git.run_git", new=AsyncMock()) as mock_run:
            assert await _svc().https_auth_args(None) == []
            mock_run.assert_not_awaited()


class TestStatusParsing:
    @pytest.mark.asyncio
    async def test_porcelain_counts(self):
        outputs = {
            ("status", "--porcelain"): (0, "M  a.py\n?? b.py\n M c.py\n", ""),
            ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main", ""),
        }

        async def fake_run_git(args, cwd=None, env=None, timeout=30):
            return outputs[tuple(args)]

        with patch("mikoshi.git.run_git", side_effect=fake_run_git):
            status = await _svc().status()

        assert status.branch == "main"
        assert status.staged == 1
        assert status.unstaged == 1
        assert status.untracked == 1

    @pytest.mark.asyncio
    async def test_failure_returns_unknown(self):
        with patch("mikoshi.git.run_git", new=AsyncMock(return_value=(128, "", "err"))):
            status = await _svc().status()
        assert status.branch == "(unknown)"
