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
