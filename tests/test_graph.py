"""Tests for the graph generator."""

import json
import os
from pathlib import Path

import pytest
import yaml

from anttrail.files import UnsupportedWriteFormatError
from anttrail.graph import GraphGenerator
from anttrail.models import BaseNode, EntityRelationshipType, NodeType
from anttrail.python_parser import SourceParseError

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


PYTHON_ASSETS = Path(__file__).parent / "python_assets"


def test_python_files_get_symbol_nodes() -> None:
    generator = GraphGenerator(PYTHON_ASSETS)
    generator.run()

    nodes = {node.id: node for node in generator.graph.nodes}
    assert nodes["shapes.py::Shape"].type is NodeType.CLASS
    assert nodes["shapes.py::Shape.area"].type is NodeType.METHOD
    assert nodes["shapes.py::Shape.area"].name == "area"
    assert nodes["shapes.py::describe"].type is NodeType.FUNCTION
    assert nodes["pkg/util.py::DEFAULT"].type is NodeType.VARIABLE
    assert nodes["shapes.py::Shape"].line_start == 4
    assert nodes["shapes.py::Shape"].line_end == 12
    assert not any("notes.txt::" in node_id for node_id in nodes)


def test_symbols_are_declared_by_their_parent() -> None:
    generator = GraphGenerator(PYTHON_ASSETS)
    generator.run()

    declares = {
        (edge.source, edge.target)
        for edge in generator.graph.edges
        if edge.type is EntityRelationshipType.DECLARES
    }
    assert ("shapes.py", "shapes.py::Shape") in declares
    assert ("shapes.py::Shape", "shapes.py::Shape.Style") in declares
    assert ("shapes.py::Shape.Style", "shapes.py::Shape.Style.color") in declares
    assert ("pkg/util.py", "pkg/util.py::clamp") in declares


def test_graph_with_symbols_is_valid() -> None:
    generator = GraphGenerator(PYTHON_ASSETS)
    generator.run()

    assert generator.validate().is_valid


def symbol_ids(symbol_depth: int | None) -> set[str]:
    generator = GraphGenerator(PYTHON_ASSETS, symbol_depth=symbol_depth)
    generator.run()
    return {node.id for node in generator.graph.nodes if "::" in node.id}


def test_symbol_depth_zero_adds_no_symbols() -> None:
    assert symbol_ids(0) == set()


def test_symbol_depth_one_adds_top_level_symbols_only() -> None:
    assert symbol_ids(1) == {
        "shapes.py::SIDES",
        "shapes.py::Shape",
        "shapes.py::describe",
        "pkg/util.py::DEFAULT",
        "pkg/util.py::clamp",
    }


def test_symbol_depth_two_adds_class_members() -> None:
    ids = symbol_ids(2)

    assert "shapes.py::Shape.area" in ids
    assert "shapes.py::Shape.Style" in ids
    assert "shapes.py::Shape.Style.color" not in ids


def test_symbol_depth_limit_keeps_graph_valid() -> None:
    generator = GraphGenerator(PYTHON_ASSETS, symbol_depth=2)
    generator.run()

    assert generator.validate().is_valid


@pytest.fixture
def broken_python_tree(tmp_path: Path) -> Path:
    (tmp_path / "ok.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    return tmp_path


def test_unparseable_python_file_raises_by_default(broken_python_tree: Path) -> None:
    with pytest.raises(SourceParseError, match="broken.py"):
        GraphGenerator(broken_python_tree).run()


def test_unparseable_python_file_is_skipped_when_silenced(
    broken_python_tree: Path,
) -> None:
    generator = GraphGenerator(broken_python_tree, silence_read_failure=True)
    generator.run()

    assert node_ids(generator) == {".", "broken.py", "ok.py", "ok.py::X"}


def test_symbol_depth_zero_ignores_unparseable_files(broken_python_tree: Path) -> None:
    generator = GraphGenerator(broken_python_tree, symbol_depth=0)
    generator.run()

    assert node_ids(generator) == {".", "broken.py", "ok.py"}
