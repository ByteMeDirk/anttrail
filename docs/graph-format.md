# Graph format

AntTrail writes one graph per run. This page describes the fields and shows the output for a small directory.

## Fields

| Field            | Description                                                                |
|------------------|----------------------------------------------------------------------------|
| `schema_version` | The string you pass with `--schema-version`.                               |
| `created_at`     | UTC timestamp of when the graph was created.                               |
| `root_id`        | ID of the root node. Always `.`.                                           |
| `nodes`          | One node per directory or file, including the root.                        |
| `edges`          | One `CONTAINS` edge from each node's parent directory to the node.         |

Each node has an `id`, an absolute `path`, a `name`, and a `type` of `Directory` or `File`. The `id` is the POSIX-style
path relative to the crawled directory, so it stays the same on every operating system.

Each edge has an `id` in the form `source|CONTAINS|target`, plus `source`, `type`, and `target`.

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
| `invalid_containment_nodes` | Nodes, other than the root, that do not have exactly one parent.     |
