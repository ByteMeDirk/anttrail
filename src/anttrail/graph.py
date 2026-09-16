"""The main Base GraphGenerator"""
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from anttrail.files import SupportedReadFormats, SupportedWriteFormats
from anttrail.models import BaseGraph, BaseNode, NodeType, EntityRelationshipType, BaseEdge, GraphIntegrity


class GraphGenerator:
    def __init__(self, directory_path: Path, output_path: Path | None = None, schema_version: str = "<unset>",
                 **kwargs):
        """
        GraphGenerator is the substance object of anttrail.
        The objective is to build a concise graph from a provided directory.
        This graph can then be used for other purposes, i.e. an "anttrail" to traverse a directory.

        Args:
            directory_path (Path): The directory to traverse.
            output_path (Path | None): The path to save the graph to.
            schema_version (str, optional): The schema version to use. Defaults to "<unset>".
            kwargs (dict[str, Any], optional): Additional keyword arguments.
        """
        self.root_path: Path = directory_path
        self.output_path: Path | None = output_path
        self.artefacts: list[Path] = [
            path for path in self.root_path.rglob("*")
        ]
        self.schema_version: str = schema_version

        self.graph: BaseGraph = BaseGraph(
            schema_version=self.schema_version,
            created_at=datetime.now(),
            nodes=[BaseNode(
                id=".",
                path=self.root_path,
                name=self.root_path.name,
                type=NodeType.DIRECTORY,
            )],
            edges=[],
        )
        self.graph_integrity: GraphIntegrity | None = None

        self.kwargs: dict[str, Any] = kwargs

    def read_file(self, file_path: Path) -> list:
        """
        Read a file into a list.

        Args:
            file_path (Path): The file to read.

        Returns:
            list: A list of all lines in the file.
        """
        if SupportedReadFormats.supports(file_path):
            return file_path.read_text(encoding="utf-8").splitlines()
        else:
            if not self.kwargs.get("silence_read_failure"):
                raise ValueError("Unsupported file format during read: %s", file_path)
            return []

    def write_file(self, file_path: Path) -> None:
        """
        Write a file.

        Args:
            file_path (Path): The file to write.

        Returns:
            None
        """
        if SupportedWriteFormats.JSON.check(file_path):
            file_path.write_text(self.graph.model_dump_json(), encoding="utf-8")
        elif SupportedWriteFormats.YAML.check(file_path):
            file_path.write_text(
                yaml.safe_dump(
                    json.loads(self.graph.model_dump_json()),
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8"
            )
        else:
            if not self.kwargs.get("silence_write_failure"):
                raise ValueError(f"Unsupported file format during write: `{str(file_path)}`.")

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
            type=node_type
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
        for artefact in self.artefacts:
            self._build_nodes(artefact)
            self._build_edges(artefact)

    def validate(self) -> None:
        """
        Once the graph has been generated, one can validate it.

        Note: The algorithm here is a bit cognitively intense so will revise it later.

        Returns:
            None
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
            node_ids
            for node_id in node_ids
            if not adjacency[node_id]
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
        incoming_contains: dict[str, int] = {
            node_id: 0
            for node_id in node_ids
        }
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

        is_weakly_connected = (
                not missing_edge_endpoints
                and len(visited) == len(node_ids)
        )

        is_valid = (
                is_weakly_connected
                and not isolated_node_ids
                and not invalid_containment_nodes
        )

        self.graph_integrity = GraphIntegrity(
            is_valid=is_valid,
            # if True, this is not a bad thing for a containment tree, that's the type of graph we are generating
            is_weakly_connected=is_weakly_connected,
            missing_edge_endpoints=missing_edge_endpoints,
            isolated_node_ids=isolated_node_ids,
            unreachable_from_root=unreachable_from_root,
            invalid_containment_nodes=invalid_containment_nodes,
        )

    def run(self) -> BaseGraph:
        """
        Run the graph.
        If BaseGraph extends, this will need to be updated to extend the Graph Object.

        Returns:
            BaseGraph
        """
        self._traversal()
        return self.graph
