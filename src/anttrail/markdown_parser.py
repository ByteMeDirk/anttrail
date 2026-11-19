"""Extract sections from Markdown source."""

import re

from pydantic import BaseModel, ConfigDict

# A heading has at most 3 spaces of indent, so a line with 4 or more is code.
ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
SETEXT_UNDERLINE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
FENCE_OPENING = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
# A line that starts one of these cannot be the text of a setext heading.
NOT_HEADING_TEXT = re.compile(r"^ {0,3}(?:[-*+] |\d+[.)] |>|\|)")
FRONT_MATTER_DELIMITER = "---"
FRONT_MATTER_ENDINGS = frozenset({"---", "..."})


class Section(BaseModel):
    """A heading and the lines it covers."""

    model_config = ConfigDict(frozen=True)

    qualified_name: str
    title: str
    line_start: int
    line_end: int
    parent: str | None


class _Heading(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    level: int
    line_start: int


def parse_markdown(source: str, max_depth: int | None = None) -> list[Section]:
    """
    List the sections of a Markdown document, in document order.

    A section runs from its heading to the line before the next heading of the same or a
    higher level, or to the end of the document, without trailing blank lines. It
    includes its subsections. Text before the first heading belongs to no section.

    The qualified name is the titles of the enclosing headings and the heading itself,
    joined with `/`. A `/` inside a title becomes `-`. When a name is already taken, a
    number is added, as in `Example (2)`.

    Headings inside fenced code blocks, in YAML front matter, or in indented code are
    ignored. A setext heading (text with a `===` or `---` underline) is recognized only
    when its text is a single line.

    Args:
        source: The document text.
        max_depth: Levels of sections to return. A top-level heading has depth 1, and a
            heading nested in it has depth 2, whatever their heading levels are. None
            means no limit.
    """
    if max_depth == 0:
        return []

    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headings = _find_headings(lines)
    return _build_sections(headings, lines, max_depth)


def _find_headings(lines: list[str]) -> list[_Heading]:
    headings: list[_Heading] = []
    fence: str | None = None
    previous_is_text = False
    index = _front_matter_end(lines)

    while index < len(lines):
        line = lines[index]
        line_number = index + 1
        index += 1

        if fence is not None:
            if _closes_fence(line, fence):
                fence = None
            continue

        opening = FENCE_OPENING.match(line)
        if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(2)):
            fence = opening.group(1)
            previous_is_text = False
            continue

        atx = ATX_HEADING.match(line)
        if atx:
            title = (atx.group(2) or "").strip()
            if title:
                headings.append(
                    _Heading(
                        title=title,
                        level=len(atx.group(1)),
                        line_start=line_number,
                    )
                )
            previous_is_text = False
            continue

        underline = SETEXT_UNDERLINE.match(line)
        if underline and previous_is_text:
            title = lines[line_number - 2].strip()
            level = 1 if underline.group(1)[0] == "=" else 2
            headings.append(
                _Heading(title=title, level=level, line_start=line_number - 1)
            )
            previous_is_text = False
            continue

        previous_is_text = _can_start_setext_heading(line)

    return headings


def _front_matter_end(lines: list[str]) -> int:
    """Return the index of the first line after YAML front matter, or 0 if there is none."""
    if lines[0].rstrip() != FRONT_MATTER_DELIMITER:
        return 0
    for index in range(1, len(lines)):
        if lines[index].rstrip() in FRONT_MATTER_ENDINGS:
            return index + 1
    return 0


def _closes_fence(line: str, fence: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= len(fence) and set(stripped) == {fence[0]}


def _can_start_setext_heading(line: str) -> bool:
    is_indented_code = line.startswith("    ") or line.startswith("\t")
    return (
        bool(line.strip()) and not is_indented_code and not NOT_HEADING_TEXT.match(line)
    )


def _build_sections(
    headings: list[_Heading], lines: list[str], max_depth: int | None
) -> list[Section]:
    sections: list[Section] = []
    open_headings: list[tuple[int, str]] = []
    used_names: set[str] = set()

    for position, heading in enumerate(headings):
        while open_headings and open_headings[-1][0] >= heading.level:
            open_headings.pop()
        parent = open_headings[-1][1] if open_headings else None
        qualified_name = _unique_name(parent, heading.title, used_names)
        open_headings.append((heading.level, qualified_name))

        depth = len(open_headings)
        if max_depth is not None and depth > max_depth:
            continue

        sections.append(
            Section(
                qualified_name=qualified_name,
                title=heading.title,
                line_start=heading.line_start,
                line_end=_section_end(headings, position, lines),
                parent=parent,
            )
        )
    return sections


def _unique_name(parent: str | None, title: str, used_names: set[str]) -> str:
    segment = title.replace("/", "-")
    candidate = segment
    number = 1
    while True:
        name = f"{parent}/{candidate}" if parent else candidate
        if name not in used_names:
            used_names.add(name)
            return name
        number += 1
        candidate = f"{segment} ({number})"


def _section_end(headings: list[_Heading], position: int, lines: list[str]) -> int:
    heading = headings[position]
    next_start = next(
        (
            later.line_start
            for later in headings[position + 1 :]
            if later.level <= heading.level
        ),
        len(lines) + 1,
    )
    line_end = next_start - 1
    while line_end > heading.line_start and not lines[line_end - 1].strip():
        line_end -= 1
    return line_end
