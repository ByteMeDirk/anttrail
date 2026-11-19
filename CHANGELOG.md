# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 0.2.0

### Added

- `Section` nodes for the headings of `.md` and `.markdown` files, with `line_start` and `line_end`, linked to their
  file or enclosing section by `DECLARES` edges. IDs look like `README.md::AntTrail/Quickstart`.
- `--section-depth` to limit how many levels of Markdown sections are added.
- Query options that print a short answer instead of the graph: `--outline PATH`, `--find TEXT` with `--type` and
  `--limit`, `--at PATH:LINE`, and `--show ID`.
- `--compact` to leave node paths and edges out of the output, which makes it about two thirds smaller.
- A typed package marker (`py.typed`), so type checkers read the package's annotations.
- `benchmarks/run_benchmark.py`, which compares AntTrail answers with plain-text baselines.

### Changed

- `--silence-read-failure` also skips Markdown files that cannot be read. Graphs for directories that contain Markdown
  files now include `Section` nodes. Pass `--section-depth 0` to get the previous output.

## 0.1.1

### Added

- `anttrail` command that crawls a directory and writes a `Directory`/`File` containment graph as JSON or YAML.
- `--validate` option that reports missing edge endpoints, isolated nodes, unreachable nodes, and invalid containment.
- Nodes for the classes, functions, methods, and variables declared in Python files, linked to their file or class by
  `DECLARES` edges. Symbol nodes carry `line_start` and `line_end`.
- `--symbol-depth` to limit how many levels of Python symbols are added.
- Default exclusion of `.git`, virtual environments, and cache directories, with `--no-ignore` to include them.
- `--silence-read-failure` to skip unreadable directories and unparseable Python files, and a one-line error when they
  are not skipped.
- Tests for the models, the graph generator, and the command line, and a CI workflow that runs lint, format checks, and
  tests.

### Changed

- The minimum supported Python version is 3.11.
- `--schema-version` has a default, so `anttrail DIRECTORY` works without other options.

### Removed

- The `--verbose` option, which had no effect.
- The `.txt` output format, which was never implemented.
