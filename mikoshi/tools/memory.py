"""Memory tool server: persistent semantic memory backed by Qdrant."""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from mikoshi.config import MemoryConfig
from mikoshi.tools.context import ToolCallContext
from mikoshi.tools.toolset_handler import ToolSetHandler, tool

logger = logging.getLogger(__name__)


class MemoryTools(ToolSetHandler):
    """Semantic memory over Qdrant with embeddings served via a Provider."""

    server_name = "memory"

    def __init__(self, config: Optional[MemoryConfig] = None):
        super().__init__()
        c = config or MemoryConfig()
        self._embed_provider = c.embed_provider
        self._embed_model = c.embed_model
        self._vector_size = c.vector_size
        self._qdrant_url = c.qdrant_url
        self._collection = c.collection
        self._client: Optional[AsyncQdrantClient] = None

    @property
    def _configured(self) -> bool:
        return bool(
            self._embed_provider and self._embed_model and self._vector_size
        )

    async def initialize(self) -> None:
        await super().initialize()
        if not self._configured:
            missing = [
                k
                for k, v in {
                    "embed_provider": self._embed_provider,
                    "embed_model": self._embed_model,
                    "vector_size": self._vector_size,
                }.items()
                if not v
            ]
            logger.warning(
                "MemoryTools not configured, skipping Qdrant setup: %s",
                ", ".join(missing),
            )
            return

        self._client = AsyncQdrantClient(url=self._qdrant_url)
        await self._ensure_collection()
        logger.info(
            "MemoryTools ready: qdrant=%s collection=%s dim=%d embed_provider=%s embed_model=%s",
            self._qdrant_url,
            self._collection,
            self._vector_size,
            self._embed_provider,
            self._embed_model,
        )

    async def _ensure_collection(self) -> None:
        """Create the Qdrant collection if missing. Raises on Qdrant failure."""
        if await self._client.collection_exists(self._collection):
            return
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(
                size=self._vector_size, distance=Distance.COSINE
            ),
        )
        logger.info(
            "created qdrant collection %s (dim=%d)",
            self._collection,
            self._vector_size,
        )

    async def cleanup(self) -> None:
        if self._client:
            await self._client.close()

    async def _embed(self, text: str) -> Optional[List[float]]:
        if not self._embed_provider or not self._embed_model:
            return None
        if not self._tool_manager:
            logger.error("MemoryTools: tool manager not set, cannot resolve provider")
            return None
        provider = self._tool_manager.get_provider(self._embed_provider)
        if provider is None:
            logger.error(
                "MemoryTools: embed provider '%s' not found", self._embed_provider
            )
            return None
        try:
            return await provider.get_llm_client().create_embedding(
                self._embed_model, text
            )
        except Exception as e:
            logger.error("embedding request failed: %s", e, exc_info=True)
            return None

    @tool(
        description=(
            "Save a piece of information to long-term semantic memory. The text is "
            "embedded and stored in a vector database so it can be retrieved later by "
            "meaning (not exact wording). Use this for facts, preferences, decisions, "
            "or anything worth recalling in future conversations. An optional category "
            "tags the memory for scoped retrieval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The content to remember.",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category/tag for the memory (e.g. 'preferences', 'people').",
                },
            },
            "required": ["text"],
        },
    )
    async def save_memory(
        self, text: str, category: Optional[str] = None, context: ToolCallContext = None
    ) -> Any:
        if not self._client:
            return "Error: memory not initialized (check memory config)."

        vec = await self._embed(text)
        if not vec:
            return "Error: failed to embed text."

        payload: Dict[str, Any] = {"text": text, "created_at": int(time.time())}
        if category:
            payload["category"] = category

        try:
            await self._client.upsert(
                collection_name=self._collection,
                points=[
                    PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload)
                ],
            )
        except Exception as e:
            logger.error("qdrant upsert failed: %s", e, exc_info=True)
            return f"Error: failed to save memory: {e}"

        logger.info(
            "saved memory (category=%s, chars=%d)", category or "(none)", len(text)
        )
        return {"status": "saved", "category": category or None, "chars": len(text)}

    @tool(
        description=(
            "Search long-term semantic memory for content relevant to a query. The "
            "query is embedded and matched against stored memories by meaning, returning "
            "the closest matches. Optionally restrict the search to a single category."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for in memory.",
                },
                "category": {
                    "type": "string",
                    "description": "Optional: only return memories tagged with this category.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    )
    async def search_memory(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
        context: ToolCallContext = None,
    ) -> Any:
        if not self._client:
            return "Error: memory not initialized (check memory config)."

        vec = await self._embed(query)
        if not vec:
            return "Error: failed to embed query."

        query_filter: Optional[Filter] = None
        if category:
            query_filter = Filter(
                must=[
                    FieldCondition(key="category", match=MatchValue(value=category))
                ]
            )

        try:
            response = await self._client.query_points(
                collection_name=self._collection,
                query=vec,
                query_filter=query_filter,
                limit=max(1, min(int(limit or 5), 50)),
            )
            hits = response.points
        except Exception as e:
            logger.error("qdrant search failed: %s", e, exc_info=True)
            return f"Error: failed to search memory: {e}"

        results = []
        for hit in hits:
            p = hit.payload or {}
            results.append(
                {
                    "text": p.get("text", ""),
                    "category": p.get("category"),
                    "score": hit.score,
                    "created_at": p.get("created_at"),
                }
            )
        return {"results": results, "count": len(results)}
