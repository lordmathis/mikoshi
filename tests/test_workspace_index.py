import hashlib
import math
import os
import re
import zlib
from types import SimpleNamespace

import pytest

from mikoshi.config import AppConfig, WorkspaceIndexConfig
from mikoshi.tools.builtin.workspace import WorkspaceTools
from mikoshi.tools.context import ToolCallContext, WorkspaceContext
from mikoshi.tools.manager import ToolManager
from mikoshi.workspace_index import WorkspaceIndexer, chunk_text


def fake_embed(text: str) -> list[float]:
    vec = [0.0] * 8
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vec[zlib.crc32(word.encode()) % 8] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if not norm:
        return [1.0] + [0.0] * 7
    return [v / norm for v in vec]


class FakeEmbedClient:
    def __init__(self):
        self.embedded_texts: list[str] = []

    async def create_embedding(self, model, input):
        if isinstance(input, str):
            self.embedded_texts.append(input)
            return fake_embed(input)
        self.embedded_texts.extend(input)
        return [fake_embed(t) for t in input]


class FakeProviderRegistry:
    def __init__(self, client: FakeEmbedClient):
        self._client = client

    def get_provider(self, name):
        if name != "embed":
            return None
        return SimpleNamespace(get_llm_client=lambda: self._client)


class FakeQdrantClient:
    def __init__(self):
        self.collections: dict[str, dict[str, object]] = {}

    async def collection_exists(self, collection_name):
        return collection_name in self.collections

    async def create_collection(self, collection_name, vectors_config=None):
        self.collections[collection_name] = {}

    async def delete_collection(self, collection_name):
        self.collections.pop(collection_name, None)

    async def upsert(self, collection_name, points):
        store = self.collections.setdefault(collection_name, {})
        for point in points:
            store[point.id] = point

    async def delete(self, collection_name, points_selector):
        store = self.collections.get(collection_name, {})
        filt = getattr(points_selector, "filter", None)
        conditions = (getattr(filt, "must", None) or []) + (
            getattr(filt, "should", None) or []
        )
        matches = {c.key: c.match.value for c in conditions}
        if not matches:
            return
        for point_id, point in list(store.items()):
            payload = point.payload or {}
            if any(payload.get(k) == v for k, v in matches.items()):
                del store[point_id]

    async def scroll(
        self,
        collection_name,
        limit=10,
        offset=None,
        with_payload=True,
        with_vectors=False,
    ):
        store = self.collections.get(collection_name, {})
        return list(store.values()), None

    async def query_points(
        self, collection_name, query, query_filter=None, limit=10
    ):
        store = self.collections.get(collection_name, {})

        def score(vector):
            dot = sum(a * b for a, b in zip(query, vector))
            qn = math.sqrt(sum(v * v for v in query))
            vn = math.sqrt(sum(v * v for v in vector))
            return dot / (qn * vn) if qn and vn else 0.0

        ranked = sorted(store.values(), key=lambda p: -score(p.vector))
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    id=p.id, score=score(p.vector), payload=p.payload
                )
                for p in ranked[:limit]
            ]
        )

    async def close(self):
        pass


def make_indexer(workspaces_dir, **cfg_overrides):
    defaults = {
        "embed_provider": "embed",
        "embed_model": "emb-model",
        "vector_size": 8,
        "qdrant_url": "http://fake",
    }
    defaults.update(cfg_overrides)
    cfg = WorkspaceIndexConfig(**defaults)
    embed_client = FakeEmbedClient()
    qdrant = FakeQdrantClient()
    indexer = WorkspaceIndexer(
        cfg, str(workspaces_dir), FakeProviderRegistry(embed_client), client=qdrant
    )
    indexer._debounce_seconds = 0
    return indexer, qdrant, embed_client


def make_workspace(workspaces_dir, workspace_id="alpha"):
    ws = workspaces_dir / workspace_id
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def points_for(qdrant, collection, path):
    return [
        p
        for p in qdrant.collections.get(collection, {}).values()
        if (p.payload or {}).get("path") == path
    ]


class TestChunkText:
    def test_line_boundary_split_with_overlap(self):
        chunks = chunk_text("aaaa\nbbbb\ncccc", chunk_chars=10, overlap_chars=4)
        assert chunks == [(1, "aaaa\nbbbb"), (2, "bbbb\ncccc")]

    def test_single_short_line(self):
        assert chunk_text("hello", 100, 20) == [(1, "hello")]

    def test_monster_line_hard_split(self):
        chunks = chunk_text("x" * 25, chunk_chars=10, overlap_chars=4)
        assert chunks == [(1, "x" * 10), (1, "x" * 10), (1, "x" * 5)]

    def test_empty_and_whitespace(self):
        assert chunk_text("", 100, 20) == []
        assert chunk_text("  \n \n", 100, 20) == []

    def test_no_overlap_when_zero(self):
        chunks = chunk_text("aaaa\nbbbb\ncccc", chunk_chars=10, overlap_chars=0)
        assert chunks == [(1, "aaaa\nbbbb"), (3, "cccc")]

    def test_chunk_never_exceeds_char_budget_on_normal_lines(self):
        lines = "\n".join("line%d" % i for i in range(50))
        for start, text in chunk_text(lines, 40, 10):
            assert len(text) <= 40


class TestNotifyChanged:
    @pytest.mark.asyncio
    async def test_file_appears_as_points_with_payload(self, tmp_path):
        ws = make_workspace(tmp_path)
        content = "alpha beta\ngamma delta\n"
        (ws / "hello.py").write_text(content)
        indexer, qdrant, _ = make_indexer(tmp_path)

        indexer.notify_changed("alpha", "hello.py")
        await indexer._wait_for_tasks()

        points = points_for(qdrant, "ws_alpha", "hello.py")
        assert len(points) == 1
        payload = points[0].payload
        assert payload["path"] == "hello.py"
        assert payload["start_line"] == 1
        assert payload["chunk"] == 0
        assert payload["text"] == content
        assert payload["hash"] == hashlib.sha1(content.encode()).hexdigest()
        assert payload["size"] == len(content)

    @pytest.mark.asyncio
    async def test_deterministic_ids_upsert_stable(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "hello.py").write_text("alpha beta\n")
        indexer, qdrant, _ = make_indexer(tmp_path)

        indexer.notify_changed("alpha", "hello.py")
        await indexer._wait_for_tasks()
        count = len(qdrant.collections["ws_alpha"])

        indexer.notify_changed("alpha", "hello.py")
        await indexer._wait_for_tasks()
        assert len(qdrant.collections["ws_alpha"]) == count

    @pytest.mark.asyncio
    async def test_stale_gen_performs_no_upsert(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "hello.py").write_text("alpha beta\n")
        indexer, qdrant, _ = make_indexer(tmp_path)

        await indexer._reindex_file("alpha", "hello.py", gen=99)

        assert "ws_alpha" not in qdrant.collections

    @pytest.mark.asyncio
    async def test_delete_removes_points(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "hello.py").write_text("alpha beta\n")
        indexer, qdrant, _ = make_indexer(tmp_path)
        indexer.notify_changed("alpha", "hello.py")
        await indexer._wait_for_tasks()
        assert points_for(qdrant, "ws_alpha", "hello.py")

        indexer.notify_deleted("alpha", "hello.py")
        await indexer._wait_for_tasks()

        assert not points_for(qdrant, "ws_alpha", "hello.py")


class TestSync:
    @pytest.mark.asyncio
    async def test_indexes_new_files(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "a.py").write_text("alpha alpha\n")
        (ws / "sub").mkdir()
        (ws / "sub" / "b.md").write_text("beta beta\n")
        indexer, qdrant, _ = make_indexer(tmp_path)

        await indexer._sync_workspace("alpha")

        assert len(points_for(qdrant, "ws_alpha", "a.py")) == 1
        assert len(points_for(qdrant, "ws_alpha", "sub/b.md")) == 1

    @pytest.mark.asyncio
    async def test_skips_unchanged_files(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "a.py").write_text("alpha alpha\n")
        indexer, qdrant, embed = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")
        embedded_after_first = len(embed.embedded_texts)

        await indexer._sync_workspace("alpha")

        assert len(embed.embedded_texts) == embedded_after_first

    @pytest.mark.asyncio
    async def test_stat_only_drift_not_reembedded(self, tmp_path):
        ws = make_workspace(tmp_path)
        target = ws / "a.py"
        target.write_text("alpha alpha\n")
        indexer, qdrant, embed = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")
        embedded_after_first = len(embed.embedded_texts)

        os.utime(target, ns=(1, 1))
        await indexer._sync_workspace("alpha")

        assert len(embed.embedded_texts) == embedded_after_first

    @pytest.mark.asyncio
    async def test_reembeds_modified_content(self, tmp_path):
        ws = make_workspace(tmp_path)
        target = ws / "a.py"
        target.write_text("alpha alpha\n")
        indexer, qdrant, embed = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")
        embedded_after_first = len(embed.embedded_texts)

        target.write_text("beta beta\n")
        await indexer._sync_workspace("alpha")

        assert len(embed.embedded_texts) > embedded_after_first
        points = points_for(qdrant, "ws_alpha", "a.py")
        assert len(points) == 1
        assert points[0].payload["hash"] == hashlib.sha1(
            b"beta beta\n"
        ).hexdigest()

    @pytest.mark.asyncio
    async def test_deletes_points_for_removed_files(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "a.py").write_text("alpha alpha\n")
        indexer, qdrant, _ = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")
        assert points_for(qdrant, "ws_alpha", "a.py")

        (ws / "a.py").unlink()
        await indexer._sync_workspace("alpha")

        assert not points_for(qdrant, "ws_alpha", "a.py")

    @pytest.mark.asyncio
    async def test_skips_excluded_binary_and_oversized(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "node_modules").mkdir()
        (ws / "node_modules" / "lib.js").write_text("junk junk\n")
        (ws / "uv.lock").write_text("lock lock\n")
        (ws / "blob.bin").write_bytes(b"\x00\x01binary")
        (ws / "big.txt").write_text("word " * 20)
        (ws / "ok.py").write_text("alpha alpha\n")
        indexer, qdrant, _ = make_indexer(tmp_path, max_file_bytes=30)

        await indexer._sync_workspace("alpha")

        assert points_for(qdrant, "ws_alpha", "ok.py")
        assert not points_for(qdrant, "ws_alpha", "node_modules/lib.js")
        assert not points_for(qdrant, "ws_alpha", "uv.lock")
        assert not points_for(qdrant, "ws_alpha", "blob.bin")
        assert not points_for(qdrant, "ws_alpha", "big.txt")

    @pytest.mark.asyncio
    async def test_notify_sync_runs_workspace_sync(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "a.py").write_text("alpha alpha\n")
        indexer, qdrant, _ = make_indexer(tmp_path)

        indexer.notify_sync("alpha")
        await indexer._wait_for_tasks()

        assert points_for(qdrant, "ws_alpha", "a.py")

    @pytest.mark.asyncio
    async def test_rename_moves_points(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "old.py").write_text("alpha alpha\n")
        indexer, qdrant, _ = make_indexer(tmp_path)
        indexer.notify_changed("alpha", "old.py")
        await indexer._wait_for_tasks()

        (ws / "old.py").rename(ws / "new.py")
        indexer.notify_deleted("alpha", "old.py")
        indexer.notify_changed("alpha", "new.py")
        await indexer._wait_for_tasks()

        assert not points_for(qdrant, "ws_alpha", "old.py")
        assert points_for(qdrant, "ws_alpha", "new.py")

    @pytest.mark.asyncio
    async def test_notify_workspace_deleted_drops_collection(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "a.py").write_text("alpha alpha\n")
        indexer, qdrant, _ = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")
        assert "ws_alpha" in qdrant.collections

        indexer.notify_workspace_deleted("alpha")
        await indexer._wait_for_tasks()

        assert "ws_alpha" not in qdrant.collections


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_ranked_chunks(self, tmp_path):
        ws = make_workspace(tmp_path)
        (ws / "fruits.md").write_text("apple banana cherry\n")
        (ws / "cars.md").write_text("engine tire piston\n")
        indexer, qdrant, _ = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")

        results = await indexer.search("alpha", "apple pie")

        assert results
        assert results[0]["path"] == "fruits.md"
        assert results[0]["start_line"] == 1
        assert results[0]["score"] > 0
        assert "apple" in results[0]["text"]

    @pytest.mark.asyncio
    async def test_search_honors_limit(self, tmp_path):
        ws = make_workspace(tmp_path)
        for i in range(5):
            (ws / f"f{i}.txt").write_text("shared topic\n")
        indexer, qdrant, _ = make_indexer(tmp_path)
        await indexer._sync_workspace("alpha")

        results = await indexer.search("alpha", "shared topic", limit=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_missing_collection_returns_empty(self, tmp_path):
        indexer, qdrant, _ = make_indexer(tmp_path)

        assert await indexer.search("nowhere", "anything") == []


class TestDisabledIndexer:
    @pytest.mark.asyncio
    async def test_notify_methods_are_noops(self, tmp_path):
        indexer, qdrant, embed = make_indexer(
            tmp_path,
            embed_provider="",
            embed_model="",
            vector_size=0,
            qdrant_url="",
        )

        indexer.notify_changed("alpha", "a.py")
        indexer.notify_deleted("alpha", "a.py")
        indexer.notify_sync("alpha")
        indexer.notify_workspace_deleted("alpha")
        await indexer.sync_all()

        assert not indexer.enabled
        assert not indexer._tasks
        assert not embed.embedded_texts
        assert qdrant.collections == {}
        assert indexer._qdrant is qdrant  # no real client created

    def test_notify_without_running_loop_is_noop(self, tmp_path):
        indexer, qdrant, _ = make_indexer(tmp_path)

        indexer.notify_changed("alpha", "a.py")
        indexer.notify_sync("alpha")

        assert not indexer._tasks


def make_tool_manager(indexer):
    from unittest.mock import MagicMock

    return ToolManager(AppConfig(), MagicMock(), workspace_index=indexer)


class TestSearchToolRegistration:
    @pytest.mark.asyncio
    async def test_hidden_without_indexer(self):
        tools = WorkspaceTools()
        tools.set_tool_manager(make_tool_manager(None))
        await tools.initialize()

        assert "search" not in tools._tools

    @pytest.mark.asyncio
    async def test_hidden_when_indexer_disabled(self, tmp_path):
        indexer, _, _ = make_indexer(
            tmp_path, embed_provider="", qdrant_url=""
        )
        tools = WorkspaceTools()
        tools.set_tool_manager(make_tool_manager(indexer))
        await tools.initialize()

        assert "search" not in tools._tools

    @pytest.mark.asyncio
    async def test_present_with_enabled_indexer(self, tmp_path):
        indexer, _, _ = make_indexer(tmp_path)
        tools = WorkspaceTools()
        tools.set_tool_manager(make_tool_manager(indexer))
        await tools.initialize()

        assert "search" in tools._tools


class TestSearchToolInvocation:
    @pytest.mark.asyncio
    async def test_returns_formatted_results(self, tmp_path):
        workspaces_dir = tmp_path / "workspaces"
        ws = make_workspace(workspaces_dir)
        (ws / "fruits.md").write_text("apple banana cherry\n")
        indexer, qdrant, _ = make_indexer(workspaces_dir)
        await indexer._sync_workspace("alpha")

        tools = WorkspaceTools()
        tools.set_tool_manager(make_tool_manager(indexer))
        await tools.initialize()

        context = ToolCallContext(
            provider=None,
            model_id="m",
            chat_id="c1",
            workspace=WorkspaceContext(
                workspace_id="alpha",
                data_dir=str(tmp_path),
                connector=None,
                git_user_name="",
                git_user_email="",
            ),
        )
        result = await tools.call_tool(
            "search", {"query": "apple", "limit": 1}, context
        )

        assert "fruits.md:1" in result
        assert "apple banana cherry" in result

    @pytest.mark.asyncio
    async def test_missing_collection_reports_no_results(self, tmp_path):
        workspaces_dir = tmp_path / "workspaces"
        make_workspace(workspaces_dir)
        indexer, qdrant, _ = make_indexer(workspaces_dir)

        tools = WorkspaceTools()
        tools.set_tool_manager(make_tool_manager(indexer))
        await tools.initialize()

        context = ToolCallContext(
            provider=None,
            model_id="m",
            chat_id="c1",
            workspace=WorkspaceContext(
                workspace_id="alpha",
                data_dir=str(tmp_path),
                connector=None,
                git_user_name="",
                git_user_email="",
            ),
        )
        result = await tools.call_tool("search", {"query": "apple"}, context)

        assert result == "No results found."
