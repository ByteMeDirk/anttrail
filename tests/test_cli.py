"""Tests for the command line interface."""

import json
from pathlib import Path

import pytest

from anttrail.cli import main

ASSETS = Path(__file__).parent / "assets"


def test_bare_command_prints_graph_json(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(ASSETS)])

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

    main([str(ASSETS), "--output", str(output)])

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
