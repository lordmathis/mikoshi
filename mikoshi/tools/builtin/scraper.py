"""Shared web page fetching logic and the raw scraper tool server.

``WebFetcher`` owns the httpx/Firecrawl pipeline that turns a URL into clean
markdown. ``ScraperTools`` exposes it as a standalone tool server (``scraper``)
so other tools can fetch raw page content via ``call_other_tool`` without the
capability being visible to agents (agents only see servers listed in their
``tool_servers``).
"""

import logging
import re

import httpx
from bs4 import BeautifulSoup
from firecrawl import AsyncFirecrawl
from markdownify import markdownify as md

from mikoshi.config import SearchConfig
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 50000


class WebFetcher:
    """Fetch web pages and convert HTML to clean markdown.

    Uses the Firecrawl scrape API when configured, falling back to the local
    httpx + BeautifulSoup pipeline on error or if no API key is set.
    """

    def __init__(self, firecrawl_api_key=None, firecrawl_api_url=None):
        self._firecrawl_api_key = firecrawl_api_key
        self._firecrawl_api_url = firecrawl_api_url
        self._client = None
        self._firecrawl = None

    async def initialize(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible, AgentKit/1.0)"},
        )
        if self._firecrawl_api_key:
            self._firecrawl = AsyncFirecrawl(
                api_key=self._firecrawl_api_key,
                api_url=self._firecrawl_api_url,
            )

    async def cleanup(self):
        if self._client:
            await self._client.aclose()

    async def fetch_page(
        self,
        url: str,
        include_links: bool = True,
        include_images: bool = False,
        max_chars: int | None = None,
    ) -> str:
        """Fetch a web page and convert HTML to clean markdown.

        Raises httpx.HTTPError (or other exceptions) on failure; callers handle.
        """
        markdown_text = None

        if self._firecrawl:
            markdown_text = await self._firecrawl_scrape(url)

        if markdown_text is None:
            markdown_text = await self._bs4_fetch(url)

        if not include_images:
            markdown_text = re.sub(r"!\[.*?\]\(.*?\)", "", markdown_text)

        if not include_links:
            markdown_text = re.sub(
                r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown_text
            )

        markdown_text = self._clean_markdown(markdown_text)

        limit = max_chars if max_chars is not None else DEFAULT_MAX_CHARS
        if len(markdown_text) > limit:
            markdown_text = (
                markdown_text[:limit]
                + f"\n\n[... truncated: {len(markdown_text)} total chars, "
                f"showing first {limit} ...]"
            )

        logger.info(
            f"Successfully fetched and converted {url} ({len(markdown_text)} characters)"
        )
        return f"# Content from {url}\n\n{markdown_text}"

    async def _firecrawl_scrape(self, url: str) -> str | None:
        """Scrape a URL via the Firecrawl API and return its markdown."""
        try:
            logger.info(f"Scraping URL via Firecrawl: {url}")
            document = await self._firecrawl.scrape(
                url, formats=["markdown"], only_main_content=True
            )
            markdown_text = getattr(document, "markdown", None)
            if not markdown_text:
                logger.warning(f"Firecrawl returned no markdown for {url}")
                return None
            return markdown_text
        except Exception as e:
            logger.warning(
                f"Firecrawl scrape failed for {url}: {e}; falling back to local fetch"
            )
            return None

    async def _bs4_fetch(self, url: str) -> str:
        """Fetch a page with httpx and convert HTML to markdown via BeautifulSoup."""
        logger.info(f"Fetching URL (local): {url}")
        response = await self._client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        for comment in soup.find_all(
            string=lambda text: (
                isinstance(text, str) and text.strip().startswith("<!--")
            )
        ):
            comment.extract()

        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=lambda c: c and "content" in c.lower())
            or soup.body
            or soup
        )

        return md(
            str(main_content),
            heading_style="ATX",
            bullets="-",
            escape_asterisks=False,
            escape_underscores=False,
        )

    def _clean_markdown(self, text: str) -> str:
        """Clean up markdown text"""
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        text = re.sub(r"\n[-*+]\s*\n", "\n", text)
        return text.strip()


class ScraperTools(ToolSetHandler):
    """Raw page-fetch tool server. Not added to any agent's ``tool_servers``."""

    server_name = "scraper"

    def __init__(self, config: SearchConfig):
        super().__init__()
        self._fetcher = WebFetcher(config.firecrawl_api_key, config.firecrawl_api_url)

    async def initialize(self):
        await super().initialize()
        await self._fetcher.initialize()

    async def cleanup(self):
        await self._fetcher.cleanup()

    @tool(
        description=(
            "Fetch a web page and return its full content as markdown. "
            "Intended to be called by other tools, not directly by agents."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch."},
                "include_links": {
                    "type": "boolean",
                    "description": "Keep markdown links in the output (default true).",
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Keep markdown images in the output (default false).",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default 50000).",
                },
            },
            "required": ["url"],
        },
    )
    async def fetch_page(
        self,
        url: str,
        include_links: bool = True,
        include_images: bool = False,
        max_chars: int | None = None,
    ) -> str:
        try:
            return await self._fetcher.fetch_page(
                url, include_links, include_images, max_chars
            )
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            return f"Error: Failed to fetch {url}: {e}"
        except Exception as e:
            logger.error(f"Error processing {url}: {e}", exc_info=True)
            return f"Error: Failed to process {url}: {e}"
