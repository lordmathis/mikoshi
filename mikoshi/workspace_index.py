"""Per-workspace semantic file index backed by Qdrant.

Re-embedding is event-driven: mutation sites call the sync notify methods,
which spawn debounced tasks. Qdrant point payloads are the only state store
— a full sync at startup rebuilds everything if Qdrant is wiped.
"""

import asyncio
import fnmatch
import hashlib
import json
import logging
import os
import re
import uuid
from typing import Optional

from openinference.semconv.trace import SpanAttributes
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from mikoshi.config import WorkspaceIndexConfig
from mikoshi.observability import start_retriever_span
from mikoshi.providers.registry import ProviderRegistry
from mikoshi.workspace import is_binary_file, walk_files

logger = logging.getLogger(__name__)

WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

EMBED_BATCH_SIZE = 32
SCROLL_PAGE_LIMIT = 256
DEBOUNCE_SECONDS = 0.5


def chunk_text(
    text: str, chunk_chars: int, overlap_chars: int
) -> list[tuple[int, str]]:
    """Split text into (start_line, chunk) pairs on line boundaries.

    Chunks hold complete lines up to ``chunk_chars``; the next chunk is
    seeded with trailing lines of the previous one totaling <= overlap_chars.
    A single line longer than ``chunk_chars`` is hard-split into slices.
    """
    if not text.strip():
        return []

    chunks: list[tuple[int, str]] = []
    current: list[str] = []
    current_start = 1

    for line_no, line in enumerate(text.split("\n"), start=1):
        if len(line) > chunk_chars:
            if current:
                chunks.append((current_start, "\n".join(current)))
                current = []
            for offset in range(0, len(line), chunk_chars):
                chunks.append((line_no, line[offset : offset + chunk_chars]))
            current_start = line_no + 1
            continue

        added = len(line) + (1 if current else 0)
        if current and current_len(current) + added > chunk_chars:
            chunks.append((current_start, "\n".join(current)))
            current = trailing_lines(current, overlap_chars)
            current_start = line_no - len(current)
            added = len(line) + (1 if current else 0)
        if not current:
            current_start = line_no
        current.append(line)

    if current:
        chunks.append((current_start, "\n".join(current)))
    return chunks


def current_len(lines: list[str]) -> int:
    return sum(len(line) for line in lines) + max(0, len(lines) - 1)


def trailing_lines(lines: list[str], overlap_chars: int) -> list[str]:
    taken: list[str] = []
    total = 0
    for line in reversed(lines):
        if total + len(line) > overlap_chars:
            break
        taken.insert(0, line)
        total += len(line)
    return taken


class WorkspaceIndexer:
    def __init__(
        self,
        cfg: WorkspaceIndexConfig,
        workspaces_dir: str,
        provider_registry: ProviderRegistry,
        client: Optional[AsyncQdrantClient] = None,
    ):
        self._cfg = cfg
        self._workspaces_dir = workspaces_dir
        self._registry = provider_registry
        self._qdrant: Optional[AsyncQdrantClient] = client
        self._gen: dict[tuple[str, str], int] = {}
        self._tasks: set[asyncio.Task] = set()
        self._debounce_seconds = DEBOUNCE_SECONDS

        self._enabled = bool(
            cfg.embed_provider
            and cfg.embed_model
            and cfg.vector_size
            and cfg.qdrant_url
        )
        if not self._enabled:
            missing = [
                key
                for key, value in {
                    "embed_provider": cfg.embed_provider,
                    "embed_model": cfg.embed_model,
                    "vector_size": cfg.vector_size,
                    "qdrant_url": cfg.qdrant_url,
                }.items()
                if not value
            ]
            logger.warning(
                "workspace index partially configured, feature disabled — missing: %s",
                ", ".join(missing),
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _get_client(self) -> AsyncQdrantClient:
        if self._qdrant is None:
            self._qdrant = AsyncQdrantClient(url=self._cfg.qdrant_url)
        return self._qdrant

    def _spawn(self, coro) -> None:
        async def runner():
            try:
                await coro
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("workspace index task failed", exc_info=True)

        loop = asyncio.get_running_loop()
        task = loop.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _wait_for_tasks(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks))

    def notify_changed(self, workspace_id: str, path: str) -> None:
        if not self._enabled:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        gen = self._bump_gen(workspace_id, path)
        self._spawn(self._reindex_after_debounce(workspace_id, path, gen))
        logger.info("workspace index: change queued %s/%s", workspace_id, path)

    def notify_deleted(self, workspace_id: str, path: str) -> None:
        if not self._enabled:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        gen = self._bump_gen(workspace_id, path)
        self._spawn(self._delete_after_debounce(workspace_id, path, gen))

    def notify_sync(self, workspace_id: str) -> None:
        if not self._enabled:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._spawn(self._sync_workspace(workspace_id))
        logger.info("workspace index: sync queued %s", workspace_id)

    def notify_workspace_deleted(self, workspace_id: str) -> None:
        if not self._enabled:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        for key in [k for k in self._gen if k[0] == workspace_id]:
            del self._gen[key]
        self._spawn(self._delete_collection(workspace_id))

    def _bump_gen(self, workspace_id: str, path: str) -> int:
        key = (workspace_id, path)
        self._gen[key] = self._gen.get(key, 0) + 1
        return self._gen[key]

    def _gen_current(self, workspace_id: str, path: str, gen: int) -> bool:
        return self._gen.get((workspace_id, path), 0) == gen

    async def _reindex_after_debounce(
        self, workspace_id: str, rel_path: str, gen: int
    ) -> None:
        await asyncio.sleep(self._debounce_seconds)
        if not self._gen_current(workspace_id, rel_path, gen):
            return
        await self._reindex_file(workspace_id, rel_path, gen)

    async def _delete_after_debounce(
        self, workspace_id: str, rel_path: str, gen: int
    ) -> None:
        await asyncio.sleep(self._debounce_seconds)
        if not self._gen_current(workspace_id, rel_path, gen):
            return
        collection = self._collection(workspace_id)
        if collection is None:
            return
        await self._delete_points(collection, rel_path)
        logger.info(
            "workspace index: removed %s/%s", workspace_id, rel_path
        )

    def _collection(self, workspace_id: str) -> Optional[str]:
        if not WORKSPACE_ID_RE.match(workspace_id):
            logger.warning(
                "workspace index: invalid workspace id %r, skipping",
                workspace_id,
            )
            return None
        return f"ws_{workspace_id}"

    def _excluded(self, rel_path: str) -> bool:
        return any(
            fnmatch.fnmatch(rel_path, pattern) for pattern in self._cfg.exclude
        )

    async def _ensure_collection(self, collection: str) -> None:
        client = self._get_client()
        if await client.collection_exists(collection):
            return
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=self._cfg.vector_size, distance=Distance.COSINE
            ),
        )
        logger.info(
            "workspace index: created collection %s (dim=%d)",
            collection,
            self._cfg.vector_size,
        )

    async def _delete_points(self, collection: str, rel_path: str) -> None:
        client = self._get_client()
        if not await client.collection_exists(collection):
            return
        await client.delete(
            collection_name=collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="path", match=MatchValue(value=rel_path))
                    ]
                )
            ),
        )

    async def _delete_collection(self, workspace_id: str) -> None:
        collection = self._collection(workspace_id)
        if collection is None:
            return
        client = self._get_client()
        if await client.collection_exists(collection):
            await client.delete_collection(collection_name=collection)
            logger.info(
                "workspace index: dropped collection %s", collection
            )

    async def _embed_texts(self, texts: list[str]) -> Optional[list[list[float]]]:
        provider = self._registry.get_provider(self._cfg.embed_provider)
        if provider is None:
            logger.error(
                "workspace index: embed provider '%s' not found",
                self._cfg.embed_provider,
            )
            return None
        llm_client = provider.get_llm_client()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            try:
                batch_vectors = await llm_client.create_embedding(
                    self._cfg.embed_model, batch
                )
            except Exception:
                logger.error(
                    "workspace index: embedding request failed", exc_info=True
                )
                return None
            if not batch_vectors:
                return None
            vectors.extend(batch_vectors)
        return vectors

    async def _reindex_file(
        self, workspace_id: str, rel_path: str, gen: int
    ) -> None:
        collection = self._collection(workspace_id)
        if collection is None or self._excluded(rel_path):
            return

        root = os.path.join(self._workspaces_dir, workspace_id)
        full_path = os.path.join(root, rel_path)
        if not os.path.isfile(full_path):
            await self._delete_points(collection, rel_path)
            return
        if is_binary_file(full_path):
            return
        try:
            st = os.stat(full_path)
            with open(full_path, "rb") as f:
                raw = f.read(self._cfg.max_file_bytes + 1)
        except OSError as e:
            logger.warning(
                "workspace index: cannot read %s/%s: %s", workspace_id, rel_path, e
            )
            return
        if len(raw) > self._cfg.max_file_bytes:
            return

        text = raw.decode("utf-8", errors="replace")
        chunks = chunk_text(text, self._cfg.chunk_chars, self._cfg.chunk_overlap)
        vectors = await self._embed_texts([chunk for _, chunk in chunks])
        if vectors is None:
            return
        # Re-check after embedding: a newer write to the same path must win.
        if not self._gen_current(workspace_id, rel_path, gen):
            return

        await self._ensure_collection(collection)
        await self._delete_points(collection, rel_path)
        if not chunks:
            return
        digest = hashlib.sha1(raw).hexdigest()
        points = [
            PointStruct(
                id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"mikoshi-index/{workspace_id}/{rel_path}#{index}",
                    )
                ),
                vector=vector,
                payload={
                    "path": rel_path,
                    "text": chunk,
                    "chunk": index,
                    "start_line": start_line,
                    "hash": digest,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                },
            )
            for index, ((start_line, chunk), vector) in enumerate(
                zip(chunks, vectors, strict=True)
            )
        ]
        await self._get_client().upsert(collection_name=collection, points=points)
        logger.info(
            "workspace index: indexed %s/%s (%d chunks)",
            workspace_id,
            rel_path,
            len(points),
        )

    async def _sync_workspace(self, workspace_id: str) -> None:
        collection = self._collection(workspace_id)
        if collection is None:
            return
        root = os.path.join(self._workspaces_dir, workspace_id)
        if not os.path.isdir(root):
            return

        client = self._get_client()
        await self._ensure_collection(collection)
        state = await self._scroll_state(collection)

        disk: dict[str, str] = {}
        for full_path in walk_files(root):
            rel_path = os.path.relpath(full_path, root)
            if self._excluded(rel_path):
                continue
            if is_binary_file(full_path):
                continue
            try:
                if os.path.getsize(full_path) > self._cfg.max_file_bytes:
                    continue
            except OSError:
                continue
            disk[rel_path] = full_path

        gone = [path for path in state if path not in disk]
        if gone:
            await client.delete(
                collection_name=collection,
                points_selector=FilterSelector(
                    filter=Filter(
                        should=[
                            FieldCondition(key="path", match=MatchValue(value=path))
                            for path in gone
                        ]
                    )
                ),
            )
            logger.info(
                "workspace index: removed %d deleted path(s) in %s",
                len(gone),
                workspace_id,
            )

        for rel_path, full_path in sorted(disk.items()):
            stored = state.get(rel_path)
            try:
                st = os.stat(full_path)
                if stored and stored[0] == st.st_size and stored[1] == st.st_mtime:
                    continue
                if stored:
                    with open(full_path, "rb") as f:
                        raw = f.read(self._cfg.max_file_bytes + 1)
                    if hashlib.sha1(raw).hexdigest() == stored[2]:
                        continue
            except OSError as e:
                logger.warning(
                    "workspace index: cannot stat %s/%s: %s",
                    workspace_id,
                    rel_path,
                    e,
                )
                continue
            gen = self._gen.get((workspace_id, rel_path), 0)
            try:
                await self._reindex_file(workspace_id, rel_path, gen)
            except Exception:
                logger.error(
                    "workspace index: failed to reindex %s/%s",
                    workspace_id,
                    rel_path,
                    exc_info=True,
                )

    async def _scroll_state(
        self, collection: str
    ) -> dict[str, tuple[int, float, str]]:
        client = self._get_client()
        state: dict[str, tuple[int, float, str]] = {}
        offset = None
        while True:
            points, offset = await client.scroll(
                collection_name=collection,
                limit=SCROLL_PAGE_LIMIT,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                path = payload.get("path")
                if path:
                    state[path] = (
                        payload.get("size"),
                        payload.get("mtime"),
                        payload.get("hash"),
                    )
            if not offset:
                break
        return state

    async def sync_all(self) -> None:
        if not self._enabled:
            return
        try:
            entries = sorted(os.listdir(self._workspaces_dir))
        except OSError as e:
            logger.error("workspace index: cannot list workspaces: %s", e)
            return
        for workspace_id in entries:
            if not os.path.isdir(
                os.path.join(self._workspaces_dir, workspace_id)
            ):
                continue
            try:
                await self._sync_workspace(workspace_id)
            except Exception:
                logger.error(
                    "workspace index: sync failed for %s",
                    workspace_id,
                    exc_info=True,
                )

    async def search(
        self, workspace_id: str, query: str, limit: int = 8
    ) -> list[dict]:
        if not self._enabled:
            return []
        collection = self._collection(workspace_id)
        if collection is None:
            return []
        client = self._get_client()
        if not await client.collection_exists(collection):
            return []

        clamped = max(1, min(int(limit or 8), 25))
        with start_retriever_span("workspace_search", query) as span:
            vectors = await self._embed_texts([query])
            if vectors is None:
                raise RuntimeError("failed to embed query")
            response = await client.query_points(
                collection_name=collection,
                query=vectors[0],
                limit=clamped,
            )
            hits = response.points
            span.set_attribute(
                SpanAttributes.RETRIEVAL_DOCUMENTS,
                json.dumps(
                    [
                        {
                            "document.content": (hit.payload or {}).get("text", ""),
                            "document.score": hit.score,
                        }
                        for hit in hits
                    ]
                ),
            )

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "path": payload.get("path"),
                    "start_line": payload.get("start_line"),
                    "score": hit.score,
                    "text": payload.get("text", ""),
                }
            )
        logger.info(
            "workspace index: search %s '%s' -> %d hit(s)",
            workspace_id,
            query[:80],
            len(results),
        )
        return results

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
        self._tasks.clear()
        if self._qdrant is not None:
            await self._qdrant.close()
            self._qdrant = None
