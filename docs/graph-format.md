# Graph format

AntTrail writes one graph per run. This page describes the fields and shows the output for a small directory.

## Fields

| Field            | Description                                                                            |
|------------------|----------------------------------------------------------------------------------------|
| `schema_version` | The string you pass with `--schema-version`.                                           |
| `created_at`     | UTC timestamp of when the graph was created.                                           |
| `root_id`        | ID of the root node. Always `.`.                                                       |
| `nodes`          | One node per directory, file, Python symbol, and Markdown section, including the root. |
| `edges`          | One edge from each node's parent to the node.                                          |

Each node has an `id`, an absolute `path`, a `name`, and a `type`. The `type` is `Directory`, `File`, `Class`,
`Method`, `Function`, `Variable`, or `Section`. The `id` of a directory or file is the POSIX-style path relative to the
crawled directory, so it stays the same on every operating system.

Each edge has an `id` in the form `source|TYPE|target`, plus `source`, `type`, and `target`. The `type` is `CONTAINS`
from a directory to its children, and `DECLARES` from a file, class, or section to the symbols or sections it declares.

## Python symbols

AntTrail reads each `.py` file and adds a node for every class, function, method, and variable declared at the top level
of the module or of a class. It does not read function bodies or conditional blocks, so it does not report local
variables, instance attributes such as `self.x`, or names bound inside an `if` or `try` block.

| Type       | What it is                                                  |
|------------|-------------------------------------------------------------|
| `Class`    | A class, including a class nested in another class.         |
| `Method`   | A function, async or not, defined directly in a class body. |
| `Function` | A function defined directly in a module.                    |
| `Variable` | A plain name assigned in a module or class body.            |

Tuple targets such as `a, b = 1, 2` produce one variable per name. Augmented assignments (`x += 1`), attribute targets,
and subscripts do not produce variables.

A symbol's `id` is the ID of its file, then `::`, then its dotted qualified name, for example `shapes.py::Shape.area`.
The `path` is the file's path, `name` is the last part of the qualified name, and `line_start` and `line_end` give the
lines the symbol spans. A decorated function starts at its `def` line. Directory and file nodes have no line range.

If a name is bound more than once in the same scope, such as a property and its setter, AntTrail keeps the first
binding.

Use `--symbol-depth N` to limit the levels added below each file. A top-level symbol has depth 1, and a member of a
top-level class has depth 2. A depth of 0 adds no symbols and does not open Python files.

AntTrail parses files with the grammar of the Python version that runs it. On Python 3.11, a file that uses newer syntax
is reported as a parse error.

## Markdown sections

AntTrail reads each `.md` and `.markdown` file and adds a `Section` node for every heading. The `name` is the heading
text. A section runs from its heading to the line before the next heading of the same or a higher level, or to the end
of the file, without trailing blank lines. It includes its subsections, so the range of a level 2 heading covers all of
its level 3 headings. Text before the first heading belongs to no section.

AntTrail recognizes ATX headings (`## Title`, with an optional closing run of `#`) and single-line setext headings (a
text line underlined with `=` for level 1 or `-` for level 2). It ignores `#` lines inside fenced code blocks, YAML
front matter at the top of the file, indented code, and block quotes.

A section's `id` is the ID of its file, then `::`, then the headings from the top level down, joined with `/`, for
example
`README.md::AntTrail/Quickstart/Generate a graph`. The top-level heading is part of the ID, so a file with one `#` title
puts that title first. A heading that repeats under the same parent gets a numeric suffix from its second use, so the
IDs
`guide.md::Guide/Usage/Example` and `guide.md::Guide/Usage/Example (2)` name two sections.

A top-level section is declared by its file, and any other section by its enclosing section. Like symbols, sections
carry
`line_start` and `line_end`.

Use `--section-depth N` to limit the levels added below each file. A top-level heading has depth 1. A depth of 0 adds no
sections and does not open Markdown files.

Nodes and edges appear in a stable order: for each directory, its subdirectories come first, then its files, each sorted
by name.

## Example

Running `anttrail tests/assets --schema-version 1.0 --output graph.yaml` on the test fixture produces the following
graph. The `path` values depend on where you run the command.

```yaml
schema_version: '1.0'
created_at: '2026-11-12T11:40:10.981322Z'
root_id: .
nodes:
- id: .
  path: /home/you/tests/assets
  name: assets
  type: Directory
- id: dir_1
  path: /home/you/tests/assets/dir_1
  name: dir_1
  type: Directory
- id: dir_2
  path: /home/you/tests/assets/dir_2
  name: dir_2
  type: Directory
- id: README.md
  path: /home/you/tests/assets/README.md
  name: README.md
  type: File
- id: dir_1/dir_1_1
  path: /home/you/tests/assets/dir_1/dir_1_1
  name: dir_1_1
  type: Directory
- id: dir_1/Doc_1_1.md
  path: /home/you/tests/assets/dir_1/Doc_1_1.md
  name: Doc_1_1.md
  type: File
- id: dir_1/dir_1_1/Doc_1_1_1.md
  path: /home/you/tests/assets/dir_1/dir_1_1/Doc_1_1_1.md
  name: Doc_1_1_1.md
  type: File
- id: dir_2/Doc_2_1.md
  path: /home/you/tests/assets/dir_2/Doc_2_1.md
  name: Doc_2_1.md
  type: File
edges:
- id: .|CONTAINS|dir_1
  source: .
  type: CONTAINS
  target: dir_1
- id: .|CONTAINS|dir_2
  source: .
  type: CONTAINS
  target: dir_2
- id: .|CONTAINS|README.md
  source: .
  type: CONTAINS
  target: README.md
- id: dir_1|CONTAINS|dir_1/dir_1_1
  source: dir_1
  type: CONTAINS
  target: dir_1/dir_1_1
- id: dir_1|CONTAINS|dir_1/Doc_1_1.md
  source: dir_1
  type: CONTAINS
  target: dir_1/Doc_1_1.md
- id: dir_1/dir_1_1|CONTAINS|dir_1/dir_1_1/Doc_1_1_1.md
  source: dir_1/dir_1_1
  type: CONTAINS
  target: dir_1/dir_1_1/Doc_1_1_1.md
- id: dir_2|CONTAINS|dir_2/Doc_2_1.md
  source: dir_2
  type: CONTAINS
  target: dir_2/Doc_2_1.md
```

### Python symbols example

For a directory that contains one file, `shapes.py`:

```python
SIDES = 4


class Shape:
    def area(self):
        return 0
```

AntTrail adds these nodes after the `shapes.py` file node, and these edges. The `path` values depend on where you run
the command.

```yaml
nodes:
- id: shapes.py::SIDES
  path: /home/you/project/shapes.py
  name: SIDES
  type: Variable
  line_start: 1
  line_end: 1
- id: shapes.py::Shape
  path: /home/you/project/shapes.py
  name: Shape
  type: Class
  line_start: 4
  line_end: 6
- id: shapes.py::Shape.area
  path: /home/you/project/shapes.py
  name: area
  type: Method
  line_start: 5
  line_end: 6
edges:
- id: shapes.py|DECLARES|shapes.py::SIDES
  source: shapes.py
  type: DECLARES
  target: shapes.py::SIDES
- id: shapes.py|DECLARES|shapes.py::Shape
  source: shapes.py
  type: DECLARES
  target: shapes.py::Shape
- id: shapes.py::Shape|DECLARES|shapes.py::Shape.area
  source: shapes.py::Shape
  type: DECLARES
  target: shapes.py::Shape.area
```

## Compact output

Add `--compact` to leave the `path` of each node and all `edges` out of the output. A node's path is the crawled
directory plus its `id`, and an edge joins a node to a parent that the `id` already names, so the compact form holds the
same information in about one third of the bytes. The default output does not change.

## Validation report

Add `--validate` to print an integrity report before the graph. For the graph above, the report is:

```json
{"is_valid":true,"is_weakly_connected":true,"missing_edge_endpoints":[],"isolated_node_ids":[],"unreachable_from_root":[],"invalid_containment_nodes":[]}
```

| Field                       | Meaning                                                                                 |
|-----------------------------|-----------------------------------------------------------------------------------------|
| `is_valid`                  | `true` when the graph is connected and every node has one parent.                       |
| `is_weakly_connected`       | `true` when every node is reachable from the root.                                      |
| `missing_edge_endpoints`    | Edges that point to a node that does not exist.                                         |
| `isolated_node_ids`         | Nodes, other than the root, that have no edges.                                         |
| `unreachable_from_root`     | Nodes that cannot be reached from the root.                                             |
| `invalid_containment_nodes` | Nodes, other than the root, that lack exactly one `CONTAINS` or `DECLARES` parent edge. |
