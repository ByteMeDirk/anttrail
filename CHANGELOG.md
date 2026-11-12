# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 0.1.0 (unreleased)

### Added

- `anttrail` command that crawls a directory and writes a `Directory`/`File` containment graph as JSON or YAML.
- `--validate` option that reports missing edge endpoints, isolated nodes, unreachable nodes, and invalid containment.
- Default exclusion of `.git`, virtual environments, and cache directories, with `--no-ignore` to include them.
- `--silence-read-failure` to skip unreadable directories, and a one-line error when they are not skipped.
- Tests for the models, the graph generator, and the command line, and a CI workflow that runs lint, format checks,
  and tests.

### Changed

- The minimum supported Python version is 3.11.
- `--schema-version` has a default, so `anttrail DIRECTORY` works without other options.

### Removed

- The `--verbose` option, which had no effect.
- The `.txt` output format, which was never implemented.
