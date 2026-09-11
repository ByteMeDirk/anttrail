"""Terminal interface for anttrail."""
from __future__ import annotations

import argparse
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version
from pydoc import describe

from anttrail.graph import GraphGenerator

DISTRIBUTION_NAME = "anttrail"

def get_version() -> str:
    """Returns the installed package version."""
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return "0+unknown"

def existing_directory(value:str) -> Path:
    """Handle CLI path value."""
    path = Path(value).expanduser()

    if not path.is_dir():
        raise argparse.ArgumentTypeError(
            f"Directory {value} does not exist."
        )
    return path.resolve()


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        prog="anttrail",
        description="Generate a graph by crawling a directory, among other things.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--version", "-v",
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
        "--schema-version", "-s",
        metavar="VERSION",
        help="Schema version to use for graph generation.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        metavar="PATH",
        help=(
            "Output file where the graph will be written. If omitted, the graph "
            "is printed to the console as json. The filename extension selects the output "
            "format when supported."
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "If set, the graph is validated before writing the graph."
        )
    )
    parser.add_argument(
        "--silence-read-failure",
        action="store_true",
        help="Ignore read failures, such as unsupported file formats.",
    )
    parser.add_argument(
        "--silence-write-failure",
        action="store_true",
        help="Ignore write failures, such as unsupported output formats.",
    )
    parser.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity.",
    )

    return parser


def main() -> None:
    """Main entry point."""
    args = build_parser().parse_args()

    graph_generator = GraphGenerator(
        directory_path=args.directory,
        schema_version=args.schema_version,
        output_path=args.output,
        silence_read_failure=args.silence_read_failure,
        silence_write_failure=args.silence_write_failure,
    )

    graph_generator.run()

    if args.validate:
        graph_generator.validate()
        if graph_generator.graph_integrity:
            print(graph_generator.graph_integrity.model_dump_json())

    if args.output:
        graph_generator.write_file(Path(args.output))
    else:
        print(graph_generator.graph.model_dump_json())


if __name__ == "__main__":
    main()