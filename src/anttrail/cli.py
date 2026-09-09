"""Terminal interface for anttrail."""
from __future__ import annotations

import argparse
from pathlib import Path

from anttrail.graph import GraphGenerator


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate a graph by crawling a directory."
    )

    parser.add_argument(
        "--directory", "-d",
        required=True,
        type=str,
        help="Directory to be crawled for graph generation.",
    )
    parser.add_argument(
        "--schema-version", "-s",
        required=False,
        default="",
        type=str,
        help="Schema version to use for graph generation.",
    )
    parser.add_argument(
        "--output", "-o",
        required=False,
        default="",
        type=str,
        help=(
            "Output file where the graph will be written. If omitted, the graph "
            "is printed to the console as json. The filename extension selects the output "
            "format when supported."
        ),
    )
    parser.add_argument(
        "--validate", "-v",
        default=False,
        type=bool,
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

    return parser


def main() -> None:
    """Main entry point."""
    args = build_parser().parse_args()

    graph_generator = GraphGenerator(
        directory_path=Path(args.directory),
        schema_version=args.schema_version,
        output_path=Path(args.output),
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