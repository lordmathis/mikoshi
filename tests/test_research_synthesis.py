import asyncio

import pytest

from mikoshi.agents.research.helpers import (
    DEFAULT_CONTEXT_WINDOW,
    _batch_findings,
    _batch_files,
    _find_findings_file,
    _format_material_block,
    _parse_findings_files,
    _synthesis_budget,
    _synthesis_user_prompt,
)
from mikoshi.agents.research.stages import Synthesizer


class TestFindFindingsFile:
    def test_matches_by_index_prefix(self):
        files = [
            "findings/01-anything.md",
            "findings/02-some-topic.md",
            "findings/10-foo.md",
        ]
        assert _find_findings_file(files, 1) == "findings/01-anything.md"
        assert _find_findings_file(files, 2) == "findings/02-some-topic.md"
        assert _find_findings_file(files, 10) == "findings/10-foo.md"

    def test_ignores_suffix(self):
        # Whatever descriptive suffix the model wrote, the index is what matters.
        files = ["findings/05-totally-unexpected-suffix.md"]
        assert _find_findings_file(files, 5) == "findings/05-totally-unexpected-suffix.md"

    def test_no_match_returns_none(self):
        assert _find_findings_file(["findings/03-x.md"], 5) is None
        assert _find_findings_file([], 1) is None

    def test_requires_zero_padded_prefix(self):
        # The suggested format is `NN-`; bare `5-` does not match idx=5.
        assert _find_findings_file(["findings/5-foo.md"], 5) is None

    def test_requires_md_extension(self):
        assert _find_findings_file(["findings/05-foo.txt"], 5) is None

    def test_first_match_wins(self):
        # If the model wrote two files for the same task (e.g. a retry), pick
        # the first one in iteration order — deterministic for a sorted list.
        files = [
            "findings/05-aaa.md",
            "findings/05-bbb.md",
        ]
        assert _find_findings_file(files, 5) == "findings/05-aaa.md"

    def test_does_not_match_other_dirs(self):
        assert _find_findings_file(["synthesis/05-foo.md"], 5) is None
        assert _find_findings_file(["05-foo.md"], 5) is None


class TestParseFindingsFiles:
    def test_returns_only_paths_existing_on_disk(self):
        plan = (
            "# Research: X\n\n"
            "## Tasks\n"
            "- [ ] first\n"
            "- [x] Second Task\n"
            "- [x] third-thing\n"
        )
        files = [
            "findings/02-second-task.md",
            "findings/03-third-thing.md",
            "findings/04-not-in-plan.md",
        ]
        assert _parse_findings_files(plan, files) == [
            "findings/02-second-task.md",
            "findings/03-third-thing.md",
        ]

    def test_tolerates_suffix_mismatch(self):
        # The model wrote a different suffix than the slug would produce, but
        # the index prefix still matches — synthesis should pick it up.
        plan = (
            "## Tasks\n"
            "- [x] Some Task\n"
        )
        files = ["findings/01-models-own-suffix.md"]
        assert _parse_findings_files(plan, files) == ["findings/01-models-own-suffix.md"]

    def test_unchecked_tasks_excluded(self):
        plan = (
            "## Tasks\n"
            "- [ ] a\n"
            "- [x] b\n"
        )
        files = ["findings/02-b.md"]
        assert _parse_findings_files(plan, files) == ["findings/02-b.md"]

    def test_missing_file_silently_dropped(self):
        # A checked task with no matching findings file on disk contributes
        # nothing — synthesis skips it rather than crashing.
        plan = (
            "## Tasks\n"
            "- [x] present\n"
            "- [x] missing\n"
        )
        files = ["findings/01-present.md"]
        assert _parse_findings_files(plan, files) == ["findings/01-present.md"]

    def test_empty_disk_returns_empty(self):
        plan = "## Tasks\n- [x] anything\n"
        assert _parse_findings_files(plan, []) == []


class TestSynthesisBudget:
    def test_applies_fraction_when_larger(self):
        reserve = int(DEFAULT_CONTEXT_WINDOW * 0.30)
        assert _synthesis_budget(DEFAULT_CONTEXT_WINDOW) == (
            DEFAULT_CONTEXT_WINDOW - reserve
        )

    def test_applies_min_reserve_for_small_window(self):
        assert _synthesis_budget(4000) == 4000 - 2048

    def test_floors_at_1024(self):
        assert _synthesis_budget(2000) == 1024


class TestBatchFindings:
    def test_packs_within_budget(self):
        items = [("a.md", "x", 10), ("b.md", "y", 10), ("c.md", "z", 25)]
        batches = _batch_findings(items, 20)
        assert batches == [items[:2], items[2:]]

    def test_oversized_item_gets_own_batch(self):
        items = [("big.md", "x", 100)]
        batches = _batch_findings(items, 20)
        assert batches == [items]

    def test_empty_input(self):
        assert _batch_findings([], 20) == []


class TestBatchFiles:
    def test_matches_only_synthesis_batches_sorted(self):
        files = [
            "synthesis/batch_02.md",
            "RESEARCH_PLAN.md",
            "synthesis/batch_01.md",
            "synthesis/other.md",
            "findings/01-x.md",
            "synthesis/batch_10.txt",
        ]
        assert _batch_files(files) == ["synthesis/batch_01.md", "synthesis/batch_02.md"]

    def test_empty(self):
        assert _batch_files([]) == []


class TestPromptBuilders:
    def test_synthesis_prompt_source_wording_by_flag(self):
        default = _synthesis_user_prompt("Q?", "BLOCK")
        summaries = _synthesis_user_prompt("Q?", "BLOCK", from_summaries=True)
        assert "research findings" in default
        assert "batch summaries" not in default
        assert "batch summaries" in summaries

    def test_format_material_block(self):
        block = _format_material_block([("a.md", "CONTENT", 5)])
        assert block == "=== a.md ===\nCONTENT"


class _FakeSynthCtx:
    """Minimal StageContext double for exercising the Synthesizer."""

    workspace_id = "ws-1"
    chat_id = "chat-1"
    tool_servers = []

    def __init__(self, files, context_window):
        self._files = dict(files)
        self.context_window = context_window
        self.deleted = []

    def list_files(self):
        return sorted(self._files)

    def file_exists(self, path):
        return path in self._files

    def read_file(self, path):
        return self._files.get(path, "")

    def write_file(self, path, content):
        self._files[path] = content

    def delete_file(self, path):
        self.deleted.append(path)
        self._files.pop(path, None)

    async def spawn(self, system_prompt, user_message, queue, *, tool_servers, phase=None):
        from types import SimpleNamespace

        return SimpleNamespace(last_response=f"out-{phase}")


def _big_content(n_words):
    return " ".join(f"word{i}" for i in range(n_words))


class TestSynthesizerStaleBatchCleanup:
    @pytest.mark.asyncio
    async def test_stale_batches_from_previous_run_deleted(self):
        # Small window forces the reduce path (budget < findings tokens).
        ctx = _FakeSynthCtx(
            {
                "RESEARCH_PLAN.md": "## Tasks\n- [x] one\n- [x] two\n",
                "findings/01-one.md": _big_content(2000),
                "findings/02-two.md": _big_content(2000),
                # Leftovers from a previous synthesis run with three batches.
                "synthesis/batch_01.md": "stale 1",
                "synthesis/batch_02.md": "stale 2",
                "synthesis/batch_03.md": "stale 3",
            },
            context_window=4000,
        )

        await Synthesizer(ctx, "the question").apply(asyncio.Queue())

        assert ctx.deleted == [
            "synthesis/batch_01.md",
            "synthesis/batch_02.md",
            "synthesis/batch_03.md",
        ]
        assert "out-synthesize" in ctx._files["REPORT.md"]
        # Fresh batches were written for this run only.
        assert "stale" not in ctx._files.get("synthesis/batch_01.md", "")

    @pytest.mark.asyncio
    async def test_fast_path_leaves_existing_batches_alone(self):
        ctx = _FakeSynthCtx(
            {
                "RESEARCH_PLAN.md": "## Tasks\n- [x] one\n",
                "findings/01-one.md": "small findings",
                "synthesis/batch_01.md": "pre-existing",
            },
            context_window=None,  # default window -> fast path
        )

        await Synthesizer(ctx, "the question").apply(asyncio.Queue())

        assert ctx.deleted == []
        assert ctx._files["synthesis/batch_01.md"] == "pre-existing"
        assert "out-synthesize" in ctx._files["REPORT.md"]
