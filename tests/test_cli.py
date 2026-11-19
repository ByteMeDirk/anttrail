"""Tests for the command line interface."""

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from anttrail import cli
from anttrail.cli import main

ASSETS = Path(__file__).parent / "assets"


def test_bare_command_prints_graph_json(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(ASSETS), "--section-depth", "0"])

    graph = json.loads(capsys.readouterr().out)
    assert len(graph["nodes"]) == 8
    assert len(graph["edges"]) == 7
    assert isinstance(graph["schema_version"], str)


def test_schema_version_is_stamped_on_graph(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(ASSETS), "--schema-version", "2.0"])

    assert json.loads(capsys.readouterr().out)["schema_version"] == "2.0"


def test_validate_prints_integrity_report_before_graph(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(ASSETS), "--validate"])

    report_line, _graph_line = capsys.readouterr().out.splitlines()
    assert json.loads(report_line)["is_valid"] is True


def test_output_option_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "graph.json"

    main([str(ASSETS), "--section-depth", "0", "--output", str(output)])

    assert len(json.loads(output.read_text(encoding="utf-8"))["nodes"]) == 8


def test_missing_directory_exits_with_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(tmp_path / "missing")])

    assert exit_info.value.code == 2


def test_unsupported_output_format_exits_with_one_line_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(ASSETS), "--output", str(tmp_path / "graph.txt")])

    assert str(exit_info.value).startswith("anttrail: error: Unsupported output format")


def test_silence_write_failure_exits_cleanly(tmp_path: Path) -> None:
    main(
        [
            str(ASSETS),
            "--output",
            str(tmp_path / "graph.txt"),
            "--silence-write-failure",
        ]
    )


PYTHON_ASSETS = Path(__file__).parent / "python_assets"


def symbol_ids(capsys: pytest.CaptureFixture[str]) -> set[str]:
    graph = json.loads(capsys.readouterr().out)
    return {node["id"] for node in graph["nodes"] if "::" in node["id"]}


def test_symbols_are_included_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(PYTHON_ASSETS)])

    assert "shapes.py::Shape.Style.color" in symbol_ids(capsys)


def test_symbol_depth_zero_matches_a_graph_without_symbols(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(PYTHON_ASSETS), "--symbol-depth", "0"])

    assert symbol_ids(capsys) == set()


def test_symbol_depth_one_limits_to_top_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(PYTHON_ASSETS), "--symbol-depth", "1"])

    ids = symbol_ids(capsys)
    assert "shapes.py::Shape" in ids
    assert "shapes.py::Shape.area" not in ids


@pytest.mark.parametrize("value", ["-1", "two"])
def test_invalid_symbol_depth_exits_with_usage_error(value: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(PYTHON_ASSETS), "--symbol-depth", value])

    assert exit_info.value.code == 2


def test_unparseable_python_file_exits_with_one_line_error(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        main([str(tmp_path)])

    message = str(exit_info.value)
    assert message.startswith("anttrail: error: ")
    assert "broken.py" in message
    assert "\n" not in message


def test_version_falls_back_when_package_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_found(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(cli, "version", raise_not_found)

    assert cli.get_version() == "0+unknown"


MARKDOWN_ASSETS = Path(__file__).parent / "markdown_assets"


def section_ids(capsys: pytest.CaptureFixture[str]) -> set[str]:
    graph = json.loads(capsys.readouterr().out)
    return {node["id"] for node in graph["nodes"] if node["type"] == "Section"}


def test_sections_are_included_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(MARKDOWN_ASSETS)])

    assert "guide.md::Guide/Install" in section_ids(capsys)


def test_section_depth_zero_matches_a_graph_without_sections(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(MARKDOWN_ASSETS), "--section-depth", "0"])

    assert section_ids(capsys) == set()


def test_section_depth_one_limits_to_top_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(MARKDOWN_ASSETS), "--section-depth", "1"])

    assert section_ids(capsys) == {
        "guide.md::Guide",
        "guide.md::Setext Title",
        "docs/notes.markdown::Notes",
    }


@pytest.mark.parametrize("value", ["-1", "two"])
def test_invalid_section_depth_exits_with_usage_error(value: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(MARKDOWN_ASSETS), "--section-depth", value])

    assert exit_info.value.code == 2


def test_undecodable_markdown_file_exits_with_one_line_error(tmp_path: Path) -> None:
    (tmp_path / "broken.md").write_bytes(b"# Bad \xff bytes\n")

    with pytest.raises(SystemExit) as exit_info:
        main([str(tmp_path)])

    message = str(exit_info.value)
    assert message.startswith("anttrail: error: ")
    assert "broken.md" in message
    assert "\n" not in message


MARKDOWN_ASSETS = Path(__file__).parent / "markdown_assets"


def test_outline_prints_lines_instead_of_the_graph(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(MARKDOWN_ASSETS), "--outline", "guide.md"])

    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line == "guide.md:1-26\tSection\tguide.md::Guide"


def test_find_limits_matches(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(MARKDOWN_ASSETS), "--find", "e", "--limit", "1"])

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("(showing 1 of ")


def test_find_type_ignores_case(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(MARKDOWN_ASSETS), "--find", "guide", "--type", "file"])

    assert capsys.readouterr().out == "guide.md\tFile\tguide.md\n"


def test_at_prints_the_containing_section(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(MARKDOWN_ASSETS), "--at", "guide.md:26"])

    assert "Deep detail" in capsys.readouterr().out.splitlines()[0]


def test_show_prints_only_the_section(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(MARKDOWN_ASSETS), "--show", "guide.md::Guide/Install"])

    output = capsys.readouterr().out
    assert output.startswith("## Install\n")
    assert "pip install thing" in output
    assert "## Usage" not in output


def test_query_error_exits_with_one_line_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(MARKDOWN_ASSETS), "--show", "guide.md::Missing"])

    assert str(exit_info.value).startswith("anttrail: error: No node")


@pytest.mark.parametrize(
    "options",
    [
        ["--outline", "guide.md", "--find", "x"],
        ["--type", "File"],
        ["--limit", "5"],
        ["--find", "x", "--limit", "0"],
        ["--find", "x", "--type", "Nonsense"],
        ["--find", "x", "--output", "out.json"],
        ["--find", "x", "--compact"],
    ],
)
def test_invalid_query_options_exit_with_usage_error(options: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(MARKDOWN_ASSETS), *options])

    assert exit_info.value.code == 2


def test_compact_leaves_out_paths_and_edges(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(MARKDOWN_ASSETS), "--compact"])

    graph = json.loads(capsys.readouterr().out)
    assert "edges" not in graph
    assert all("path" not in node for node in graph["nodes"])
    assert all("id" in node for node in graph["nodes"])


def test_compact_applies_to_written_json_and_yaml(tmp_path: Path) -> None:
    for name in ("graph.json", "graph.yaml"):
        main([str(MARKDOWN_ASSETS), "--compact", "--output", str(tmp_path / name)])

        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "edges" not in text
        assert "path" not in text
