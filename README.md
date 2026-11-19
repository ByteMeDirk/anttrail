# AntTrail

[![PyPI](https://img.shields.io/pypi/v/anttrail)](https://pypi.org/project/anttrail/)
[![Python versions](https://img.shields.io/pypi/pyversions/anttrail)](https://pypi.org/project/anttrail/)
[![CI](https://github.com/ByteMeDirk/anttrail/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ByteMeDirk/anttrail/actions/workflows/ci.yml)
[![Security](https://github.com/ByteMeDirk/anttrail/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/ByteMeDirk/anttrail/actions/workflows/security.yml)
[![License](https://img.shields.io/pypi/l/anttrail)](LICENSE)

AntTrail is a lightweight Python library for building structured, queryable repository graphs. It helps agents and other
software systems retrieve object context without reading or scraping an entire repository.

AntTrail represents repository artefacts and their relationships as a graph.

The result is a concise, navigable “ant trail” through a repository: a machine-readable map that helps downstream
systems identify relevant artefacts and understand how they relate.

## Quickstart

Install the package into your active Python environment:

```bash
uv add anttrail
```

Or, when working from a cloned repository:

```bash
uv sync
```

Verify that the command is available:

```bash
anttrail --version
```

### Generate a graph

Pass the directory you want to crawl as the required positional argument:

```bash
anttrail ./docs
```

When no output path is supplied, AntTrail writes the generated graph as JSON to standard output. Redirect it to a file
if needed:

```bash
anttrail ./docs > graph.json
```

### Write graph output to a file

Use `--output` (or `-o`) to write the graph to a file. The filename extension determines the output format, either
`.json` or `.yaml`:

```bash
anttrail ./docs --output graph.json
```

The directory argument must already exist. AntTrail resolves it to an absolute path before crawling.

### Validate the graph

Add `--validate` to validate the generated graph before writing it. Integrity results are emitted as JSON when
validation produces a graph-integrity result:

```bash
anttrail ./docs --validate --output graph.json
```

### Select a schema version

Supply a schema version when your workflow requires you to output evolving schemas:

```bash
anttrail ./docs --schema-version 1.0 --output graph.json
```

The short form is `-s`:

```bash
anttrail ./docs -s 1.0 -o graph.json
```

### Handle unsupported files or output formats

By default, AntTrail stops with a one-line error when a directory cannot be read or the output format is unsupported.
Use the silence flags only when partial output is acceptable:

```bash
# Continue crawling when a directory cannot be read.
anttrail ./docs --silence-read-failure --output graph.json

# Do not fail the command when the selected output format cannot be written.
anttrail ./docs --silence-write-failure --output graph.unsupported
```

### Include Python symbols

AntTrail adds a node for each class, function, method, and variable declared at the top level of a `.py` file or of a
class. It does not read function bodies or conditional blocks. Use `--symbol-depth` to limit how many levels it adds:

```bash
# Top-level classes, functions, and variables only.
anttrail ./src --symbol-depth 1

# Also add class members.
anttrail ./src --symbol-depth 2

# Files and directories only.
anttrail ./src --symbol-depth 0
```

Without the option, AntTrail adds every level. If a Python file has a syntax error or cannot be read, AntTrail stops
with a one-line error. Add `--silence-read-failure` to keep the file's node and skip its symbols instead.

### Include Markdown sections

AntTrail adds a `Section` node for each heading of a `.md` or `.markdown` file, with the lines the section spans. Use
`--section-depth` to limit how many levels it adds:

```bash
# Top-level headings only.
anttrail ./docs --section-depth 1

# Files and directories only.
anttrail ./docs --section-depth 0
```

Without the option, AntTrail adds every level. Headings inside fenced code blocks and front matter are ignored.

### Ask a question instead of reading the graph

The full graph grows with the repository. To get a short answer instead, add one query option. Each line of the answer
has the form `PATH:LINE_START-LINE_END`, a tab, the node type, a tab, and the node ID.

```bash
# What is in this file? Sections or symbols, indented by depth.
anttrail . --outline README.md

# Where is a node with this name? Add --type and --limit to narrow the matches.
anttrail . --find area --type Method

# Which section or symbol contains this line, and what contains that?
anttrail . --at README.md:57

# What does this section or symbol say? Prints those lines and nothing else.
anttrail . --show "README.md::AntTrail/Quickstart"
```

To shrink the full graph instead, add `--compact`, which leaves out each node's `path` and all edges. For when to use
which option, see [Agent usage](docs/agent-usage.md).

### Skip or include directories

AntTrail skips `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `.pytest_cache`, `.mypy_cache`, and `.ruff_cache`
by default. Pass `--no-ignore` to include them:

```bash
anttrail . --no-ignore
```

For the structure of the output and a full example, see [Graph format](docs/graph-format.md).

### Command reference

```text
anttrail [OPTIONS] DIRECTORY
```

| Option                     | Short form   | Purpose                                                                                   |
|----------------------------|--------------|-------------------------------------------------------------------------------------------|
| `--version`                | `-v`         | Show the installed AntTrail version and exit                                              |
| `--schema-version VERSION` | `-s VERSION` | Select the graph schema version                                                           |
| `--output PATH`            | `-o PATH`    | Write the generated graph to a file; otherwise print JSON to the console                  |
| `--validate`               | -            | Validate the generated graph before output                                                |
| `--symbol-depth N`         | -            | Limit how many levels of Python symbols are added; `0` adds none                          |
| `--section-depth N`        | -            | Limit how many levels of Markdown sections are added; `0` adds none                       |
| `--compact`                | -            | Leave node paths and edges out of the output                                              |
| `--outline PATH`           | -            | Print the sections or symbols of one file instead of the graph                            |
| `--find TEXT`              | -            | Print the nodes whose name contains `TEXT`; use with `--type` and `--limit`               |
| `--at PATH:LINE`           | -            | Print the node that contains a line, then its ancestors                                   |
| `--show ID`                | -            | Print the lines of one section or symbol                                                  |
| `--silence-read-failure`   | -            | Skip directories, Python files, and Markdown files that cannot be read instead of failing |
| `--silence-write-failure`  | -            | Do not fail when the output format is unsupported                                         |
| `--no-ignore`              | -            | Include the directories that are skipped by default                                       |

Run `anttrail --help` to view the complete command-line help for the installed version.

### Troubleshooting

If `anttrail --version` prints `0+unknown`, the package is running from source without being installed. Run `uv sync`
to install it with its metadata.

See the [changelog](CHANGELOG.md) for changes between versions.

## Current capabilities

AntTrail currently:

- Traverses a configured repository or directory root.
- Creates graph nodes for directories and files.
- Creates graph nodes for the classes, functions, methods, and variables declared in Python files.
- Creates graph nodes for the headings of Markdown files, with their line ranges.
- Creates directed `CONTAINS` relationships for immediate parent-child filesystem relationships.
- Creates directed `DECLARES` relationships from a file, class, or section to the symbols or sections it declares.
- Uses normalized root-relative IDs for stable graph traversal.
- Validates containment relationships, node references, root reachability, and weak graph connectivity.
- Exports the graph as JSON or YAML.
- Answers short questions about the graph: the outline of a file, nodes by name, the node at a line, and the lines of
  one node.
- Skips common non-source directories such as `.git` and virtual environments.

AntTrail reads Python files only for the symbols listed above, and Markdown files only for their headings. It does not
extract imports, calls, inheritance, or instance attributes, and it does not extract content from other file types. The
queries match node names and positions. They do not search text, so use `grep` for that.

## Motivation

Large repositories are expensive for agents read through. Loading an entire repo into an agent context window can be
ineffective and costly.

The project was motivated by two related use cases:

1. **Agent-oriented repository navigation**  
   Build an explainable repository map that supports targeted context retrieval, navigation, and dependency-aware
   traversal without overloading an agent’s context window.
2. **Dynamic ontology generation from multimodal sources**  
   Build structural and semantic graphs from repository and document artefacts that can later support ontology
   generation, classification, metadata extraction, and relationship discovery.

## Planned direction

**Note**: this is not supposed to be another Graph database or query engine...

Future versions may support:

- Extended relationship functionality.
- Object parsing, such as modules, classes, functions, imports, etc. if the object is a `.py` file.
- NLP-based metadata and entity extraction from non-standard objects.
- OCR-based metadata extraction from images and documents.
- Graph traversal beyond the current queries.
- Dreaming big here: export to JSON, graph databases, GraphML, DOT, and Cypher-compatible formats.

AntTrail is intended to remain lightweight and deterministic, so I will not be incorporating an LLM to do the heavy
lifting. I want it to be local-first, lightweight, deterministic, extensible, and agent-friendly.

---

Please note that this is currently a project in its infancy.
