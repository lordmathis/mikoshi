from unittest.mock import AsyncMock, patch

import pytest

from mikoshi.git import GitService, GitTimeout, auth_env, run_git


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


class TestAuthEnv:
    def test_token_not_in_argv(self):
        env = auth_env("sekrit")
        # The token (base64 of x-access-token:sekrit) must travel in env
        # values, never in a command-line argument.
        assert "GIT_CONFIG_COUNT" in env
        assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
        assert "Authorization: Basic" in env["GIT_CONFIG_VALUE_0"]

    @pytest.mark.asyncio
    async def test_run_git_overlays_env_and_keeps_path(self, tmp_path):
        # Real subprocess: proves git honors GIT_CONFIG_* env vars and that
        # the overlay doesn't strip PATH (git itself must stay invocable).
        rc, stdout, _ = await run_git(
            ["config", "--get", "http.extraHeader"],
            cwd=str(tmp_path),
            env=auth_env("tok"),
        )
        assert rc == 0
        assert stdout.strip().startswith("Authorization: Basic")

    @pytest.mark.asyncio
    async def test_https_origin_returns_auth_env(self):
        with patch(
            "mikoshi.git.run_git",
            new=AsyncMock(return_value=(0, "https://github.com/o/r\n", "")),
        ):
            env = await _svc().https_auth_env("tok")
        assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
        assert "Authorization: Basic" in env["GIT_CONFIG_VALUE_0"]

    @pytest.mark.asyncio
    async def test_ssh_origin_returns_empty(self):
        with patch(
            "mikoshi.git.run_git",
            new=AsyncMock(return_value=(0, "git@github.com:o/r.git\n", "")),
        ):
            assert await _svc().https_auth_env("tok") == {}

    @pytest.mark.asyncio
    async def test_no_token_returns_empty_without_git_call(self):
        with patch("mikoshi.git.run_git", new=AsyncMock()) as mock_run:
            assert await _svc().https_auth_env(None) == {}
            mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pull_passes_auth_env_through(self):
        captured = {}

        async def fake_run_git(args, cwd=None, env=None, timeout=30):
            captured["args"] = args
            captured["env"] = env
            return 0, "ok", ""

        with patch("mikoshi.git.run_git", side_effect=fake_run_git):
            result = await _svc().pull({"GIT_CONFIG_COUNT": "1"})
        assert result.success is True
        assert captured["args"] == ["pull"]
        assert captured["env"] == {"GIT_CONFIG_COUNT": "1"}


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
