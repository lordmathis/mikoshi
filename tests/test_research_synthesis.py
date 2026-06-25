from mikoshi.agents.research import (
    DEFAULT_CONTEXT_WINDOW,
    _batch_findings,
    _format_material_block,
    _parse_findings_files,
    _summarize_user_prompt,
    _synthesis_budget,
    _synthesis_user_prompt,
)


class TestParseFindingsFiles:
    def test_derives_paths_from_index_and_description(self):
        # Paths are derived from the name format, never parsed from plan text.
        plan = (
            "# Research: X\n\n"
            "## Tasks\n"
            "- [ ] first\n"
            "- [x] Second Task\n"
            "- [x] third-thing\n"
        )
        assert _parse_findings_files(plan) == [
            "findings/02-second-task.md",
            "findings/03-third-thing.md",
        ]

    def test_unchecked_tasks_excluded(self):
        plan = (
            "## Tasks\n"
            "- [ ] a\n"
            "- [x] b\n"
        )
        assert _parse_findings_files(plan) == ["findings/02-b.md"]


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


class TestPromptBuilders:
    def test_synthesis_prompt_mentions_findings(self):
        prompt = _synthesis_user_prompt("Q?", "BLOCK")
        assert "Q?" in prompt
        assert "research findings" in prompt
        assert "BLOCK" in prompt

    def test_synthesis_prompt_from_summaries(self):
        prompt = _synthesis_user_prompt("Q?", "BLOCK", from_summaries=True)
        assert "batch summaries" in prompt

    def test_summarize_prompt(self):
        prompt = _summarize_user_prompt("Q?", "BLOCK")
        assert "Q?" in prompt
        assert "batch of research findings" in prompt
        assert "BLOCK" in prompt

    def test_format_material_block(self):
        block = _format_material_block([("a.md", "CONTENT", 5)])
        assert block == "=== a.md ===\nCONTENT"
