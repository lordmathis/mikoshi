import unicodedata


class EditError(Exception):
    pass


def normalize_for_fuzzy_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    text = "\n".join(lines)
    for ch in [
        "\u2018",
        "\u2019",
        "\u201A",
        "\u201B",
    ]:
        text = text.replace(ch, "'")
    for ch in [
        "\u201C",
        "\u201D",
        "\u201E",
        "\u201F",
    ]:
        text = text.replace(ch, '"')
    for ch in [
        "\u2010",
        "\u2011",
        "\u2012",
        "\u2013",
        "\u2014",
        "\u2015",
        "\u2212",
    ]:
        text = text.replace(ch, "-")
    for ch in [
        "\u00A0",
        "\u2002",
        "\u2003",
        "\u2004",
        "\u2005",
        "\u2006",
        "\u2007",
        "\u2008",
        "\u2009",
        "\u200A",
        "\u202F",
        "\u205F",
        "\u3000",
    ]:
        text = text.replace(ch, " ")
    return text


def _find_unique_match(haystack: str, needle: str) -> int:
    idx = haystack.find(needle)
    if idx < 0:
        return -1
    second = haystack.find(needle, idx + 1)
    if second >= 0:
        raise EditError(
            f"oldText matches multiple times in file. Provide more surrounding context to make it unique."
        )
    return idx


def _apply_edits_in_space(content: str, edits: list[dict]) -> str:
    matches: list[tuple[int, int, str]] = []

    for edit in edits:
        old_text = edit["oldText"]
        new_text = edit["newText"]

        if not old_text:
            raise EditError("oldText cannot be empty")

        idx = _find_unique_match(content, old_text)
        if idx < 0:
            raise EditError(
                f"oldText not found in file. Make sure the text matches exactly."
            )

        matches.append((idx, idx + len(old_text), new_text))

    matches.sort(key=lambda m: m[0])

    for i in range(1, len(matches)):
        if matches[i][0] < matches[i - 1][1]:
            raise EditError("Edits overlap — each edit must target a distinct region")

    result = content
    for start, end, new_text in reversed(matches):
        result = result[:start] + new_text + result[end:]

    if result == content:
        raise EditError("All edits produced identical content — no changes made")

    return result


def apply_edits(content: str, edits: list[dict]) -> tuple[str, list[str]]:
    warnings: list[str] = []

    if content.startswith("\ufeff"):
        content = content[1:]
        warnings.append("Stripped UTF-8 BOM before matching")

    crlf_count = content.count("\r\n")
    lf_count = content.count("\n") - crlf_count
    original_has_crlf = crlf_count > lf_count

    content = content.replace("\r\n", "\n").replace("\r", "\n")

    try:
        result = _apply_edits_in_space(content, edits)
    except EditError:
        warnings.append(
            "Using fuzzy matching (normalized trailing whitespace, smart quotes, unicode dashes)"
        )
        normalized = normalize_for_fuzzy_match(content)
        normalized_edits = [
            {
                "oldText": normalize_for_fuzzy_match(e["oldText"]),
                "newText": e["newText"],
            }
            for e in edits
        ]
        result = _apply_edits_in_space(normalized, normalized_edits)

    if original_has_crlf:
        result = result.replace("\n", "\r\n")

    return result, warnings



