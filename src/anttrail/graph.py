"""The main Base GraphGenerator"""

import os
from collections import defaultdict, deque
from pathlib import Path

import yaml

from anttrail.files import SupportedWriteFormats, UnsupportedWriteFormatError
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
PARENT_EDGE_TYPES = frozenset(
    {EntityRelationshipType.CONTAINS, EntityRelationshipType.DECLARES}
)
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
        silence_read_failure: bool = False,
        silence_write_failure: bool = False,
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
            silence_read_failure: Skip, rather than raise on, unreadable directories
                and Python files that cannot be parsed.
            silence_write_failure: Skip, rather than raise on, unsupported output formats.
        """
        self.root_path: Path = directory_path
        self.ignored_directories: frozenset[str] = ignored_directories
        self.symbol_depth: int | None = symbol_depth
        self.silence_read_failure: bool = silence_read_failure
        self.silence_write_failure: bool = silence_write_failure

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
            file_path.write_text(self.graph.model_dump_json(), encoding="utf-8")
        elif SupportedWriteFormats.YAML.check(file_path):
            file_path.write_text(
                yaml.safe_dump(
                    self.graph.model_dump(mode="json"),
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

    def _build_symbols(self, file_path: Path) -> None:
        """
        Add the classes, functions, methods and variables declared in a Python file.

        Raises:
            SourceParseError: If the file cannot be parsed and read failures are
                not silenced.
        """
        try:
            symbols = parse_python(file_path.read_bytes(), self.symbol_depth)
        except (OSError, SyntaxError, ValueError) as error:
            if self.silence_read_failure:
                return
            raise SourceParseError(f"{file_path}: {error}") from error

        file_id = self._canonical_id(file_path)
        for symbol in symbols:
            parent_id = f"{file_id}::{symbol.parent}" if symbol.parent else file_id
            node = BaseNode(
                id=f"{file_id}::{symbol.qualified_name}",
                path=file_path,
                name=symbol.qualified_name.rsplit(".", 1)[-1],
                type=symbol.kind,
                line_start=symbol.line_start,
                line_end=symbol.line_end,
            )
            self._add_child(node, parent_id, EntityRelationshipType.DECLARES)

    def _raise_unless_silenced(self, error: OSError) -> None:
        """Handle a directory that could not be listed during traversal."""
        if not self.silence_read_failure:
            raise error

    def _traversal(self) -> None:
        """
        Walk the directory in a stable order, skipping ignored directories.

        Raises:
            OSError: If a directory cannot be read and read failures are not silenced.
            SourceParseError: If a Python file cannot be parsed and read failures
                are not silenced.
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

    def validate(self) -> GraphIntegrity:
        """
        Check referential integrity, connectivity and containment of the graph.

        Returns:
            GraphIntegrity: The validation report.
        """
        node_ids = {node.id for node in self.graph.nodes}

        # curate all missing edge endpoints
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

        # Check adjacent connections between source and target
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

        # traverse all node_ids to check their status
        visited: set[str] = set()
        if self.graph.root_id in node_ids:
            queue = deque([self.graph.root_id])

            while queue:
                node_id = queue.popleft()

                if node_id in visited:
                    continue

                visited.add(str(node_id))
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
