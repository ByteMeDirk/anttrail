# Phase 2 implementation strategy: basic Python parsing

Status: implemented.

## Goal

When AntTrail crawls a directory, it also reads each `.py` file and adds nodes for the classes, methods, and variables it
declares. An agent can then find a symbol and the line range that holds it without reading the whole file.

## Scope

In scope:

- Classes, including nested classes.
- Methods: functions defined directly in a class body, including `async` methods and decorated methods.
- Variables: names assigned at module level or directly in a class body.
- Module-level functions.
- The `DECLARES` relationship, which already exists in `EntityRelationshipType` but is unused.

Out of scope:

- Imports, calls, inheritance, decorators, docstrings, and type resolution.
- Functions nested inside functions, and variables inside function bodies.
- Instance attributes such as `self.x = 1`.
- Other languages, and any parser plugin system.

## Design

### Parsing with the standard library

Use `ast.parse` on the file's bytes, so Python's own encoding detection applies. This adds no dependency and keeps
parsing deterministic. Walk only the top-level statements of the module and of each class body. Do not descend into
`if`, `try`, or function bodies. This keeps the rule easy to state: AntTrail reports what a reader sees at the top level
of a module or class.

The parser lives in a new `src/anttrail/python_parser.py` and exposes one pure function:

```python
def parse_python(source: bytes, max_depth: int | None = None) -> list[Symbol]: ...
```

`Symbol` is a small frozen dataclass with `qualified_name`, `kind`, `line_start`, `line_end`, and `parent` (the
qualified name of the enclosing class, or `None`). The function does no I/O and knows nothing about graphs, so you can
test it with plain strings.

### Model changes

- `NodeType` gains `CLASS`, `METHOD`, `VARIABLE`, and `FUNCTION`.
- `BaseNode` gains optional `line_start` and `line_end` fields. They are `None` for directories and files.
- No new edge type. Symbols use `DECLARES`.

Edges:

| Source | Edge       | Target                                   |
|--------|------------|------------------------------------------|
| File   | `DECLARES` | Class, function, or variable at top level |
| Class  | `DECLARES` | Method, variable, or nested class         |

`CONTAINS` keeps its meaning: filesystem containment only.

### Node IDs

A symbol ID is the file's ID, then `::`, then the dotted qualified name:

```text
src/anttrail/graph.py::GraphGenerator
src/anttrail/graph.py::GraphGenerator.validate
src/anttrail/graph.py::DEFAULT_SCHEMA_VERSION
```

IDs stay root-relative and POSIX-style, so they remain stable across operating systems. The `::` separator cannot
appear in a normal file path component, so a symbol ID never collides with a file ID.

Python allows the same name to be bound more than once in one scope (property setters, `typing.overload`, a variable
assigned in two branches). IDs must be unique, so the parser keeps the first binding of each qualified name and drops
the rest. The `line_end` of a kept symbol is not extended to cover the dropped ones.

### What counts as a variable

- `x = ...` and `x: int = ...` where the target is a plain name.
- Tuple targets, such as `a, b = ...`, produce one variable per name.
- Annotation-only statements (`x: int`) count.
- Augmented assignments (`x += 1`), attribute targets (`obj.x = ...`), and subscripts do not.

### Limiting symbol depth

`--symbol-depth N` limits how many levels of symbols AntTrail adds below each file. It takes an integer of 0 or more.
Without the option, there is no limit.

| Depth | Adds                                                                |
|-------|---------------------------------------------------------------------|
| 0     | Nothing. Python files are not opened, so no parse errors can occur. |
| 1     | Classes, functions, and variables at the top level of a file.       |
| 2     | Level 1, plus methods, variables, and nested classes in a class.    |
| 3     | Level 2, plus the members of nested classes, and so on.             |

A symbol's depth is the number of dots in its qualified name, plus 1. The parser takes an optional `max_depth` argument
and stops descending when it reaches it, so a depth limit never produces a node whose parent is missing and never
changes the ID of a symbol that remains. The CLI rejects negative values with the usual usage error.

### Graph generator changes

`GraphGenerator._traversal` calls the parser for each file whose suffix is `.py` (unless the depth is 0), then adds one node and one
`DECLARES` edge per symbol. A small helper replaces the duplicated node-and-edge code that `_build_node` currently
holds, so filesystem nodes and symbol nodes share one path.

Parse failures (`SyntaxError`, `UnicodeDecodeError`, and `OSError` while reading) follow the existing rule for read
failures. The file node always stays in the graph. Without `--silence-read-failure`, AntTrail stops with a one-line
`anttrail: error: path: reason` message. With the flag, it skips that file's symbols. The flag's help text changes from
"directories" to "directories and files".

### Validation changes

`validate()` currently requires every non-root node to have exactly one incoming `CONTAINS` edge. Symbol nodes have
none, so every Python graph would report as invalid. The fix requires exactly one incoming `CONTAINS` or
`DECLARES` edge for every non-root node. It does not check that a file has a `CONTAINS` parent and a symbol a `DECLARES`
parent, which keeps the rule short. This is the one change to existing
behavior, and it needs its own test before the parser is wired in.

## Implementation steps

Each step is one commit, and the test suite passes after each one.

1. `refactor(graph): share node and edge creation between traversal and symbols`. Pure refactor, no behavior change.
2. `feat(models): add symbol node types and line ranges`. Model tests for the new enum members and fields.
3. `fix(validate): accept DECLARES as a parent edge`. Tests build a hand-made graph with a `DECLARES` edge.
4. `feat(parser): extract classes, methods, functions and variables from Python source`. Unit tests on source strings.
   Cases: nested classes, async and decorated methods, tuple targets, duplicate bindings, an empty file, a syntax error,
   and each `max_depth` value from 0 to 3.
5. `feat(graph): add symbol nodes for Python files`. Tests use a new `tests/python_assets/` fixture so the existing
   `tests/assets` counts do not change. Includes the failure cases with and without `--silence-read-failure`.
6. `feat(cli): add --symbol-depth`. Tests cover the default, 0, 1, a negative value, and a non-integer value.
7. `docs: document symbol nodes`. Update `docs/graph-format.md`, the README capability list and command reference, and
   the changelog entry for 0.1.0.

## Acceptance criteria

- `anttrail tests/python_assets --validate` reports `is_valid: true`.
- Running `anttrail src` on this repository lists `GraphGenerator`, `GraphGenerator.validate`, and
  `DEFAULT_SCHEMA_VERSION` with correct line ranges.
- A file with a syntax error produces a one-line error by default and a partial graph with the silence flag.
- `--symbol-depth 0` produces the same graph as Phase 1, and depths 1 and 2 produce the node sets in the table above.
- Output is identical across two runs, apart from `created_at`.

## Risks

- **Graph size.** Symbols multiply the node count. A large repository could produce a graph too big for an agent to
  read whole. `--symbol-depth` lets you cap it. Filtering and querying stay out of scope.
- **Interpreter grammar.** `ast.parse` uses the grammar of the Python running AntTrail. On 3.11, a file that uses
  newer syntax (for example, PEP 695 generics) raises `SyntaxError`, and AntTrail reports it as a parse failure. I
  recommend documenting this rather than working around it.
- **Schema drift.** Adding node types and fields changes the output for existing consumers. `schema_version` is a
  free-form string you set, so the changelog is the only signal. Nothing has been released yet, so no consumer sees the change. Symbol support is part of the 0.1.0 changelog entry.

## Decisions

1. Module-level functions get a `FUNCTION` node type.
2. Instance attributes are out of scope for Phase 2.
3. Symbol extraction is always on, and `--symbol-depth` limits it. There is no separate on/off flag, because depth 0
   turns it off.
4. Symbol support ships in 0.1.0. The version stays at 0.1.0 and the changelog keeps one section. You tag and publish
   after Phase 2 is merged and the CI/CD pipelines are in place.
