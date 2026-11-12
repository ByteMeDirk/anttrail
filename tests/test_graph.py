"""Tests for the graph generator."""

import json
import os
from pathlib import Path

import pytest
import yaml

from anttrail.files import UnsupportedWriteFormatError
from anttrail.graph import GraphGenerator
from anttrail.models import BaseNode, EntityRelationshipType, NodeType

ASSETS = Path(__file__).parent / "assets"

ASSET_NODE_IDS = {
    ".",
    "README.md",
    "dir_1",
    "dir_1/Doc_1_1.md",
    "dir_1/dir_1_1",
    "dir_1/dir_1_1/Doc_1_1_1.md",
    "dir_2",
    "dir_2/Doc_2_1.md",
}


@pytest.fixture
def generator() -> GraphGenerator:
    generator = GraphGenerator(ASSETS)
    generator.run()
    return generator


def node_ids(generator: GraphGenerator) -> set[str]:
    return {node.id for node in generator.graph.nodes}


def test_run_builds_a_node_for_every_artefact(generator: GraphGenerator) -> None:
    assert node_ids(generator) == ASSET_NODE_IDS


def test_run_builds_one_contains_edge_per_artefact(generator: GraphGenerator) -> None:
    edges = {(edge.source, edge.target) for edge in generator.graph.edges}

    assert edges == {
        (".", "README.md"),
        (".", "dir_1"),
        (".", "dir_2"),
        ("dir_1", "dir_1/Doc_1_1.md"),
        ("dir_1", "dir_1/dir_1_1"),
        ("dir_1/dir_1_1", "dir_1/dir_1_1/Doc_1_1_1.md"),
        ("dir_2", "dir_2/Doc_2_1.md"),
    }


def test_run_assigns_node_types(generator: GraphGenerator) -> None:
    types = {node.id: node.type for node in generator.graph.nodes}

    assert types["dir_1"] is NodeType.DIRECTORY
    assert types["dir_1/Doc_1_1.md"] is NodeType.FILE


def test_run_skips_default_ignored_directories(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").touch()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "src").mkdir()

    generator = GraphGenerator(tmp_path)
    generator.run()

    assert node_ids(generator) == {".", "src"}


def test_run_includes_ignored_directories_when_overridden(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    generator = GraphGenerator(tmp_path, ignored_directories=frozenset())
    generator.run()

    assert node_ids(generator) == {".", ".git"}


def test_run_handles_empty_directory(tmp_path: Path) -> None:
    generator = GraphGenerator(tmp_path)
    generator.run()

    assert node_ids(generator) == {"."}
    assert generator.validate().is_valid


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="permission bits are not enforced",
)
class TestUnreadableDirectory:
    @pytest.fixture
    def locked_tree(self, tmp_path: Path):
        (tmp_path / "open").mkdir()
        locked = tmp_path / "locked"
        locked.mkdir()
        (locked / "secret.txt").touch()
        locked.chmod(0o000)
        yield tmp_path
        locked.chmod(0o700)

    def test_raises_by_default(self, locked_tree: Path) -> None:
        with pytest.raises(PermissionError):
            GraphGenerator(locked_tree).run()

    def test_skips_when_silenced(self, locked_tree: Path) -> None:
        generator = GraphGenerator(locked_tree, silence_read_failure=True)
        generator.run()

        assert node_ids(generator) == {".", "open", "locked"}


def test_validate_accepts_generated_graph(generator: GraphGenerator) -> None:
    integrity = generator.validate()

    assert integrity.is_valid
    assert integrity.isolated_node_ids == []
    assert integrity.unreachable_from_root == []
    assert integrity.invalid_containment_nodes == []


def test_validate_reports_isolated_node_by_id(tmp_path: Path) -> None:
    generator = GraphGenerator(tmp_path)
    generator.graph.add_node(
        BaseNode(
            id="orphan", path=tmp_path / "orphan", name="orphan", type=NodeType.FILE
        )
    )

    integrity = generator.validate()

    assert not integrity.is_valid
    assert integrity.isolated_node_ids == ["orphan"]
    assert integrity.unreachable_from_root == ["orphan"]
    assert integrity.invalid_containment_nodes == ["orphan"]


def test_validate_reports_missing_edge_endpoint(generator: GraphGenerator) -> None:
    generator.graph.nodes = [n for n in generator.graph.nodes if n.id != "dir_2"]

    integrity = generator.validate()

    assert not integrity.is_valid
    assert any(
        "missing target 'dir_2'" in item for item in integrity.missing_edge_endpoints
    )


def test_write_file_writes_json(generator: GraphGenerator, tmp_path: Path) -> None:
    output = tmp_path / "graph.json"

    generator.write_file(output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert {node["id"] for node in data["nodes"]} == ASSET_NODE_IDS


def test_write_file_writes_yaml(generator: GraphGenerator, tmp_path: Path) -> None:
    output = tmp_path / "graph.yaml"

    generator.write_file(output)

    data = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert {node["id"] for node in data["nodes"]} == ASSET_NODE_IDS


def test_write_file_rejects_unsupported_format(
    generator: GraphGenerator, tmp_path: Path
) -> None:
    with pytest.raises(UnsupportedWriteFormatError):
        generator.write_file(tmp_path / "graph.txt")


def test_write_file_ignores_unsupported_format_when_silenced(tmp_path: Path) -> None:
    generator = GraphGenerator(ASSETS, silence_write_failure=True)
    generator.run()
    output = tmp_path / "graph.txt"

    generator.write_file(output)

    assert not output.exists()


def test_validate_accepts_symbol_declared_by_file(tmp_path: Path) -> None:
    generator = GraphGenerator(tmp_path)
    generator._add_child(
        BaseNode(id="a.py", path=tmp_path / "a.py", name="a.py", type=NodeType.FILE),
        ".",
        EntityRelationshipType.CONTAINS,
    )
    generator._add_child(
        BaseNode(
            id="a.py::A",
            path=tmp_path / "a.py",
            name="A",
            type=NodeType.CLASS,
            line_start=1,
            line_end=2,
        ),
        "a.py",
        EntityRelationshipType.DECLARES,
    )

    assert generator.validate().is_valid


def test_validate_rejects_symbol_without_declaring_edge(tmp_path: Path) -> None:
    generator = GraphGenerator(tmp_path)
    generator._add_child(
        BaseNode(id="a.py", path=tmp_path / "a.py", name="a.py", type=NodeType.FILE),
        ".",
        EntityRelationshipType.CONTAINS,
    )
    generator.graph.add_node(
        BaseNode(id="a.py::A", path=tmp_path / "a.py", name="A", type=NodeType.CLASS)
    )

    integrity = generator.validate()

    assert not integrity.is_valid
    assert integrity.invalid_containment_nodes == ["a.py::A"]
