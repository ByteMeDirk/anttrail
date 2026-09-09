"""All models for the graph generation functionality."""

from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class NodeType(Enum):
    """Node Labels"""
    DIRECTORY = "Directory"
    FILE = "File"


class EntityRelationshipType(Enum):
    """Relationship Labels"""
    CONTAINS = "CONTAINS"
    DECLARES = "DECLARES"
    REFERENCES = "REFERENCES"
    LINKS_TO = "LINKS_TO"


class EntityRelationshipSyntax(Enum):
    """Relationship Syntax"""
    UNDIRECTED = "--"
    INBOUND = "<-"
    OUTBOUND = "->"


class BaseNode(BaseModel):
    """
    Base Node Model

    Attributes:
        id: Node ID
        path: Node Path
        name: Node name
        type: Node type
    """
    id: str
    path: Path
    name: str
    type: NodeType


class BaseEdge(BaseModel):
    """
    Base Edge Model

    Attributes:
        id: Edge id
        type: Edge type
        source: Source Node ID
        target: Target Node ID
    """
    id: str
    source: str
    type: EntityRelationshipType
    target: str


class BaseGraph(BaseModel):
    """
    Base Graph Model

    Attributes:
        schema_version: The schema version defined by you.
        created_at: UTC datetime of when the graph was created.
        root_id: Graphs canonical root ID.
        nodes: List of Node objects.
        edges: List of Edge objects.
    """
    schema_version: str = Field(title="Schema Version")
    created_at: datetime = Field(title="Schema Creation UTC Timestamp", default_factory=lambda: datetime.now(UTC))
    root_id: str = Field(title="Schema Root Node ID", default=".")
    nodes: list[BaseNode] = Field(title="Schema Node List", default_factory=list)
    edges: list[BaseEdge] = Field(title="Schema Edge List", default_factory=list)

    def add_node(self, node: BaseNode) -> None:
        """Add a node to the graph"""
        self.nodes.append(node)

    def pop_node(self, node: BaseNode) -> None:
        """Remove a node from the graph"""
        self.nodes.remove(node)

    def add_edge(self, edge: BaseEdge) -> None:
        """Add an edge to the graph"""
        self.edges.append(edge)

    def pop_edge(self, edge: BaseEdge) -> None:
        """Remove an edge from the graph"""
        self.edges.remove(edge)

    def graph_syntax(self) -> tuple:
        """
        Generate Graph syntax.
        The Graph model may be reduced to generic graph syntax, as text.

        Returns:
            tuple(str, str): Node Graph, Edge Graph
        """
        def escape(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', '\\"')

        def fmt_properties(prop: dict[str, Any]) -> str:
            return ", ".join(
                f'{key}: "{escape(str(value))}"' for key, value in prop.items()
            )

        nodes_by_id = {
            node.id: node for node in self.nodes
        }

        node_lines = []
        for node in sorted(self.nodes, key=lambda item: item.id):
            properties = {
                "id": node.id,
                "path": node.path,
                "name": node.name,
            }
            node_lines.append(
                f'(:{node.type.value} {{{fmt_properties(properties)}}})'
            )

        edge_lines = []
        for edge in sorted(self.edges, key=lambda item: (item.source, item.type.value, item.target)):
            source_node = nodes_by_id[edge.source]
            target_node = nodes_by_id[edge.target]

            source = (
                f'(:{source_node.type.value} {{id: "{escape(source_node.id)}"}})'
            )
            target = (
                f'(:{target_node.type.value} {{id: "{escape(target_node.id)}"}})'
            )
            edge_lines.append(
                f"{source}-[:{edge.type.value}]->{target}"
            )

        return "\n".join([*node_lines]), "\n".join([*edge_lines])

class GraphIntegrity(BaseModel):
    """
    Graph Integrity Model

    Checks the following:
        1. Referential integrity.
        2. Graph connectivity.
        3. Structural containment validity.
    """
    is_valid: bool = Field(title="Validity of Graph integrity")
    is_weakly_connected: bool = Field(title="Connection strength of Graph integrity")
    missing_edge_endpoints:list[str] = Field(title="Missing endpoints", default_factory=list)
    isolated_node_ids: list[set[str]] = Field(title="Isolated nodes", default_factory=list)
    unreachable_from_root: list[str] = Field(title="Unreachable from root", default_factory=list)
    invalid_containment_nodes: list[str] = Field(title="Invalid containment nodes", default_factory=list)
