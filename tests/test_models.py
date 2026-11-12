"""Tests for models."""

from datetime import timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from anttrail.models import (
    BaseEdge,
    BaseGraph,
    BaseNode,
    EntityRelationshipType,
    GraphIntegrity,
    NodeType,
)


@pytest.fixture
def root_node() -> BaseNode:
    return BaseNode(id=".", path=Path("."), name="project", type=NodeType.DIRECTORY)


def test_node_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        BaseNode(id=".", path=Path("."), name="project", type="Socket")


def test_edge_rejects_unknown_relationship() -> None:
    with pytest.raises(ValidationError):
        BaseEdge(id="e", source="a", type="OWNS", target="b")


def test_graph_requires_schema_version() -> None:
    with pytest.raises(ValidationError):
        BaseGraph()


def test_graph_defaults(root_node: BaseNode) -> None:
    graph = BaseGraph(schema_version="1.0")

    assert graph.root_id == "."
    assert graph.nodes == []
    assert graph.edges == []
    assert graph.created_at.tzinfo is timezone.utc


def test_add_and_pop_node(root_node: BaseNode) -> None:
    graph = BaseGraph(schema_version="1.0")

    graph.add_node(root_node)
    assert graph.nodes == [root_node]

    graph.pop_node(root_node)
    assert graph.nodes == []


def test_add_and_pop_edge() -> None:
    graph = BaseGraph(schema_version="1.0")
    edge = BaseEdge(
        id="a|CONTAINS|b",
        source="a",
        type=EntityRelationshipType.CONTAINS,
        target="b",
    )

    graph.add_edge(edge)
    assert graph.edges == [edge]

    graph.pop_edge(edge)
    assert graph.edges == []


def test_graph_round_trips_through_json(root_node: BaseNode) -> None:
    graph = BaseGraph(schema_version="1.0", nodes=[root_node])

    restored = BaseGraph.model_validate_json(graph.model_dump_json())

    assert restored == graph


def test_integrity_isolated_node_ids_are_strings() -> None:
    integrity = GraphIntegrity(
        is_valid=False, is_weakly_connected=False, isolated_node_ids=["orphan"]
    )

    assert integrity.isolated_node_ids == ["orphan"]
