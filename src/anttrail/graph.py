"""The main Base GraphGenerator"""

import os
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar, cast

import yaml
from pydantic.main import IncEx

from anttrail.files import SupportedWriteFormats, UnsupportedWriteFormatError
from anttrail.markdown_parser import parse_markdown
from anttrail.models import (
    BaseEdge,
    BaseGraph,
    BaseNode,
    EntityRelationshipType,
    GraphIntegrity,
    NodeType,
)
from anttrail.python_parser import SourceParseError, parse_python

DEFAULT_SCHEMA_VERSION = "<unset>"
MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})
ParsedItem = TypeVar("ParsedItem")
PARENT_EDGE_TYPES = frozenset(
    {EntityRelationshipType.CONTAINS, EntityRelationshipType.DECLARES}
)
# Every path is the root plus the node ID, and every edge is a parent and a child
# that the node IDs already name, so the compact form leaves both out.
COMPACT_EXCLUDE = cast(IncEx, {"edges": True, "nodes": {"__all__": {"path": True}}})
DEFAULT_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)


class GraphGenerator:
    def __init__(
        self,
        directory_path: Path,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
        ignored_directories: frozenset[str] = DEFAULT_IGNORED_DIRECTORIES,
        symbol_depth: int | None = None,
        section_depth: int | None = None,
        silence_read_failure: bool = False,
        silence_write_failure: bool = False,
        compact: bool = False,
    ):
        """
        GraphGenerator builds a concise containment graph from a directory.
        The graph can then be used as an "anttrail" to traverse that directory.

        Args:
            directory_path: The directory to traverse.
            schema_version: The schema version stamped onto the graph.
            ignored_directories: Names of directories to leave out of the graph.
            symbol_depth: Levels of Python symbols to add below each file. None means
                no limit and 0 adds none.
            section_depth: Levels of Markdown sections to add below each file. None
                means no limit and 0 adds none.
            silence_read_failure: Skip, rather than raise on, unreadable directories
                and Python or Markdown files that cannot be read.
            silence_write_failure: Skip, rather than raise on, unsupported output formats.
            compact: Leave the path of each node and all edges out of the output.
        """
        self.root_path: Path = directory_path
        self.ignored_directories: frozenset[str] = ignored_directories
        self.symbol_depth: int | None = symbol_depth
        self.section_depth: int | None = section_depth
        self.silence_read_failure: bool = silence_read_failure
        self.silence_write_failure: bool = silence_write_failure
        self.compact: bool = compact

        self.graph: BaseGraph = BaseGraph(
            schema_version=schema_version,
            nodes=[
                BaseNode(
                    id=".",
                    path=self.root_path,
                    name=self.root_path.name,
                    type=NodeType.DIRECTORY,
                )
            ],
        )

    def to_json(self) -> str:
        """Return the graph as JSON, leaving out paths and edges if `compact` is set."""
        return self.graph.model_dump_json(
            exclude=COMPACT_EXCLUDE if self.compact else None
        )

    def write_file(self, file_path: Path) -> None:
        """
        Write the graph to a JSON or YAML file, chosen by the file extension.

        Args:
            file_path: The file to write.

        Raises:
            UnsupportedWriteFormatError: If the extension is not supported and
                write failures are not silenced.
        """
        if SupportedWriteFormats.JSON.check(file_path):
            file_path.write_text(self.to_json(), encoding="utf-8")
        elif SupportedWriteFormats.YAML.check(file_path):
            file_path.write_text(
                yaml.safe_dump(
                    self.graph.model_dump(
                        mode="json", exclude=COMPACT_EXCLUDE if self.compact else None
                    ),
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
        elif not self.silence_write_failure:
            raise UnsupportedWriteFormatError(
                f"Unsupported output format: `{file_path}`."
            )

    def _canonical_id(self, path: Path) -> str:
        """
        Return the canonical id of a path.

        Args:
            path (Path): The relevant path that requires a canonical id.

        Returns:
            str: The canonical id.
        """
        return path.relative_to(self.root_path).as_posix() or "."

    def _add_child(
        self,
        node: BaseNode,
        parent_id: str,
        relationship_type: EntityRelationshipType,
    ) -> None:
        """Add a node to the graph, linked to its parent by one edge."""
        self.graph.add_node(node)
        self.graph.add_edge(
            BaseEdge(
                id=f"{parent_id}|{relationship_type.value}|{node.id}",
                source=parent_id,
                type=relationship_type,
                target=node.id,
            )
        )

    def _build_node(self, artefact: Path, node_type: NodeType) -> None:
        """Add a directory or file node, contained by its parent directory."""
        node = BaseNode(
            id=self._canonical_id(artefact),
            path=artefact,
            name=artefact.name,
            type=node_type,
        )
        self._add_child(
            node,
            self._canonical_id(artefact.parent),
            EntityRelationshipType.CONTAINS,
        )

    def _parse_file(
        self, file_path: Path, parse: Callable[[bytes], list[ParsedItem]]
    ) -> list[ParsedItem]:
        """
        Read a file and parse it into the items it declares.

        Raises:
            SourceParseError: If the file cannot be read or parsed and read failures
                are not silenced.
        """
        try:
            return parse(file_path.read_bytes())
        except (OSError, SyntaxError, ValueError) as error:
            if self.silence_read_failure:
                return []
            raise SourceParseError(f"{file_path}: {error}") from error

    def _add_declaration(
        self,
        file_path: Path,
        node_type: NodeType,
        qualified_name: str,
        name: str,
        parent: str | None,
        line_start: int,
        line_end: int,
    ) -> None:
        """Add a node declared in a file, linked to its file or enclosing node."""
        file_id = self._canonical_id(file_path)
        node = BaseNode(
            id=f"{file_id}::{qualified_name}",
            path=file_path,
            name=name,
            type=node_type,
            line_start=line_start,
            line_end=line_end,
        )
        parent_id = f"{file_id}::{parent}" if parent else file_id
        self._add_child(node, parent_id, EntityRelationshipType.DECLARES)

    def _build_symbols(self, file_path: Path) -> None:
        """Add the classes, functions, methods and variables declared in a Python file."""
        for symbol in self._parse_file(
            file_path, lambda source: parse_python(source, self.symbol_depth)
        ):
            self._add_declaration(
                file_path,
                symbol.kind,
                symbol.qualified_name,
                symbol.qualified_name.rsplit(".", 1)[-1],
                symbol.parent,
                symbol.line_start,
                symbol.line_end,
            )

    def _build_sections(self, file_path: Path) -> None:
        """Add the sections of a Markdown file, one for each heading."""
        for section in self._parse_file(
            file_path,
            lambda source: parse_markdown(
                source.decode("utf-8-sig"), self.section_depth
            ),
        ):
            self._add_declaration(
                file_path,
                NodeType.SECTION,
                section.qualified_name,
                section.title,
                section.parent,
                section.line_start,
                section.line_end,
            )

    def _raise_unless_silenced(self, error: OSError) -> None:
        """Handle a directory that could not be listed during traversal."""
        if not self.silence_read_failure:
            raise error

    def _traversal(self) -> None:
        """
        Walk the directory in a stable order, skipping ignored directories.

        Raises:
            OSError: If a directory cannot be read and read failures are not silenced.
            SourceParseError: If a Python or Markdown file cannot be read or parsed
                and read failures are not silenced.
        """
        for current, directory_names, file_names in os.walk(
            self.root_path, onerror=self._raise_unless_silenced
        ):
            directory_names[:] = sorted(
                name for name in directory_names if name not in self.ignored_directories
            )
            current_path = Path(current)

            for name in directory_names:
                self._build_node(current_path / name, NodeType.DIRECTORY)
            for name in sorted(file_names):
                file_path = current_path / name
                self._build_node(file_path, NodeType.FILE)
                if file_path.suffix == ".py" and self.symbol_depth != 0:
                    self._build_symbols(file_path)
                elif (
                    file_path.suffix.lower() in MARKDOWN_SUFFIXES
                    and self.section_depth != 0
                ):
                    self._build_sections(file_path)

    def validate(self) -> GraphIntegrity:
        """
        Check referential integrity, connectivity and containment of the graph.

        Returns:
            GraphIntegrity: The validation report.
        """
        node_ids = {node.id for node in self.graph.nodes}

        # Collect edges that point at nodes that do not exist
        missing_edge_endpoints: list[str] = []
        for edge in self.graph.edges:
            if edge.source not in node_ids:
                missing_edge_endpoints.append(
                    f"{edge.id}: missing source {edge.source!r}"
                )

            if edge.target not in node_ids:
                missing_edge_endpoints.append(
                    f"{edge.id}: missing target {edge.target!r}"
                )

        if self.graph.root_id not in node_ids:
            missing_edge_endpoints.append(
                f"Graph root node is missing: {self.graph.root_id}"
            )

        # Treat edges as undirected to check connectivity
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in self.graph.edges:
            if edge.source in node_ids and edge.target in node_ids:
                adjacency[edge.source].add(edge.target)
                adjacency[edge.target].add(edge.source)

        isolated_node_ids = sorted(
            node_id
            for node_id in node_ids
            if node_id != self.graph.root_id and not adjacency[node_id]
        )

        # Walk outward from the root to find every node it can reach
        visited: set[str] = set()
        if self.graph.root_id in node_ids:
            queue = deque([self.graph.root_id])

            while queue:
                node_id = queue.popleft()

                if node_id in visited:
                    continue

                visited.add(node_id)
                queue.extend(adjacency[node_id] - visited)

        unreachable_from_root = sorted(node_ids - visited)

        # Every node except the root has exactly one parent, which is either
        # its directory (CONTAINS) or the file or class that declares it (DECLARES).
        incoming_parent_edges: dict[str, int] = {node_id: 0 for node_id in node_ids}
        for edge in self.graph.edges:
            if edge.type in PARENT_EDGE_TYPES and edge.target in incoming_parent_edges:
                incoming_parent_edges[edge.target] += 1

        invalid_containment_nodes = sorted(
            node_id
            for node_id, incoming_count in incoming_parent_edges.items()
            if node_id != self.graph.root_id and incoming_count != 1
        )

        is_weakly_connected = not missing_edge_endpoints and len(visited) == len(
            node_ids
        )

        is_valid = (
            is_weakly_connected
            and not isolated_node_ids
            and not invalid_containment_nodes
        )

        return GraphIntegrity(
            is_valid=is_valid,
            is_weakly_connected=is_weakly_connected,
            missing_edge_endpoints=missing_edge_endpoints,
            isolated_node_ids=isolated_node_ids,
            unreachable_from_root=unreachable_from_root,
            invalid_containment_nodes=invalid_containment_nodes,
        )

    def run(self) -> BaseGraph:
        """
        Traverse the directory and populate the graph.

        Returns:
            BaseGraph
        """
        self._traversal()
        return self.graph
