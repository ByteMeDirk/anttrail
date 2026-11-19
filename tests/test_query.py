"""Tests for the graph queries."""

from pathlib import Path

import pytest

from anttrail.graph import GraphGenerator
from anttrail.models import NodeType
from anttrail.query import GraphQuery, QueryError

MARKDOWN_ASSETS = Path(__file__).parent / "markdown_assets"
PYTHON_ASSETS = Path(__file__).parent / "python_assets"


def make_query(root: Path) -> GraphQuery:
    return GraphQuery(GraphGenerator(root).run(), root)


@pytest.fixture
def markdown_query() -> GraphQuery:
    return make_query(MARKDOWN_ASSETS)


@pytest.fixture
def python_query() -> GraphQuery:
    return make_query(PYTHON_ASSETS)


def test_outline_indents_sections_by_depth(markdown_query: GraphQuery) -> None:
    lines = markdown_query.outline("guide.md")

    assert lines[0] == "guide.md:1-26\tSection\tguide.md::Guide"
    assert lines[1].startswith("  guide.md:5-10\tSection\t")
    assert lines[3].startswith("    guide.md:14-16\tSection\t")


def test_outline_of_python_file_lists_members_below_classes(
    python_query: GraphQuery,
) -> None:
    lines = python_query.outline("shapes.py")

    assert "shapes.py:4-12\tClass\tshapes.py::Shape" in lines
    assert "  shapes.py:7-8\tMethod\tshapes.py::Shape.area" in lines
    assert any(line.startswith("    shapes.py:11-12\tMethod") for line in lines)


@pytest.mark.parametrize("file_id", ["missing.md", "docs", "guide.md::Guide"])
def test_outline_rejects_anything_but_a_file(
    markdown_query: GraphQuery, file_id: str
) -> None:
    with pytest.raises(QueryError, match="No file"):
        markdown_query.outline(file_id)


def test_find_ignores_case_and_matches_substrings(python_query: GraphQuery) -> None:
    lines = python_query.find("ARE")

    assert [line.split("\t")[2] for line in lines] == ["shapes.py::Shape.area"]


def test_find_filters_by_type(python_query: GraphQuery) -> None:
    all_matches = python_query.find("s")
    classes = python_query.find("s", NodeType.CLASS)

    assert len(classes) < len(all_matches)
    assert all("\tClass\t" in line for line in classes)


def test_find_reports_truncation(python_query: GraphQuery) -> None:
    lines = python_query.find("", limit=2)

    assert len(lines) == 3
    assert lines[-1].startswith("(showing 2 of ")


def test_find_without_matches_returns_nothing(python_query: GraphQuery) -> None:
    assert python_query.find("no such name") == []


def test_find_lists_nodes_without_lines_by_path(python_query: GraphQuery) -> None:
    assert python_query.find("pkg", NodeType.DIRECTORY) == ["pkg\tDirectory\tpkg"]


def test_at_names_the_innermost_section_then_its_ancestors(
    markdown_query: GraphQuery,
) -> None:
    lines = markdown_query.at("guide.md:19")

    assert [line.split("\t")[2] for line in lines] == [
        "guide.md::Guide/Usage/Example (2)",
        "guide.md::Guide/Usage",
        "guide.md::Guide",
        "guide.md",
    ]


def test_at_names_a_python_method(python_query: GraphQuery) -> None:
    lines = python_query.at("shapes.py:8")

    assert lines[0].endswith("shapes.py::Shape.area")
    assert lines[-1] == "shapes.py\tFile\tshapes.py"


def test_at_a_line_outside_any_node_names_the_file(python_query: GraphQuery) -> None:
    assert python_query.at("shapes.py:3") == ["shapes.py\tFile\tshapes.py"]


@pytest.mark.parametrize("location", ["shapes.py", "shapes.py:x", "shapes.py:0"])
def test_at_rejects_a_malformed_location(
    python_query: GraphQuery, location: str
) -> None:
    with pytest.raises(QueryError, match="PATH:LINE"):
        python_query.at(location)


def test_at_rejects_an_unknown_file(python_query: GraphQuery) -> None:
    with pytest.raises(QueryError, match="No file"):
        python_query.at("missing.py:1")


def test_show_returns_the_lines_of_a_section(markdown_query: GraphQuery) -> None:
    assert markdown_query.show("guide.md::Guide/Usage/Example (2)") == [
        "### Example",
        "",
        "Second example.",
    ]


def test_show_returns_the_lines_of_a_symbol(python_query: GraphQuery) -> None:
    assert python_query.show("shapes.py::Shape.area") == [
        "    def area(self):",
        "        return 0",
    ]


def test_show_rejects_an_unknown_id(markdown_query: GraphQuery) -> None:
    with pytest.raises(QueryError, match="No node"):
        markdown_query.show("guide.md::Missing")


def test_show_rejects_a_node_without_lines(markdown_query: GraphQuery) -> None:
    with pytest.raises(QueryError, match="no line range"):
        markdown_query.show("guide.md")


def test_show_rejects_a_file_that_changed_since_the_crawl(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Title\n\nBody.\n", encoding="utf-8")
    query = make_query(tmp_path)
    note.write_text("# Title\n", encoding="utf-8")

    with pytest.raises(QueryError, match="changed since the crawl"):
        query.show("note.md::Title")


def test_show_does_not_read_a_symlink_that_leaves_the_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# Secret\n", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    (root / "link.md").symlink_to(outside)
    query = make_query(root.resolve())

    with pytest.raises(QueryError, match="outside"):
        query.show("link.md::Secret")
