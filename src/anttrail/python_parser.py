"""Extract classes, functions, methods and variables from Python source."""

import ast
from dataclasses import dataclass

from anttrail.models import NodeType


class SourceParseError(Exception):
    """Raised when a Python file cannot be read or parsed."""


@dataclass(frozen=True, slots=True)
class Symbol:
    """A class, function, method or variable declared in a Python file."""

    qualified_name: str
    kind: NodeType
    line_start: int
    line_end: int
    parent: str | None


def parse_python(source: bytes, max_depth: int | None = None) -> list[Symbol]:
    """
    List the symbols declared at the top level of a module and of its classes.

    Only module and class bodies are read. Function bodies and conditional
    blocks are not entered. When a qualified name is bound more than once, the
    first binding is kept.

    Args:
        source: The file contents. Python detects the encoding.
        max_depth: Levels of symbols to return. A top-level symbol has depth 1,
            a member of a top-level class has depth 2. None means no limit.

    Raises:
        SyntaxError: If the source is not valid Python.
        ValueError: If the source contains null bytes.
    """
    symbols: dict[str, Symbol] = {}
    _collect(ast.parse(source).body, None, 1, max_depth, symbols)
    return list(symbols.values())


def _collect(
    body: list[ast.stmt],
    parent: str | None,
    depth: int,
    max_depth: int | None,
    symbols: dict[str, Symbol],
) -> None:
    if max_depth is not None and depth > max_depth:
        return

    in_class = parent is not None
    for statement in body:
        if isinstance(statement, ast.ClassDef):
            symbol = _symbol(statement.name, NodeType.CLASS, statement, parent)
            if symbols.setdefault(symbol.qualified_name, symbol) is symbol:
                _collect(
                    statement.body, symbol.qualified_name, depth + 1, max_depth, symbols
                )
        elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            kind = NodeType.METHOD if in_class else NodeType.FUNCTION
            symbol = _symbol(statement.name, kind, statement, parent)
            symbols.setdefault(symbol.qualified_name, symbol)
        else:
            for name in _assigned_names(statement):
                symbol = _symbol(name, NodeType.VARIABLE, statement, parent)
                symbols.setdefault(symbol.qualified_name, symbol)


def _symbol(
    name: str, kind: NodeType, statement: ast.stmt, parent: str | None
) -> Symbol:
    return Symbol(
        qualified_name=f"{parent}.{name}" if parent else name,
        kind=kind,
        line_start=statement.lineno,
        line_end=statement.end_lineno or statement.lineno,
        parent=parent,
    )


def _assigned_names(statement: ast.stmt) -> list[str]:
    """Return the plain names bound by an assignment statement."""
    if isinstance(statement, ast.Assign):
        targets = statement.targets
    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]
    else:
        return []

    names: list[str] = []
    for target in targets:
        _add_names(target, names)
    return names


def _add_names(target: ast.expr, names: list[str]) -> None:
    if isinstance(target, ast.Name):
        names.append(target.id)
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            _add_names(element, names)
