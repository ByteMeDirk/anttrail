"""Terminal interface for anttrail."""

import argparse
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from anttrail.files import UnsupportedWriteFormatError
from anttrail.graph import (
    DEFAULT_IGNORED_DIRECTORIES,
    DEFAULT_SCHEMA_VERSION,
    GraphGenerator,
)
from anttrail.models import BaseGraph, NodeType
from anttrail.python_parser import SourceParseError
from anttrail.query import DEFAULT_FIND_LIMIT, GraphQuery, QueryError

DISTRIBUTION_NAME = "anttrail"


def get_version() -> str:
    """Returns the installed package version."""
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return "0+unknown"


def existing_directory(value: str) -> Path:
    """Parse a directory argument into an absolute path that must exist."""
    path = Path(value).expanduser()

    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Directory {value} does not exist.")
    return path.resolve()


def integer_at_least(minimum: int) -> Callable[[str], int]:
    """Return a CLI value parser for an integer that is `minimum` or more."""

    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value} is not an integer.") from None
        if number < minimum:
            raise argparse.ArgumentTypeError(f"{value} is less than {minimum}.")
        return number

    return parse


def node_type(value: str) -> NodeType:
    """Parse a node type name, ignoring case."""
    for member in NodeType:
        if member.value.casefold() == value.casefold():
            return member
    names = ", ".join(member.value for member in NodeType)
    raise argparse.ArgumentTypeError(f"{value} is not one of {names}.")


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        prog="anttrail",
        description="Generate a graph by crawling a directory, among other things.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {get_version()}",
        help="Show version information and exit.",
    )
    parser.add_argument(
        "directory",
        metavar="DIRECTORY",
        type=existing_directory,
        help="Directory to be crawled for graph generation.",
    )
    parser.add_argument(
        "--schema-version",
        "-s",
        default=DEFAULT_SCHEMA_VERSION,
        metavar="VERSION",
        help="Schema version to use for graph generation.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        metavar="PATH",
        help=(
            "Output file where the graph will be written. If omitted, the graph "
            "is printed to the console as JSON. The filename extension selects the "
            "output format: .json or .yaml."
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="If set, the graph is validated before writing the graph.",
    )
    parser.add_argument(
        "--silence-read-failure",
        action="store_true",
        help=(
            "Skip directories, Python files, and Markdown files that cannot be read "
            "instead of failing."
        ),
    )
    parser.add_argument(
        "--silence-write-failure",
        action="store_true",
        help="Do not fail when the output format is unsupported.",
    )

    parser.add_argument(
        "--symbol-depth",
        type=integer_at_least(0),
        metavar="N",
        help=(
            "Levels of Python symbols to add below each .py file: 1 adds top-level "
            "classes, functions and variables, 2 adds class members, and so on. "
            "0 adds none. If omitted, all levels are added."
        ),
    )
    parser.add_argument(
        "--section-depth",
        type=integer_at_least(0),
        metavar="N",
        help=(
            "Levels of Markdown sections to add below each .md file: 1 adds top-level "
            "headings, 2 adds the headings nested in them, and so on. 0 adds none. "
            "If omitted, all levels are added."
        ),
    )
    parser.add_argument(
        "--no-ignore",
        action="store_true",
        help=(
            "Include directories that are skipped by default: "
            f"{', '.join(sorted(DEFAULT_IGNORED_DIRECTORIES))}."
        ),
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Leave the path of each node and all edges out of the graph output.",
    )

    queries = parser.add_argument_group(
        "queries",
        "Print a short answer instead of the graph. Each line is "
        "PATH:LINE_START-LINE_END, a tab, the node type, a tab, and the node ID.",
    )
    query = queries.add_mutually_exclusive_group()
    query.add_argument(
        "--outline",
        metavar="PATH",
        help="List the sections or symbols of one file, indented by depth.",
    )
    query.add_argument(
        "--find",
        metavar="TEXT",
        help="List the nodes whose name contains TEXT, ignoring case.",
    )
    query.add_argument(
        "--at",
        metavar="PATH:LINE",
        help="Name the section or symbol that contains a line, then its ancestors.",
    )
    query.add_argument(
        "--show",
        metavar="ID",
        help="Print the lines of one section or symbol, and nothing else.",
    )
    queries.add_argument(
        "--type",
        type=node_type,
        metavar="TYPE",
        help=(
            "With --find, keep only nodes of this type: "
            f"{', '.join(member.value for member in NodeType)}."
        ),
    )
    queries.add_argument(
        "--limit",
        type=integer_at_least(1),
        metavar="N",
        help=f"With --find, the most matches to list. Default: {DEFAULT_FIND_LIMIT}.",
    )

    return parser


def check_option_combinations(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Exit with a usage error for options that do not work together."""
    if args.find is None and (args.type is not None or args.limit is not None):
        parser.error("--type and --limit need --find.")
    is_query = any(
        option is not None for option in (args.outline, args.find, args.at, args.show)
    )
    if is_query and (args.output or args.compact):
        parser.error(
            "A query prints lines, so it cannot be used with --output or --compact."
        )


def answer_query(args: argparse.Namespace, graph: BaseGraph) -> list[str] | None:
    """Answer the query option that was given, or return None if there is none."""
    query = GraphQuery(graph, args.directory)
    if args.outline is not None:
        return query.outline(args.outline)
    if args.find is not None:
        return query.find(args.find, args.type, args.limit or DEFAULT_FIND_LIMIT)
    if args.at is not None:
        return query.at(args.at)
    if args.show is not None:
        return query.show(args.show)
    return None


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    check_option_combinations(parser, args)

    graph_generator = GraphGenerator(
        directory_path=args.directory,
        schema_version=args.schema_version,
        ignored_directories=(
            frozenset() if args.no_ignore else DEFAULT_IGNORED_DIRECTORIES
        ),
        symbol_depth=args.symbol_depth,
        section_depth=args.section_depth,
        silence_read_failure=args.silence_read_failure,
        silence_write_failure=args.silence_write_failure,
        compact=args.compact,
    )

    try:
        graph = graph_generator.run()

        if args.validate:
            print(graph_generator.validate().model_dump_json())

        answer = answer_query(args, graph)
        if answer is not None:
            print("\n".join(answer))
        elif args.output:
            graph_generator.write_file(args.output)
        else:
            print(graph_generator.to_json())
    except (
        OSError,
        SourceParseError,
        UnsupportedWriteFormatError,
        QueryError,
    ) as error:
        raise SystemExit(f"anttrail: error: {error}") from error


if __name__ == "__main__":
    main()
