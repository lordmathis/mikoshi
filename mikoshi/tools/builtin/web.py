"""Web tools: page fetching, summarization, and web search.
"""

import asyncio
import logging
import os
import re
import time

import httpx
from bs4 import BeautifulSoup
from firecrawl import AsyncFirecrawl
from markdownify import markdownify as md

from mikoshi.config import SearchConfig
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 50000
SUMMARIZE_MAX_CHARS = 20000

SUMMARIZE_SYSTEM_PROMPT = """\
You are a helpful assistant. You are given the markdown content of a web page \
and a focus topic. Extract the information relevant to the focus and return a \
concise, well-structured markdown summary: key facts, numbers, claims, and named \
sources/authors. Omit navigation, boilerplate, and anything irrelevant to the \
focus. If the page has little relevant content, say so briefly.
"""


class WebTools(ToolSetHandler):
    server_name = "web"

    def __init__(self, config: SearchConfig):
        """Initialize WebTools with HTTP client and DuckDuckGo search capabilities.

        Args:
            max_results: Maximum number of search results to return (default: 10)
            rate_limit: Maximum queries per second for web search. Set to None to disable (default: 1.0)
        """
        super().__init__()
        self._client = None
        self.max_results = config.max_results
        self.rate_limit = config.rate_limit
        self._min_interval = 1.0 / self.rate_limit if self.rate_limit else 0.0
        self._last_request_time = 0.0
        self._firecrawl_api_key = config.firecrawl_api_key
        self._firecrawl_api_url = config.firecrawl_api_url
        self._firecrawl = None
        self._searxng_url = config.searxng_url

    async def initialize(self):
        """Set up HTTP client and DDGS client"""
        await super().initialize()
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgentKit/1.0)"},
        )
        if self._firecrawl_api_key:
            self._firecrawl = AsyncFirecrawl(
                api_key=self._firecrawl_api_key,
                api_url=self._firecrawl_api_url,
            )

    async def cleanup(self):
        """Clean up HTTP client"""
        if self._client:
            await self._client.aclose()

    async def fetch_page(
        self,
        url: str,
        include_links: bool = True,
        include_images: bool = False,
        max_chars: int | None = None,
    ) -> str:
        """Fetch a web page and convert HTML to clean markdown. Internal helper.

        Uses the Firecrawl scrape API when configured, falling back to the local
        httpx + BeautifulSoup pipeline on error or if FIRECRAWL_API_KEY is unset.

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
        """Scrape a URL via the Firecrawl API and return its markdown.
        """
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

    @tool(
        description=(
            "Fetch a web page and return a concise summary focused on a specific "
            "topic. Use this to read pages — it keeps the full content out of your "
            "context. This is the only way to read a page."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to summarize."},
                "focus": {
                    "type": "string",
                    "description": "What to extract from the page.",
                },
            },
            "required": ["url", "focus"],
        },
    )
    async def summarize_website(
        self, url: str, focus: str, context: ToolCallContext
    ) -> str:
        """Fetch a page (capped) and summarize it focused on `focus` via one LLM call."""
        try:
            page = await self.fetch_page(
                url,
                include_links=False,
                include_images=False,
                max_chars=SUMMARIZE_MAX_CHARS,
            )
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            return f"Error: Failed to fetch {url}: {e}"
        except Exception as e:
            logger.error(f"Error processing {url}: {e}", exc_info=True)
            return f"Error: Failed to process {url}: {e}"

        user_content = f"Focus: {focus}\n\nURL: {url}\n\nPage content:\n{page}"

        client = context.provider.get_llm_client()
        response = await client.chat_completion(
            model=context.model_id,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        summary = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            or ""
        )

        if not summary:
            return f"Error: Failed to summarize {url} (empty response)."
        return summary

    @tool(
        description="Performs a web search based on your query then returns the top search results.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to perform.",
                }
            },
            "required": ["query"],
        },
    )
    async def web_search(self, query: str) -> str:
        """Perform a web search and return formatted results.
        """
        try:
            await self._enforce_rate_limit()

            logger.info(f"Searching via SearXNG: {query}")
            response = await self._client.get(
                f"{self._searxng_url}/search",
                params={"q": query, "format": "json"},
            )
            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                return None

            postprocessed = [
                f"[{r.get('title', '')}]({r.get('url', '')})\n{r.get('content', '')}"
                for r in results[: self.max_results]
            ]
            logger.info(f"SearXNG search completed with {len(results)} results")
            return "## Search Results\n\n" + "\n\n".join(postprocessed)
        except Exception as e:
            logger.warning(
                f"SearXNG search failed for '{query}': {e}"
            )
            return f"Error performing search: {str(e)}"


    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between requests"""
        # No rate limit enforced
        if not self.rate_limit:
            return

        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _clean_markdown(self, text: str) -> str:
        """Clean up markdown text"""
        # Remove excessive newlines (more than 2)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove leading/trailing whitespace from each line
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Remove empty list items
        text = re.sub(r"\n[-*+]\s*\n", "\n", text)

        return text.strip()
