"""Compare AntTrail answers with plain-text baselines.

Each task is a question that an agent might ask about a repository. For each task, the
script records how many tool calls and how many bytes of output the agent needs when it
uses text tools (`ls`, `grep`, and reading a file), and when it uses AntTrail.

The script needs no network access and no language model. The text-tool baselines are
simulated in Python, with the same output format as the real tools, so the sizes are the
same on every operating system. Run it from the repository root:

    uv run python benchmarks/run_benchmark.py
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Sequence
from enum import Enum
from functools import cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from anttrail.graph import COMPACT_EXCLUDE, GraphGenerator
from anttrail.models import NodeType
from anttrail.query import GraphQuery

BENCHMARKS_DIRECTORY = Path(__file__).resolve().parent
FIXTURE_DIRECTORY = BENCHMARKS_DIRECTORY / "fixtures" / "sample_repo"
REPOSITORY_DIRECTORY = BENCHMARKS_DIRECTORY.parent

# The real graph contains absolute paths and a timestamp. Replacing both with fixed
# values keeps the measured size the same wherever the repository is checked out.
PLACEHOLDER_ROOT = "/work/sample"
PLACEHOLDER_TIMESTAMP = "2026-01-01T00:00:00.000000Z"

HEADING_PATTERN = re.compile(r"^(#{1,6}) +(.*?)(?: +#+)? *$")
FENCE_PREFIXES = ("```", "~~~")


class Answer(BaseModel):
    """What an agent spends to get one answer."""

    model_config = ConfigDict(frozen=True)

    calls: int
    size_bytes: int


class Verdict(Enum):
    """How AntTrail's answer compares with the text-tool baseline."""

    SMALLER = "smaller"
    LARGER = "larger"
    CANNOT_ANSWER = "cannot answer"


class Task(BaseModel):
    """A question, and the ways to answer it.

    `anttrail_today` is what AntTrail did before the query options: print the full
    graph. `anttrail_query` is the targeted answer from Stage 3 of
    `docs/phase-3-strategy.md`, or `None` if no query option answers the question.
    `expected` is the verdict that `--check` accepts. It is `SMALLER` unless the
    comparison is known to favor text tools, and a task that sets another value says why.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    question: str
    baseline: Callable[[Path], Answer]
    anttrail_today: Callable[[Path], Answer] | None = None
    anttrail_query: Callable[[Path], Answer] | None = None
    expected: Verdict = Verdict.SMALLER


class TaskResult(BaseModel):
    """The measured answers for one task."""

    model_config = ConfigDict(frozen=True)

    name: str
    question: str
    baseline: Answer
    anttrail_today: Answer | None
    anttrail_query: Answer | None
    verdict: Verdict
    expected: Verdict


class Scale(BaseModel):
    """The size of a full graph, and how long the crawl took."""

    model_config = ConfigDict(frozen=True)

    node_count: int
    edge_count: int
    size_bytes: int
    compact_size_bytes: int
    crawl_seconds: float


def size_of(text: str) -> int:
    """Return the number of bytes in `text` when encoded as UTF-8."""
    return len(text.encode("utf-8"))


def join_lines(lines: Sequence[str]) -> str:
    """Join lines the way a terminal tool prints them, one per line."""
    return "".join(f"{line}\n" for line in lines)


@cache
def full_graph_json(root: Path, compact: bool = False) -> str:
    """Return the graph of `root` as JSON that ignores where `root` is.

    With `compact`, the paths and edges are left out, as `anttrail --compact` does.
    """
    graph = (
        GraphGenerator(root)
        .run()
        .model_dump(mode="json", exclude=COMPACT_EXCLUDE if compact else None)
    )
    graph["created_at"] = PLACEHOLDER_TIMESTAMP
    for node in graph["nodes"]:
        if "path" in node:
            relative = Path(node["path"]).relative_to(root).as_posix()
            node["path"] = (
                PLACEHOLDER_ROOT
                if relative == "."
                else f"{PLACEHOLDER_ROOT}/{relative}"
            )
    return json.dumps(graph, separators=(",", ":"), ensure_ascii=False)


def headings(lines: Sequence[str]) -> list[tuple[int, int, str]]:
    """Return `(line index, level, title)` for each Markdown heading outside code."""
    found: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(FENCE_PREFIXES):
            in_fence = not in_fence
        elif not in_fence and (match := HEADING_PATTERN.match(line)):
            found.append((index, len(match.group(1)), match.group(2)))
    return found


def section_text(lines: Sequence[str], title: str) -> str:
    """Return the lines under the heading `title`, including its subsections.

    The section runs from the heading to the line before the next heading of the same
    or a higher level, without trailing blank lines. This is the best case for text
    tools: it assumes the agent reads exactly the right lines.

    Raises:
        ValueError: If no heading has this title.
    """
    found = headings(lines)
    for position, (start, level, found_title) in enumerate(found):
        if found_title != title:
            continue
        end = next(
            (index for index, later, _ in found[position + 1 :] if later <= level),
            len(lines),
        )
        section = list(lines[start:end])
        while section and not section[-1].strip():
            section.pop()
        return join_lines(section)
    raise ValueError(f"No heading named {title!r}")


def read_lines(path: Path) -> list[str]:
    """Read a text file as a list of lines."""
    return path.read_text(encoding="utf-8").splitlines()


def full_graph_answer(root: Path) -> Answer:
    """Answer by printing the whole graph, which is all AntTrail can do today."""
    return Answer(calls=1, size_bytes=size_of(full_graph_json(root)))


def list_directory_baseline(root: Path) -> Answer:
    """`ls docs`"""
    names = sorted(path.name for path in (root / "docs").iterdir())
    return Answer(calls=1, size_bytes=size_of(join_lines(names)))


def file_outline_baseline(root: Path) -> Answer:
    """`grep -n '^#' docs/usage.md`"""
    lines = read_lines(root / "docs" / "usage.md")
    matches = [
        f"{number}:{line}"
        for number, line in enumerate(lines, 1)
        if line.startswith("#")
    ]
    return Answer(calls=1, size_bytes=size_of(join_lines(matches)))


def section_text_baseline(root: Path) -> Answer:
    """`grep -n '^#' docs/usage.md`, then read the lines of one section."""
    outline = file_outline_baseline(root)
    lines = read_lines(root / "docs" / "usage.md")
    text = section_text(lines, "Configure pricing")
    return Answer(calls=2, size_bytes=outline.size_bytes + size_of(text))


def find_class_baseline(root: Path) -> Answer:
    """`grep -rn 'class Cart' src`

    The output gives the first line of the class only. The agent needs another call to
    learn where the class ends, which this baseline does not count.
    """
    matches: list[str] = []
    for path in sorted((root / "src").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(read_lines(path), 1):
            if "class Cart" in line:
                matches.append(f"{relative}:{number}:{line}")
    return Answer(calls=1, size_bytes=size_of(join_lines(matches)))


def enclosing_symbol_baseline(root: Path) -> Answer:
    """Read `src/shop/cart.py` and scan upward from a line to find its function."""
    text = (root / "src" / "shop" / "cart.py").read_text(encoding="utf-8")
    return Answer(calls=1, size_bytes=size_of(text))


def graph_query(root: Path) -> GraphQuery:
    """Crawl `root` and return the queries that answer questions about it."""
    return GraphQuery(GraphGenerator(root).run(), root)


def file_outline_query(root: Path) -> Answer:
    """`anttrail DIRECTORY --outline docs/usage.md`"""
    lines = graph_query(root).outline("docs/usage.md")
    return Answer(calls=1, size_bytes=size_of(join_lines(lines)))


def section_text_query(root: Path) -> Answer:
    """`--find` the section to learn its ID, then `--show` that ID."""
    query = graph_query(root)
    found = query.find("Configure pricing", NodeType.SECTION)
    section_id = found[0].split("\t")[2]
    text = query.show(section_id)
    return Answer(
        calls=2, size_bytes=size_of(join_lines(found)) + size_of(join_lines(text))
    )


def find_class_query(root: Path) -> Answer:
    """`anttrail DIRECTORY --find Cart --type Class`

    The output gives the first and last line of the class.
    """
    lines = graph_query(root).find("Cart", NodeType.CLASS)
    return Answer(calls=1, size_bytes=size_of(join_lines(lines)))


def enclosing_symbol_query(root: Path) -> Answer:
    """`anttrail DIRECTORY --at src/shop/cart.py:LINE`, for the line of `subtotal`."""
    cart = root / "src" / "shop" / "cart.py"
    line = next(n for n, text in enumerate(read_lines(cart), 1) if "subtotal" in text)
    lines = graph_query(root).at(f"src/shop/cart.py:{line}")
    return Answer(calls=1, size_bytes=size_of(join_lines(lines)))


# The `expected` verdicts record where text tools are known to win on bytes alone.
# `ls` prints bare names, and a one-line `grep` result or a short list of headings is
# smaller than an AntTrail line, which also carries the line range, type, and ID.
TASKS: tuple[Task, ...] = (
    Task(
        name="list_directory",
        question="Which files are in docs/?",
        baseline=list_directory_baseline,
        anttrail_today=full_graph_answer,
        expected=Verdict.LARGER,
    ),
    Task(
        name="file_outline",
        question="What are the headings of docs/usage.md?",
        baseline=file_outline_baseline,
        anttrail_today=full_graph_answer,
        anttrail_query=file_outline_query,
        expected=Verdict.LARGER,
    ),
    Task(
        name="section_text",
        question="What does docs/usage.md say under 'Configure pricing'?",
        baseline=section_text_baseline,
        anttrail_today=full_graph_answer,
        anttrail_query=section_text_query,
    ),
    Task(
        name="find_class",
        question="Where is the class Cart defined?",
        baseline=find_class_baseline,
        anttrail_today=full_graph_answer,
        anttrail_query=find_class_query,
        expected=Verdict.LARGER,
    ),
    Task(
        name="enclosing_symbol",
        question="Which method contains the 'subtotal' line of cart.py?",
        baseline=enclosing_symbol_baseline,
        anttrail_today=full_graph_answer,
        anttrail_query=enclosing_symbol_query,
    ),
)


def judge(baseline: Answer, anttrail: Answer | None) -> Verdict:
    """Compare AntTrail's answer with the baseline by the bytes the agent reads."""
    if anttrail is None:
        return Verdict.CANNOT_ANSWER
    if anttrail.size_bytes < baseline.size_bytes:
        return Verdict.SMALLER
    return Verdict.LARGER


def run_tasks(root: Path, tasks: Sequence[Task] = TASKS) -> list[TaskResult]:
    """Measure every task against the data in `root`."""
    results: list[TaskResult] = []
    for task in tasks:
        baseline = task.baseline(root)
        today = task.anttrail_today(root) if task.anttrail_today else None
        query = task.anttrail_query(root) if task.anttrail_query else None
        results.append(
            TaskResult(
                name=task.name,
                question=task.question,
                baseline=baseline,
                anttrail_today=today,
                anttrail_query=query,
                verdict=judge(baseline, query or today),
                expected=task.expected,
            )
        )
    return results


def measure_scale(root: Path) -> Scale:
    """Crawl `root` once and report the size of its full graph."""
    started = time.perf_counter()
    graph = GraphGenerator(root).run()
    crawl_seconds = time.perf_counter() - started
    return Scale(
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        size_bytes=size_of(full_graph_json(root)),
        compact_size_bytes=size_of(full_graph_json(root, compact=True)),
        crawl_seconds=crawl_seconds,
    )


def describe(answer: Answer | None) -> str:
    """Format an answer for the results table."""
    if answer is None:
        return "-"
    unit = "call" if answer.calls == 1 else "calls"
    return f"{answer.calls} {unit}, {answer.size_bytes:,} B"


def render_results(results: Sequence[TaskResult]) -> str:
    """Format the task results as an aligned text table."""
    header = ("Task", "Text tools", "AntTrail today", "AntTrail query", "Verdict")
    rows = [
        (
            result.name,
            describe(result.baseline),
            describe(result.anttrail_today),
            describe(result.anttrail_query),
            result.verdict.value,
        )
        for result in results
    ]
    widths = [max(len(row[column]) for row in (header, *rows)) for column in range(5)]

    def format_row(row: Sequence[str]) -> str:
        return "  ".join(
            cell.ljust(width) for cell, width in zip(row, widths, strict=True)
        )

    lines = [format_row(header), format_row(["-" * width for width in widths])]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)


def render_scale(label: str, scale: Scale) -> str:
    """Format one scale measurement."""
    saved = 1 - scale.compact_size_bytes / scale.size_bytes
    return (
        f"{label}: {scale.node_count:,} nodes, {scale.edge_count:,} edges, "
        f"{scale.size_bytes:,} B full graph, {scale.compact_size_bytes:,} B compact "
        f"({saved:.0%} smaller), crawl {scale.crawl_seconds * 1000:.0f} ms"
    )


def main(argv: Sequence[str] | None = None, tasks: Sequence[Task] = TASKS) -> int:
    """Run the benchmark and return the process exit status."""
    parser = argparse.ArgumentParser(
        description="Compare AntTrail answers with plain-text baselines."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Exit with status 1 if any task's verdict differs from the verdict "
            "that the task expects."
        ),
    )
    args = parser.parse_args(argv)

    results = run_tasks(FIXTURE_DIRECTORY, tasks)
    print(render_results(results))
    print()
    print("Scale (the crawl time varies from run to run):")
    print("  " + render_scale("Fixture", measure_scale(FIXTURE_DIRECTORY)))
    print("  " + render_scale("This repository", measure_scale(REPOSITORY_DIRECTORY)))

    if args.check:
        failed = [r.name for r in results if r.verdict is not r.expected]
        if failed:
            print(f"\nUnexpected verdict: {', '.join(failed)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
