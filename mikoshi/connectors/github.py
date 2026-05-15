import base64
import logging
from typing import Dict, List

import httpx

from mikoshi.config import ConnectorType
from mikoshi.connectors.client_base import ConnectorClient, FileNode, TokenEstimate

logger = logging.getLogger(__name__)

_GITHUB_DEFAULTS = {
    ConnectorType.GITHUB: {
        "base_url": "https://api.github.com",
        "auth_prefix": "Bearer",
        "accept": "application/vnd.github+json",
        "page_size": 100,
        "page_param": "per_page",
        "extra_list_params": {"sort": "updated", "affiliation": "owner,collaborator,organization_member"},
    },
    ConnectorType.FORGEJO: {
        "base_url": "https://codeberg.org/api/v1",
        "auth_prefix": "token",
        "accept": "application/json",
        "page_size": 50,
        "page_param": "limit",
        "extra_list_params": {},
    },
}


class GitHubClient(ConnectorClient):
    """Client for interacting with GitHub and Forgejo/Gitea REST APIs."""

    @property
    def type(self) -> str:
        return self._connector_type.value

    def __init__(
        self,
        token: str,
        connector_type: ConnectorType = ConnectorType.GITHUB,
        base_url: str | None = None,
    ):
        cfg = _GITHUB_DEFAULTS[connector_type]
        self._connector_type = connector_type
        self.token = token
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self._cfg = cfg
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"{cfg['auth_prefix']} {token}",
                "Accept": cfg["accept"],
            },
            timeout=30.0,
        )
        self._token_cache: Dict[tuple, int] = {}

    async def authenticate(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/user")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def list_repositories(self) -> List[Dict]:
        try:
            repos = []
            page = 1
            page_size = self._cfg["page_size"]
            page_param = self._cfg["page_param"]

            while True:
                params = {page_param: page_size, "page": page}
                params.update(self._cfg["extra_list_params"])
                response = await self.client.get(
                    f"{self.base_url}/user/repos", params=params
                )
                response.raise_for_status()
                page_repos = response.json()

                if not page_repos:
                    break

                repos.extend(page_repos)

                if len(page_repos) < page_size:
                    break

                page += 1

            return repos
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            raise

    async def browse_tree(self, repo: str, path: str = "") -> FileNode:
        try:
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            response = await self.client.get(url)
            response.raise_for_status()
            contents = response.json()

            if isinstance(contents, dict) and contents.get("type") == "file":
                return FileNode(
                    path=contents["path"],
                    name=contents["name"],
                    type="file",
                    size=contents.get("size"),
                )

            children = []
            for item in contents:
                child = FileNode(
                    path=item["path"],
                    name=item["name"],
                    type=item["type"] if item["type"] in ("file", "dir") else "file",
                    size=item.get("size"),
                )
                children.append(child)

            return FileNode(
                path=path,
                name=path.split("/")[-1] if path else repo.split("/")[-1],
                type="dir",
                children=children,
            )
        except Exception as e:
            logger.error(f"Failed to browse tree for {repo} at {path}: {e}")
            raise

    async def get_file_content(self, repo: str, path: str) -> bytes:
        try:
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            response = await self.client.get(url)
            response.raise_for_status()
            content_data = response.json()

            if "content" in content_data:
                encoded_content = content_data["content"]
                encoded_content = encoded_content.replace("\n", "")
                return base64.b64decode(encoded_content)
            else:
                raise ValueError(f"No content found for {path} in {repo}")
        except Exception as e:
            logger.error(f"Failed to get file content for {path} in {repo}: {e}")
            raise

    async def fetch_files(self, repo: str, paths: List[str]) -> Dict[str, str]:
        try:
            file_contents = {}

            for path in paths:
                url = f"{self.base_url}/repos/{repo}/contents/{path}"
                response = await self.client.get(url)
                response.raise_for_status()
                content_data = response.json()

                if "content" in content_data:
                    encoded_content = content_data["content"]
                    encoded_content = encoded_content.replace("\n", "")
                    decoded_content = base64.b64decode(encoded_content).decode("utf-8")
                    file_contents[path] = decoded_content
                else:
                    logger.warning(f"No content found for {path} in {repo}")

            return file_contents
        except Exception as e:
            logger.error(f"Failed to fetch files from {repo}: {e}")
            raise

    async def estimate_tokens(
        self, repo: str, paths: List[str], ref: str = "HEAD"
    ) -> TokenEstimate:
        try:
            if self._connector_type == ConnectorType.GITHUB:
                commits_url = f"{self.base_url}/repos/{repo}/commits/{ref}"
                commits_response = await self.client.get(commits_url)
            else:
                commits_url = f"{self.base_url}/repos/{repo}/commits"
                params = {"sha": ref} if ref != "HEAD" else {}
                commits_response = await self.client.get(commits_url, params=params)

            commits_response.raise_for_status()
            commit_data = commits_response.json()

            if isinstance(commit_data, list):
                commit_hash = commit_data[0]["sha"]
            else:
                commit_hash = commit_data["sha"]

            file_tokens = {}
            total_tokens = 0
            paths_to_fetch = []

            for path in paths:
                cache_key = (repo, commit_hash, path)

                if cache_key in self._token_cache:
                    tokens = self._token_cache[cache_key]
                    file_tokens[path] = tokens
                    total_tokens += tokens
                else:
                    paths_to_fetch.append(path)

            if paths_to_fetch:
                file_contents = await self.fetch_files(repo, paths_to_fetch)

                for path, content in file_contents.items():
                    tokens = len(content) // 4
                    file_tokens[path] = tokens
                    total_tokens += tokens

                    cache_key = (repo, commit_hash, path)
                    self._token_cache[cache_key] = tokens

            return TokenEstimate(total_tokens=total_tokens, files=file_tokens)
        except Exception as e:
            logger.error(f"Failed to estimate tokens for {repo}: {e}")
            raise

    async def close(self) -> None:
        await self.client.aclose()
