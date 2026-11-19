"""Small, bounded answers to questions about a crawled graph.

Every function returns lines of text in the form
`path:line_start-line_end<TAB>Type<TAB>id`, or `path<TAB>Type<TAB>id` for a node that
has no line range. The size of an answer depends on the number of matches, not on the
size of the repository.
"""

from pathlib import Path

from anttrail.graph import PARENT_EDGE_TYPES
from anttrail.models import BaseGraph, BaseNode, NodeType

DEFAULT_FIND_LIMIT = 50
INDENT = "  "


class QueryError(ValueError):
    """Raised when a query names a file, line, or node that the graph does not hold."""


class GraphQuery:
    """Answers questions about one graph, whose nodes were crawled below `root`."""

    def __init__(self, graph: BaseGraph, root: Path) -> None:
        self._graph = graph
        self._root = root
        self._nodes = {node.id: node for node in graph.nodes}
        self._parent_ids = {
            edge.target: edge.source
            for edge in graph.edges
            if edge.type in PARENT_EDGE_TYPES
        }

    def outline(self, file_id: str) -> list[str]:
        """List the sections or symbols of a file, indented by depth.

        Raises:
            QueryError: If `file_id` is not a file in the graph.
        """
        self._require_file(file_id)
        file_depth = len(self._ancestors(file_id))
        return [
            INDENT * (len(self._ancestors(node.id)) - file_depth - 1)
            + self._format(node)
            for node in self._declared_in(file_id)
        ]

    def find(
        self,
        text: str,
        node_type: NodeType | None = None,
        limit: int = DEFAULT_FIND_LIMIT,
    ) -> list[str]:
        """List the nodes whose name contains `text`, ignoring case.

        Args:
            text: The text to look for in node names.
            node_type: Keep only nodes of this type.
            limit: The most matches to list. The last line says if more matched.
        """
        wanted = text.casefold()
        matches = [
            node
            for node in self._graph.nodes
            if wanted in node.name.casefold()
            and (node_type is None or node.type is node_type)
        ]
        lines = [self._format(node) for node in matches[:limit]]
        if len(matches) > limit:
            lines.append(f"(showing {limit} of {len(matches)} matches, see --limit)")
        return lines

    def at(self, location: str) -> list[str]:
        """List the node that contains a line, then its ancestors within the file.

        Args:
            location: A file ID and a 1-based line number, as `PATH:LINE`.

        Raises:
            QueryError: If the location is malformed or names a file not in the graph.
        """
        file_id, separator, line_text = location.rpartition(":")
        if not separator or not line_text.isdecimal() or int(line_text) < 1:
            raise QueryError(f"{location!r} is not in the form PATH:LINE.")
        line = int(line_text)

        self._require_file(file_id)
        containing = [
            node
            for node in self._declared_in(file_id)
            if node.line_start is not None
            and node.line_end is not None
            and node.line_start <= line <= node.line_end
        ]
        if not containing:
            return [self._format(self._nodes[file_id])]

        innermost = max(containing, key=lambda node: len(self._ancestors(node.id)))
        chain = [innermost, *(self._nodes[i] for i in self._ancestors(innermost.id))]
        return [
            self._format(node)
            for node in chain
            if node.id == file_id or node.id.startswith(f"{file_id}::")
        ]

    def show(self, node_id: str) -> list[str]:
        """Return the file lines of a section or symbol.

        Only a node in the graph can be read, and only from a file inside the crawled
        root.

        Raises:
            QueryError: If the node is not in the graph, has no line range, lies
                outside the root, or its file has changed since the crawl.
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise QueryError(f"No node {node_id!r} in the graph.")
        if node.line_start is None or node.line_end is None:
            raise QueryError(f"{node_id!r} has no line range to show.")
        if not node.path.resolve().is_relative_to(self._root):
            raise QueryError(f"{node_id!r} is outside {self._root}.")

        lines = node.path.read_text(encoding="utf-8-sig").splitlines()
        if node.line_end > len(lines):
            raise QueryError(f"{node.path} changed since the crawl. Crawl it again.")
        return lines[node.line_start - 1 : node.line_end]

    def _require_file(self, file_id: str) -> None:
        node = self._nodes.get(file_id)
        if node is None or node.type is not NodeType.FILE:
            raise QueryError(f"No file {file_id!r} in the graph.")

    def _declared_in(self, file_id: str) -> list[BaseNode]:
        prefix = f"{file_id}::"
        return [node for node in self._graph.nodes if node.id.startswith(prefix)]

    def _ancestors(self, node_id: str) -> list[str]:
        """Return the IDs above a node, nearest first."""
        ancestors: list[str] = []
        while (parent_id := self._parent_ids.get(node_id)) is not None:
            ancestors.append(parent_id)
            node_id = parent_id
        return ancestors

    def _format(self, node: BaseNode) -> str:
        location = node.path.relative_to(self._root).as_posix()
        if node.line_start is not None:
            location += f":{node.line_start}-{node.line_end}"
        return f"{location}\t{node.type.value}\t{node.id}"
