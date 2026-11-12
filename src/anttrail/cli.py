"""Terminal interface for anttrail."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from anttrail.files import UnsupportedWriteFormatError
from anttrail.graph import (
    DEFAULT_IGNORED_DIRECTORIES,
    DEFAULT_SCHEMA_VERSION,
    GraphGenerator,
)

DISTRIBUTION_NAME = "anttrail"


def get_version() -> str:
    """Returns the installed package version."""
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return "0+unknown"


def existing_directory(value: str) -> Path:
    """Handle CLI path value."""
    path = Path(value).expanduser()

    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Directory {value} does not exist.")
    return path.resolve()


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
        help="Skip directories that cannot be read instead of failing.",
    )
    parser.add_argument(
        "--silence-write-failure",
        action="store_true",
        help="Do not fail when the output format is unsupported.",
    )

    parser.add_argument(
        "--no-ignore",
        action="store_true",
        help=(
            "Include directories that are skipped by default: "
            f"{', '.join(sorted(DEFAULT_IGNORED_DIRECTORIES))}."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    args = build_parser().parse_args(argv)

    graph_generator = GraphGenerator(
        directory_path=args.directory,
        schema_version=args.schema_version,
        ignored_directories=(
            frozenset() if args.no_ignore else DEFAULT_IGNORED_DIRECTORIES
        ),
        silence_read_failure=args.silence_read_failure,
        silence_write_failure=args.silence_write_failure,
    )

    try:
        graph_generator.run()

        if args.validate:
            print(graph_generator.validate().model_dump_json())

        if args.output:
            graph_generator.write_file(args.output)
        else:
            print(graph_generator.graph.model_dump_json())
    except (OSError, UnsupportedWriteFormatError) as error:
        raise SystemExit(f"anttrail: error: {error}") from error


if __name__ == "__main__":
    main()
