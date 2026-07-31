"""Web tools: page summarization and web search.

Page fetching lives in :mod:`mikoshi.tools.builtin.scraper` (``WebFetcher``),
shared by ``summarize_website`` here and the standalone ``scraper`` tool server.
"""

import asyncio
import logging
import time

import httpx

from mikoshi.config import SearchConfig
from mikoshi.tools.builtin.scraper import WebFetcher
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)

SUMMARIZE_MAX_CHARS = 20000
SEARCH_INITIAL_BACKOFF = 5.0  # seconds before the first retry; doubles up to retry_max_backoff

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
        """Initialize WebTools with SearXNG search capabilities and a shared fetcher.

        Args:
            config: Search configuration (rate limit, retry budget, firecrawl, searxng url).
        """
        super().__init__()
        self._client = None
        self.max_results = config.max_results
        self.rate_limit = config.rate_limit
        self._min_interval = 1.0 / self.rate_limit if self.rate_limit else 0.0
        self._last_request_time = 0.0
        self.retry_timeout = config.retry_timeout
        self.retry_max_backoff = config.retry_max_backoff
        self._fetcher = WebFetcher(config.firecrawl_api_key, config.firecrawl_api_url)
        self._searxng_url = config.searxng_url

    async def initialize(self):
        """Set up HTTP client for search and initialize the shared page fetcher."""
        await super().initialize()
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgentKit/1.0)"},
        )
        await self._fetcher.initialize()

    async def cleanup(self):
        """Clean up HTTP client and fetcher."""
        if self._client:
            await self._client.aclose()
        await self._fetcher.cleanup()

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
            page = await self._fetcher.fetch_page(
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
            results = await self._search_with_retries(query)

            if not results:
                return (
                    f"No results found for '{query}'. The search engines may be "
                    "rate-limited or blocked by CAPTCHAs. Try rephrasing the "
                    "query or retrying in a moment."
                )

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

    async def _search_with_retries(self, query: str) -> list[dict]:
        """Query SearXNG, retrying until results arrive or the time budget runs out.
        """
        deadline = time.monotonic() + self.retry_timeout
        delay = SEARCH_INITIAL_BACKOFF
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.get(
                    f"{self._searxng_url}/search",
                    params={"q": query, "format": "json"},
                )
                response.raise_for_status()
                results = response.json().get("results", [])
                if results:
                    if attempt > 1:
                        logger.info(
                            "SearXNG search '%s' recovered after %d attempts",
                            query, attempt,
                        )
                    return results
                logger.info(
                    "SearXNG returned no results for '%s' (attempt %d); "
                    "engines may be suspended",
                    query, attempt,
                )
            except Exception as e:
                logger.warning(
                    "SearXNG request failed for '%s' (attempt %d): %s",
                    query, attempt, e,
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "SearXNG search '%s' exhausted retry budget after %d attempts",
                    query, attempt,
                )
                return []
            await asyncio.sleep(min(delay, self.retry_max_backoff, remaining))
            delay = min(delay * 2, self.retry_max_backoff)

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
