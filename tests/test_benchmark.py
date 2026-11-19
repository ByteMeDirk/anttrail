"""Tests for the benchmark script."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from benchmarks import run_benchmark
from benchmarks.run_benchmark import (
    FIXTURE_DIRECTORY,
    Answer,
    Task,
    Verdict,
    full_graph_json,
    headings,
    judge,
    main,
    run_tasks,
    section_text,
)

USAGE_LINES = (FIXTURE_DIRECTORY / "docs" / "usage.md").read_text().splitlines()


def constant_answer(size_bytes: int) -> Callable[[Path], Answer]:
    def answer(root: Path) -> Answer:
        return Answer(calls=1, size_bytes=size_bytes)

    return answer


def test_every_task_has_a_baseline_that_reads_something() -> None:
    results = run_tasks(FIXTURE_DIRECTORY)

    assert [r.name for r in results] == [task.name for task in run_benchmark.TASKS]
    assert all(r.baseline.calls >= 1 and r.baseline.size_bytes > 0 for r in results)


def test_results_are_the_same_on_every_run() -> None:
    assert run_tasks(FIXTURE_DIRECTORY) == run_tasks(FIXTURE_DIRECTORY)


def test_full_graph_size_does_not_depend_on_the_checkout_location(
    tmp_path: Path,
) -> None:
    copy = tmp_path / "somewhere" / "deeper" / "sample_repo"
    shutil.copytree(FIXTURE_DIRECTORY, copy)

    assert full_graph_json(copy) == full_graph_json(FIXTURE_DIRECTORY)


def test_headings_skip_comments_inside_code_blocks() -> None:
    titles = [title for _, _, title in headings(USAGE_LINES)]

    assert "Configure pricing" in titles
    assert not any(title.startswith("The tax rate") for title in titles)


def test_section_text_includes_subsections_and_stops_at_the_next_sibling() -> None:
    text = section_text(USAGE_LINES, "Configure pricing")

    assert text.startswith("## Configure pricing\n")
    assert "### Rounding" in text
    assert "# The tax rate is a fraction" in text
    assert "## Limits" not in text
    assert not text.endswith("\n\n")


def test_section_text_rejects_an_unknown_heading() -> None:
    with pytest.raises(ValueError, match="No heading named 'Missing'"):
        section_text(USAGE_LINES, "Missing")


@pytest.mark.parametrize(
    ("anttrail", "expected"),
    [
        (None, Verdict.CANNOT_ANSWER),
        (Answer(calls=1, size_bytes=99), Verdict.SMALLER),
        (Answer(calls=1, size_bytes=100), Verdict.LARGER),
        (Answer(calls=1, size_bytes=101), Verdict.LARGER),
    ],
)
def test_judge_compares_bytes_read(anttrail: Answer | None, expected: Verdict) -> None:
    assert judge(Answer(calls=1, size_bytes=100), anttrail) is expected


def test_query_answer_takes_priority_over_the_full_graph() -> None:
    task = Task(
        name="example",
        question="Example?",
        baseline=constant_answer(100),
        anttrail_today=constant_answer(5_000),
        anttrail_query=constant_answer(50),
    )

    (result,) = run_tasks(FIXTURE_DIRECTORY, [task])

    assert result.verdict is Verdict.SMALLER


def test_main_reports_without_failing_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "section_text" in output
    assert "This repository:" in output


def test_compact_graph_is_at_least_60_percent_smaller() -> None:
    full = len(full_graph_json(FIXTURE_DIRECTORY))
    compact = len(full_graph_json(FIXTURE_DIRECTORY, compact=True))

    assert compact <= full * 0.4


def test_check_passes_for_the_recorded_verdicts() -> None:
    assert main(["--check"]) == 0


def test_check_passes_when_every_answer_is_smaller() -> None:
    task = Task(
        name="example",
        question="Example?",
        baseline=constant_answer(100),
        anttrail_query=constant_answer(1),
    )

    assert main(["--check"], tasks=[task]) == 0


def test_check_passes_when_a_known_larger_answer_stays_larger() -> None:
    task = Task(
        name="example",
        question="Example?",
        baseline=constant_answer(100),
        anttrail_query=constant_answer(200),
        expected=Verdict.LARGER,
    )

    assert main(["--check"], tasks=[task]) == 0


def test_check_fails_when_an_answer_is_not_smaller(
    capsys: pytest.CaptureFixture[str],
) -> None:
    task = Task(
        name="example",
        question="Example?",
        baseline=constant_answer(100),
        anttrail_query=constant_answer(100),
    )

    assert main(["--check"], tasks=[task]) == 1
    assert "Unexpected verdict: example" in capsys.readouterr().err
