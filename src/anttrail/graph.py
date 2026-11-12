"""The main Base GraphGenerator"""

from collections import defaultdict, deque
from pathlib import Path

import yaml

from anttrail.files import SupportedWriteFormats, UnsupportedWriteFormatError
from anttrail.models import (
    BaseGraph,
    BaseNode,
    NodeType,
    EntityRelationshipType,
    BaseEdge,
    GraphIntegrity,
)

DEFAULT_SCHEMA_VERSION = "<unset>"


class GraphGenerator:
    def __init__(
        self,
        directory_path: Path,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
        silence_write_failure: bool = False,
    ):
        """
        GraphGenerator builds a concise containment graph from a directory.
        The graph can then be used as an "anttrail" to traverse that directory.

        Args:
            directory_path: The directory to traverse.
            schema_version: The schema version stamped onto the graph.
            silence_write_failure: Skip, rather than raise on, unsupported output formats.
        """
        self.root_path: Path = directory_path
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

    def _containment_edge(self, path: Path) -> str:
        """
        Return the edge id of a path.

        Args:
            path (Path): The relevant path to determine its edge id.

        Returns:
            str: The edge id.
        """
        return self._canonical_id(path.parent)

    def _build_nodes(self, artefact: Path) -> None:
        """
        Add nodes to the graph.

        Args:
            artefact: Path to the artefact.

        Returns:
            None
        """
        if artefact.is_dir():
            node_type = NodeType.DIRECTORY
        elif artefact.is_file():
            node_type = NodeType.FILE
        else:
            raise ValueError("Unsupported artefact type: %s", artefact)

        node = BaseNode(
            id=self._canonical_id(artefact),
            path=artefact,
            name=artefact.name,
            type=node_type,
        )
        self.graph.add_node(node)

    def _build_edges(self, artefact: Path) -> None:
        """
        Add edges to the graph.

        Returns:
            None
        """
        source = self._containment_edge(artefact)
        target = self._canonical_id(artefact)
        relationship_type = EntityRelationshipType.CONTAINS

        edge = BaseEdge(
            id=f"{source}|{relationship_type.value}|{target}",
            source=source,
            type=relationship_type,
            target=target,
        )

        self.graph.add_edge(edge)

    def _traversal(self) -> None:
        """
        Traverse the graph.
        Extendable to all build methods.

        Returns:
            None
        """
        for artefact in self.root_path.rglob("*"):
            self._build_nodes(artefact)
            self._build_edges(artefact)

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
            node_id for node_id in node_ids if not adjacency[node_id]
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

        # Check CONTAINS status, this will need to be extended eventually
        incoming_contains: dict[str, int] = {node_id: 0 for node_id in node_ids}
        for edge in self.graph.edges:
            if (
                edge.type == EntityRelationshipType.CONTAINS
                and edge.target in incoming_contains
            ):
                incoming_contains[edge.target] += 1

        invalid_containment_nodes = sorted(
            node_id
            for node_id, incoming_count in incoming_contains.items()
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
