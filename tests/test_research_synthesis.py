from mikoshi.agents.research.helpers import (
    DEFAULT_CONTEXT_WINDOW,
    _batch_findings,
    _find_findings_file,
    _format_material_block,
    _parse_findings_files,
    _summarize_user_prompt,
    _synthesis_budget,
    _synthesis_user_prompt,
)


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
