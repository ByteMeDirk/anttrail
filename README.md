# AntTrail

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

When no output path is supplied, Anttrail writes the generated graph as JSON to standard output. Redirect it to a file
if needed:

```bash
anttrail ./docs > graph.json
```

### Write graph output to a file

Use `--output` (or `-o`) to write the graph to a file. Where supported, the filename extension determines the output
format:

```bash
anttrail ./docs --output graph.json
```

The directory argument must already exist. Anttrail resolves it to an absolute path before crawling.

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

By default, read and write failures are surfaced. Use the silence flags only when partial output is acceptable:

```bash
# Continue crawling when individual files cannot be read or are unsupported.
anttrail ./docs --silence-read-failure --output graph.json

# Do not fail the command when the selected output format cannot be written.
anttrail ./docs --silence-write-failure --output graph.unsupported
```

### Increase verbosity

Repeat `--verbose` to request more verbose command output:

```bash
anttrail ./docs --verbose --output graph.json
anttrail ./docs --verbose --verbose --output graph.json
```

### Command reference

```text
anttrail [OPTIONS] DIRECTORY
```

| Option                     | Short form   | Purpose                                                                  |
|----------------------------|--------------|--------------------------------------------------------------------------|
| `--version`                | `-v`         | Show the installed Anttrail version and exit                             |
| `--schema-version VERSION` | `-s VERSION` | Select the graph schema version                                          |
| `--output PATH`            | `-o PATH`    | Write the generated graph to a file; otherwise print JSON to the console |
| `--validate`               | -            | Validate the generated graph before output                               |
| `--silence-read-failure`   | -            | Ignore individual file-read failures, including unsupported formats      |
| `--silence-write-failure`  | -            | Ignore failures caused by unsupported output formats                     |
| `--verbose`                | -            | Increase verbosity; repeat the option for additional verbosity           |

Run `anttrail --help` to view the complete command-line help for the installed version.

## Current capabilities

AntTrail currently:

- Traverses a configured repository or directory root.
- Creates graph nodes for directories and files.
- Creates directed `CONTAINS` relationships for immediate parent-child filesystem relationships.
- Uses normalized root-relative IDs for stable graph traversal.
- Validates containment relationships, node references, root reachability, and weak graph connectivity.
- Exports a structured graph model and a Cypher-like diagnostic representation.

At present, AntTrail models filesystem structure. It does not yet extract semantic document content.

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
- Graph querying, filtering, and traversal (limited).
- Dreaming big here: export to JSON, graph databases, GraphML, DOT, and Cypher-compatible formats.

AntTrail is intended to remain lightweight and deterministic, so I will not be incorporating an LLM to do the heavy
lifting. I want it to be local-first, lightweight, deterministic, extensible, and agent-friendly.

---

Please note that this is currently a project in its infancy. Part of this endeavor is to produce something original and
challenging. Therefore, **no agent co-authoring/coding** is used in this repository. Subject material in question is
sourced from an LLM or the web, but the code in this repo is made by a human, and the goal is to keep it that way.

> It's gonna be ugly at first, but hopefully it gets better :D