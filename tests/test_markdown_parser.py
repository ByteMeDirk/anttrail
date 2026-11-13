"""Tests for the Markdown section parser."""

import pytest

from anttrail.markdown_parser import Section, parse_markdown


def names(source: str, max_depth: int | None = None) -> list[str]:
    return [section.qualified_name for section in parse_markdown(source, max_depth)]


def by_name(source: str) -> dict[str, Section]:
    return {section.qualified_name: section for section in parse_markdown(source)}


@pytest.mark.parametrize(
    ("source", "expected_title"),
    [
        ("# Title\n", "Title"),
        ("###### Six\n", "Six"),
        ("## Title ##\n", "Title"),
        ("# C#\n", "C#"),
        ("   # Indented three spaces\n", "Indented three spaces"),
        ("#\tTabbed\n", "Tabbed"),
    ],
)
def test_atx_heading_titles(source: str, expected_title: str) -> None:
    (section,) = parse_markdown(source)

    assert section.title == expected_title


@pytest.mark.parametrize(
    "source",
    [
        "#hashtag\n",
        "####### seven hashes\n",
        "#\n",
        "# \n",
        "    # indented code\n",
        "\t# tab indented code\n",
        "> # quoted\n",
        "Plain text\n",
        "",
    ],
)
def test_lines_that_are_not_headings_are_ignored(source: str) -> None:
    assert parse_markdown(source) == []


@pytest.mark.parametrize(
    "source",
    [
        "```\n# comment\n```\n",
        "~~~\n# comment\n~~~\n",
        "```python\n# comment\n```\n",
        "````\n# comment\n```\nstill code\n````\n",
        "```\n# an unclosed fence hides the rest\n",
        "   ```\n# comment\n   ```\n",
    ],
)
def test_headings_inside_fenced_code_are_ignored(source: str) -> None:
    assert parse_markdown(source) == []


def test_heading_after_a_closed_fence_is_found() -> None:
    assert names("```\n# code\n```\n# Real\n") == ["Real"]


def test_backtick_in_the_info_string_is_not_a_fence() -> None:
    assert names("```a`b\n# Real\n") == ["Real"]


def test_front_matter_is_skipped() -> None:
    source = "---\ntitle: x\n# comment\n---\n\n# Real\n"

    (section,) = parse_markdown(source)

    assert (section.title, section.line_start) == ("Real", 6)


def test_unclosed_front_matter_is_not_front_matter() -> None:
    assert names("---\n# Real\n") == ["Real"]


def test_setext_headings() -> None:
    source = "First\n=====\n\nSecond\n======\n"

    sections = parse_markdown(source)

    assert [(s.title, s.line_start, s.line_end) for s in sections] == [
        ("First", 1, 2),
        ("Second", 4, 5),
    ]


@pytest.mark.parametrize(
    "source",
    [
        "Text\n\n---\n",
        "- item\n---\n",
        "1. item\n---\n",
        "> quote\n---\n",
        "| a | b |\n---\n",
        "# Heading\n---\n",
        "    code\n---\n",
        "---\n",
    ],
)
def test_underline_without_a_paragraph_is_not_a_setext_heading(source: str) -> None:
    assert names(source) in ([], ["Heading"])


def test_setext_level_follows_the_underline() -> None:
    source = "Top\n===\n\nChild\n---\n"

    assert names(source) == ["Top", "Top/Child"]


def test_section_includes_its_subsections() -> None:
    source = "# A\n\n## B\n\ntext\n\n## C\n\n# D\n"

    sections = by_name(source)

    assert (sections["A"].line_start, sections["A"].line_end) == (1, 7)
    assert (sections["A/B"].line_start, sections["A/B"].line_end) == (3, 5)
    assert (sections["A/C"].line_start, sections["A/C"].line_end) == (7, 7)


def test_trailing_blank_lines_are_not_part_of_a_section() -> None:
    sections = by_name("# A\ntext\n\n\n# B\n")

    assert sections["A"].line_end == 2


def test_last_section_runs_to_the_end_of_the_file() -> None:
    assert by_name("# A\ntext\nmore\n")["A"].line_end == 3
    assert by_name("# A\ntext\nmore")["A"].line_end == 3


def test_section_without_a_body_covers_only_its_heading() -> None:
    sections = by_name("# A\n# B\n")

    assert (sections["A"].line_start, sections["A"].line_end) == (1, 1)


def test_text_before_the_first_heading_belongs_to_no_section() -> None:
    (section,) = parse_markdown("Intro\n\n# A\n")

    assert section.line_start == 3


def test_line_endings_do_not_change_the_ranges() -> None:
    source = "# A\n\ntext\n\n## B\n\nmore\n"

    unix = parse_markdown(source)

    assert parse_markdown(source.replace("\n", "\r\n")) == unix
    assert parse_markdown(source.replace("\n", "\r")) == unix


def test_a_skipped_heading_level_nests_under_the_closest_parent() -> None:
    sections = by_name("# A\n\n### C\n\n## B\n")

    assert sections["A/C"].parent == "A"
    assert sections["A/B"].parent == "A"


def test_a_heading_level_that_returns_closes_the_deeper_ones() -> None:
    assert names("# A\n## B\n### C\n## D\n# E\n## F\n") == [
        "A",
        "A/B",
        "A/B/C",
        "A/D",
        "E",
        "E/F",
    ]


def test_top_level_section_has_no_parent() -> None:
    sections = by_name("# A\n## B\n")

    assert sections["A"].parent is None
    assert sections["A/B"].parent == "A"


def test_repeated_titles_get_a_number() -> None:
    assert names("# A\n## Example\n## Example\n## Example\n") == [
        "A",
        "A/Example",
        "A/Example (2)",
        "A/Example (3)",
    ]


def test_repeated_titles_under_different_parents_stay_unnumbered() -> None:
    assert names("# A\n## Example\n# B\n## Example\n") == [
        "A",
        "A/Example",
        "B",
        "B/Example",
    ]


def test_a_number_never_collides_with_a_title_that_looks_like_one() -> None:
    qualified = names("# A\n## Example\n## Example (2)\n## Example\n")

    assert len(qualified) == len(set(qualified)) == 4


def test_children_of_a_repeated_title_use_its_numbered_name() -> None:
    assert names("# Example\n## Child\n# Example\n## Child\n") == [
        "Example",
        "Example/Child",
        "Example (2)",
        "Example (2)/Child",
    ]


def test_slash_in_a_title_does_not_split_the_name() -> None:
    (section,) = parse_markdown("# Input/Output\n")

    assert section.qualified_name == "Input-Output"
    assert section.title == "Input/Output"


@pytest.mark.parametrize(
    ("max_depth", "expected"),
    [
        (0, []),
        (1, ["A", "E"]),
        (2, ["A", "A/B", "A/D", "E", "E/F"]),
        (3, ["A", "A/B", "A/B/C", "A/D", "E", "E/F"]),
        (None, ["A", "A/B", "A/B/C", "A/D", "E", "E/F"]),
    ],
)
def test_max_depth_limits_sections(max_depth: int | None, expected: list[str]) -> None:
    source = "# A\n## B\n### C\n## D\n# E\n## F\n"

    assert names(source, max_depth) == expected


def test_max_depth_counts_nesting_and_not_heading_levels() -> None:
    assert names("# A\n#### B\n", 2) == ["A", "A/B"]


def test_max_depth_does_not_shorten_a_section() -> None:
    source = "# A\n\n## B\n\ntext\n"

    (section,) = parse_markdown(source, max_depth=1)

    assert section.line_end == 5


def test_empty_and_heading_free_documents_have_no_sections() -> None:
    assert parse_markdown("") == []
    assert parse_markdown("Just text.\n\nMore text.\n") == []
