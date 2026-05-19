import logging
from typing import List

from mikoshi.connectors.github import GitHubClient

logger = logging.getLogger(__name__)


class ForgejoClient(GitHubClient):
    """Client for interacting with Forgejo/Gitea REST APIs."""

    @property
    def type(self) -> str:
        return "forgejo"

    def __init__(self, token: str, base_url: str):
        super().__init__(token=token, base_url=base_url)
        self.client.headers["Accept"] = "application/json"
        self._extra_list_params = {}

    async def _resolve_commit_hash(self, repo: str, ref: str) -> str:
        commits_url = f"{self.base_url}/repos/{repo}/commits"
        params = {"sha": ref} if ref != "HEAD" else {}
        response = await self.client.get(commits_url, params=params)
        response.raise_for_status()
        commit_data = response.json()
        if isinstance(commit_data, list):
            return commit_data[0]["sha"]
        return commit_data["sha"]
