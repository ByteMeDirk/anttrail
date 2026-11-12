# Graph format

AntTrail writes one graph per run. This page describes the fields and shows the output for a small directory.

## Fields

| Field            | Description                                                                |
|------------------|----------------------------------------------------------------------------|
| `schema_version` | The string you pass with `--schema-version`.                               |
| `created_at`     | UTC timestamp of when the graph was created.                               |
| `root_id`        | ID of the root node. Always `.`.                                           |
| `nodes`          | One node per directory, file, and Python symbol, including the root.       |
| `edges`          | One edge from each node's parent to the node.                              |

Each node has an `id`, an absolute `path`, a `name`, and a `type`. The `type` is `Directory`, `File`, `Class`,
`Method`, `Function`, or `Variable`. The `id` of a directory or file is the POSIX-style path relative to the crawled
directory, so it stays the same on every operating system.

Each edge has an `id` in the form `source|TYPE|target`, plus `source`, `type`, and `target`. The `type` is `CONTAINS`
from a directory to its children, and `DECLARES` from a file or class to the symbols it declares.

## Python symbols

AntTrail reads each `.py` file and adds a node for every class, function, method, and variable declared at the top
level of the module or of a class. It does not read function bodies or conditional blocks, so it does not report local
variables, instance attributes such as `self.x`, or names bound inside an `if` or `try` block.

| Type       | What it is                                                               |
|------------|--------------------------------------------------------------------------|
| `Class`    | A class, including a class nested in another class.                      |
| `Method`   | A function, async or not, defined directly in a class body.              |
| `Function` | A function defined directly in a module.                                 |
| `Variable` | A plain name assigned in a module or class body.                         |

Tuple targets such as `a, b = 1, 2` produce one variable per name. Augmented assignments (`x += 1`), attribute targets,
and subscripts do not produce variables.

A symbol's `id` is the ID of its file, then `::`, then its dotted qualified name, for example `shapes.py::Shape.area`.
The `path` is the file's path, `name` is the last part of the qualified name, and `line_start` and `line_end` give the
lines the symbol spans. A decorated function starts at its `def` line. Directory and file nodes have no line range.

If a name is bound more than once in the same scope, such as a property and its setter, AntTrail keeps the first binding.

Use `--symbol-depth N` to limit the levels added below each file. A top-level symbol has depth 1, and a member of a
top-level class has depth 2. A depth of 0 adds no symbols and does not open Python files.

AntTrail parses files with the grammar of the Python version that runs it. On Python 3.11, a file that uses newer syntax
is reported as a parse error.

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

AntTrail adds these nodes after the `shapes.py` file node, and these edges. The `path` values depend on where you run the
command.

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

## Validation report

Add `--validate` to print an integrity report before the graph. For the graph above, the report is:

```json
{"is_valid":true,"is_weakly_connected":true,"missing_edge_endpoints":[],"isolated_node_ids":[],"unreachable_from_root":[],"invalid_containment_nodes":[]}
```

| Field                       | Meaning                                                              |
|-----------------------------|----------------------------------------------------------------------|
| `is_valid`                  | `true` when the graph is connected and every node has one parent.    |
| `is_weakly_connected`       | `true` when every node is reachable from the root.                   |
| `missing_edge_endpoints`    | Edges that point to a node that does not exist.                      |
| `isolated_node_ids`         | Nodes, other than the root, that have no edges.                      |
| `unreachable_from_root`     | Nodes that cannot be reached from the root.                          |
| `invalid_containment_nodes` | Nodes, other than the root, that lack exactly one `CONTAINS` or `DECLARES` parent edge. |
