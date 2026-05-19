import pytest

from mikoshi.tools.edit_utils import EditError, apply_edits, normalize_for_fuzzy_match


class TestNormalizeForFuzzyMatch:
    def test_smart_single_quotes(self):
        assert normalize_for_fuzzy_match("\u2018hello\u2019") == "'hello'"

    def test_smart_double_quotes(self):
        assert normalize_for_fuzzy_match("\u201Chello\u201D") == '"hello"'

    def test_unicode_dashes(self):
        for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
            assert normalize_for_fuzzy_match(f"foo{ch}bar") == "foo-bar"

    def test_non_breaking_spaces(self):
        assert normalize_for_fuzzy_match("foo\u00A0bar") == "foo bar"

    def test_trailing_whitespace_stripped(self):
        assert normalize_for_fuzzy_match("line  \nline2\t") == "line\nline2"

    def test_already_normalized_text_unchanged(self):
        text = "hello world\nline two"
        assert normalize_for_fuzzy_match(text) == text

    def test_empty_string(self):
        assert normalize_for_fuzzy_match("") == ""


class TestApplyEdits:
    def test_single_exact_replacement(self):
        content = "hello world"
        edits = [{"oldText": "world", "newText": "universe"}]
        result, warnings = apply_edits(content, edits)
        assert result == "hello universe"
        assert warnings == []

    def test_multiple_non_overlapping_edits(self):
        content = "foo bar baz"
        edits = [
            {"oldText": "foo", "newText": "one"},
            {"oldText": "baz", "newText": "three"},
        ]
        result, warnings = apply_edits(content, edits)
        assert result == "one bar three"

    def test_empty_old_text_raises(self):
        content = "hello"
        edits = [{"oldText": "", "newText": "x"}]
        with pytest.raises(EditError, match="cannot be empty"):
            apply_edits(content, edits)

    def test_not_found_raises(self):
        content = "hello"
        edits = [{"oldText": "missing", "newText": "x"}]
        with pytest.raises(EditError, match="not found"):
            apply_edits(content, edits)

    def test_duplicate_match_raises(self):
        content = "abc abc"
        edits = [{"oldText": "abc", "newText": "x"}]
        with pytest.raises(EditError, match="multiple times"):
            apply_edits(content, edits)

    def test_overlapping_edits_raises(self):
        content = "abcdef"
        edits = [
            {"oldText": "bcd", "newText": "x"},
            {"oldText": "cde", "newText": "y"},
        ]
        with pytest.raises(EditError, match="overlap"):
            apply_edits(content, edits)

    def test_no_change_raises(self):
        content = "hello"
        edits = [{"oldText": "hello", "newText": "hello"}]
        with pytest.raises(EditError, match="no changes"):
            apply_edits(content, edits)

    def test_strips_bom(self):
        content = "\ufeffhello world"
        edits = [{"oldText": "hello", "newText": "hi"}]
        result, warnings = apply_edits(content, edits)
        assert result == "hi world"
        assert any("BOM" in w for w in warnings)

    def test_preserves_crlf(self):
        content = "line1\r\nline2\r\n"
        edits = [{"oldText": "line1", "newText": "first"}]
        result, warnings = apply_edits(content, edits)
        assert result == "first\r\nline2\r\n"

    def test_fuzzy_match_fallback(self):
        content = "it\u2019s a test"
        edits = [{"oldText": "it's a test", "newText": "passed"}]
        result, warnings = apply_edits(content, edits)
        assert result == "passed"
        assert any("fuzzy" in w.lower() for w in warnings)

    def test_fuzzy_match_trailing_whitespace(self):
        content = "hello   \nworld"
        edits = [{"oldText": "hello\nworld", "newText": "goodbye\nworld"}]
        result, warnings = apply_edits(content, edits)
        assert result == "goodbye\nworld"
        assert any("fuzzy" in w.lower() for w in warnings)

    def test_multiline_edit(self):
        content = "def foo():\n    pass\n"
        edits = [{"oldText": "def foo():\n    pass", "newText": "def bar():\n    return 1"}]
        result, warnings = apply_edits(content, edits)
        assert result == "def bar():\n    return 1\n"
