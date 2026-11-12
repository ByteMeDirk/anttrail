"""Tests for the Python source parser."""

import pytest

from anttrail.models import NodeType
from anttrail.python_parser import parse_python

SOURCE = b"""\
LIMIT = 3
RATE: float = 0.5
LOW, HIGH = 1, 2
unset: int


def helper():
    inner = 1
    return inner


class Outer:
    kind = "outer"

    def method(self):
        self.x = 1

    async def fetch(self):
        pass

    class Inner:
        def deep(self):
            pass


if True:
    hidden = 1
"""


def qualified(source: bytes, max_depth: int | None = None) -> dict[str, NodeType]:
    return {s.qualified_name: s.kind for s in parse_python(source, max_depth)}


def test_extracts_every_kind_of_symbol() -> None:
    assert qualified(SOURCE) == {
        "LIMIT": NodeType.VARIABLE,
        "RATE": NodeType.VARIABLE,
        "LOW": NodeType.VARIABLE,
        "HIGH": NodeType.VARIABLE,
        "unset": NodeType.VARIABLE,
        "helper": NodeType.FUNCTION,
        "Outer": NodeType.CLASS,
        "Outer.kind": NodeType.VARIABLE,
        "Outer.method": NodeType.METHOD,
        "Outer.fetch": NodeType.METHOD,
        "Outer.Inner": NodeType.CLASS,
        "Outer.Inner.deep": NodeType.METHOD,
    }


def test_records_line_range_and_parent() -> None:
    symbols = {s.qualified_name: s for s in parse_python(SOURCE)}

    outer = symbols["Outer"]
    assert (outer.line_start, outer.line_end, outer.parent) == (12, 23, None)
    assert symbols["Outer.method"].parent == "Outer"
    assert symbols["Outer.method"].line_start == 15


def test_ignores_function_bodies_and_conditional_blocks() -> None:
    names = qualified(SOURCE)

    assert "inner" not in names
    assert "hidden" not in names
    assert "Outer.method.x" not in names


def test_decorated_method_starts_at_the_def_line() -> None:
    source = b"class A:\n    @property\n    def x(self):\n        pass\n"

    _, method = parse_python(source)

    assert method.qualified_name == "A.x"
    assert method.line_start == 3


def test_keeps_first_binding_of_a_repeated_name() -> None:
    source = (
        b"class A:\n"
        b"    @property\n    def x(self): ...\n"
        b"    @x.setter\n    def x(self, value): ...\n"
    )

    symbols = parse_python(source)

    assert [s.qualified_name for s in symbols] == ["A", "A.x"]
    assert symbols[1].line_start == 3


def test_ignores_augmented_attribute_and_subscript_targets() -> None:
    source = b"x = 1\nx += 1\nobj.y = 2\nitems[0] = 3\n"

    assert list(qualified(source)) == ["x"]


@pytest.mark.parametrize(
    ("max_depth", "expected"),
    [
        (0, set()),
        (1, {"LIMIT", "RATE", "LOW", "HIGH", "unset", "helper", "Outer"}),
        (
            2,
            {
                "LIMIT",
                "RATE",
                "LOW",
                "HIGH",
                "unset",
                "helper",
                "Outer",
                "Outer.kind",
                "Outer.method",
                "Outer.fetch",
                "Outer.Inner",
            },
        ),
    ],
)
def test_max_depth_limits_symbols(max_depth: int, expected: set[str]) -> None:
    assert set(qualified(SOURCE, max_depth)) == expected


def test_max_depth_beyond_nesting_returns_everything() -> None:
    assert qualified(SOURCE, 10) == qualified(SOURCE)


def test_empty_source_has_no_symbols() -> None:
    assert parse_python(b"") == []


def test_invalid_source_raises_syntax_error() -> None:
    with pytest.raises(SyntaxError):
        parse_python(b"def broken(:\n")
