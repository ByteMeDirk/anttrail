# Phase 3 implementation strategy: sections and cheap retrieval

Status: proposed.

## Background

An agent that used AntTrail gave this feedback:

> The graph would help with questions about structure, such as which files exist, which directories contain what, or
> which functions and classes are defined where. For finding prose under a heading, plain text search is faster. A graph
> that indexed heading nodes with line ranges would make this lookup cheap.

The agent did not find AntTrail more efficient than the tools it already had. The project exists to make retrieval
cheaper than reading a repository, so this is a failure of the main goal and not a missing feature.

### Why it was not efficient

Two separate problems add up.

1. **Markdown is opaque.** AntTrail adds a node for each Markdown file but nothing inside it. A question about prose
   under a heading has no node to land on, so the agent falls back to `grep`.
2. **The only way to use the graph is to read all of it.** AntTrail prints the whole graph and has no way to ask it a
   question. Running `anttrail .` on this repository produces 242 nodes and 241 edges in 95,779 bytes. About 48% of that
   is edges, which repeat what the node IDs already say, and about 19% is absolute paths. For comparison,
   `grep -n '^#' README.md` returns all the README's headings in 640 bytes. Even with perfect heading nodes, an agent
   that must load 96 KB to find one section loses to `grep`.

Fixing only the first problem would add nodes to a graph that is already too expensive to read. Both need to change.

### What this phase does not try to do

AntTrail will not replace text search. `grep` is the right tool for finding a word or phrase anywhere. The goal is to
answer "where is this thing, and which lines hold it" in one small response, and to connect text search results back to
structure. The README's promise still holds: AntTrail stays local, deterministic, and free of LLM calls, and it does not
become a graph database.

## Goal

An agent can do each of these with one call and a response of a few hundred bytes:

- List the outline of a file: its headings, or its classes and methods, with line ranges.
- Find a section, class, function, or file by name.
- Read the text of one section without reading the rest of the file.
- Turn a `grep` hit (`file:line`) into the enclosing section or symbol.

## Scope

In scope:

- Section nodes for Markdown files, with line ranges.
- Query options on the existing command that return small, line-oriented answers.
- A deterministic benchmark that measures the size of the answer against the plain-text-search baseline.
- Documentation that says when to use the graph and when to use `grep`.

Out of scope:

- Indexing the text of sections for full-text search.
- File types other than Markdown (reStructuredText, plain text, YAML, notebooks).
- A server, a long-running process, or an MCP integration. See [Later](#later).
- Caching or incremental crawls. Measure first.
- Any change to how Python symbols are extracted.

## Stage 1: measure

Do this first, so every later claim has a number behind it.

Add `benchmarks/` with a script that runs without network access or an LLM. It uses the repository itself plus a small
Markdown-heavy fixture, and defines a fixed list of tasks:

| Task                                  | Baseline (text tools)                    | AntTrail           |
|---------------------------------------|------------------------------------------|--------------------|
| Get the text under one heading        | `grep -n '^#'`, then read the line range | one call (Stage 3) |
| List the headings of one file         | `grep -n '^#' FILE`                      | one call (Stage 3) |
| Find where a class is defined         | `grep -rn 'class Name'`                  | one call (Stage 3) |
| Find the enclosing function of a line | read the file and scan upward            | one call (Stage 3) |
| List the files in a directory         | `ls`                                     | one call           |

For each task, record the number of calls and the bytes the agent has to read. The script prints a table and exits
non-zero if AntTrail's answer is larger than the baseline for any task, so the benchmark doubles as a regression check.

Record the current numbers in the pull request, including the 95,779-byte full graph, so the improvement is visible.

Exit criteria: the benchmark runs in CI-sized time (under 30 seconds), and today's numbers are written down.

## Stage 2: Markdown section nodes

### Parsing

Add `src/anttrail/markdown_parser.py` with one pure function, in the same style as `python_parser.py`:

```python
def parse_markdown(source: str) -> list[Section]: ...
```

It reads lines and does no I/O. It uses no Markdown library, so the project keeps its two dependencies.

What counts as a heading:

- ATX headings: one to six `#` characters, a space, then text. A closing run of `#` is dropped.
- Setext headings: a text line followed by a line of `=` (level 1) or `-` (level 2).

What does not count:

- Lines inside fenced code blocks (backticks or tildes), so a shell comment such as `# install` in a code sample is not
  a heading.
- A YAML front matter block at the top of the file.
- Indented code (four or more spaces).

### Section ranges

A section runs from its heading line to the line before the next heading of the same or a higher level, or to the end of
the file. Trailing blank lines are not part of the section. A section includes its subsections, so the range of a level
2 heading covers all of its level 3 headings. This is the range an agent wants when it asks to read a section.

Text before the first heading belongs to no section.

### Node model

- `NodeType` gains `SECTION`.
- `BaseNode` already has optional `line_start` and `line_end`, so no new field is needed. `name` is the heading text.
- A section is linked to its parent with a `DECLARES` edge: from the file for a top-level heading, from the enclosing
  section otherwise. This reuses the edge `validate()` already accepts and avoids a new edge type. See
  [Decisions](#decisions).

### Node IDs

A section ID is the file ID, then `::`, then the heading path joined with `/`:

```text
README.md::Quickstart
README.md::Quickstart/Generate a graph
docs/graph-format.md::Python symbols
```

Headings often repeat (several `Example` sections is common). IDs must be unique, and Python's rule of keeping the first
binding would hide real content. Instead, a repeated heading under the same parent gets a numeric suffix:
`README.md::Troubleshooting/Example`, then `README.md::Troubleshooting/Example (2)`. The suffix is stable as long as the
document order does not change. A `/` inside heading text is replaced with `-` so it cannot split the path.

### Graph generator changes

`_traversal` calls the Markdown parser for files with a `.md` or `.markdown` suffix and adds one node and one `DECLARES`
edge per section, using the same helper that Python symbols use. Read and decode failures follow the existing rule: the
file node always stays, and the error is raised unless `--silence-read-failure` is set.

Add `--section-depth N`, which works like `--symbol-depth`: 1 adds top-level headings, 2 adds their children, and 0 adds
none and does not open Markdown files. Without the option, all levels are added.

### Section steps

Each step is one commit, and the test suite passes after each one.

1. `feat(models): add section node type`.
2. `feat(parser): extract Markdown sections with line ranges`. Unit tests on strings. Cases: ATX and setext headings,
   closing hashes, fenced code with `#` lines, front matter, indented code, duplicate headings, a `/` in a heading,
   skipped heading levels (`#` then `###`), an empty file, a file with no headings, and each depth value.
3. `feat(graph): add section nodes for Markdown files`. Fixture in `tests/markdown_assets/`. Tests cover ranges, IDs,
   duplicate suffixes, validation, and the failure cases.
4. `feat(cli): add --section-depth`.

Exit criteria: `anttrail . --validate` on this repository reports `is_valid: true`, and the section ranges for
`README.md` match the headings that `grep -n '^#'` finds, minus any inside code blocks.

## Stage 3: query options

This stage fixes the second problem. The agent asks a question and gets a small answer, so it never loads the full
graph.

All of these are options on the existing command, so `anttrail DIRECTORY` keeps working. Each one prints lines in the
form `path:line_start-line_end<TAB>Type<TAB>id`, which an agent can pass straight to a file read. Without a query
option, the command still prints the full graph.

| Option           | Answers                                       | Example output                                          |
|------------------|-----------------------------------------------|---------------------------------------------------------|
| `--outline PATH` | What is in this file?                         | the file's sections or symbols, indented by depth       |
| `--find TEXT`    | Where is a node with this name?               | every node whose name contains `TEXT`                   |
| `--type TYPE`    | (filter for `--find`) Only nodes of this type | `--find area --type Method`                             |
| `--at PATH:LINE` | Which node contains this line?                | the innermost section or symbol, then its ancestors     |
| `--show ID`      | What does this section or symbol say?         | the lines from `line_start` to `line_end`, nothing else |

### Design notes

- **Matching.** `--find` is a case-insensitive substring match on the node name, and `--type` accepts the `NodeType`
  values. No regular expressions and no ranking. Results come out in graph order, which is stable.
- **`--at` is the bridge to `grep`.** An agent searches text with `grep -n`, then asks `--at README.md:57` to learn
  which section that hit sits in. This keeps text search where it is strong and adds structure on top of it.
- **`--show` stays inside the crawl.** It resolves the ID against the graph and reads only that file's line range. An ID
  that is not in the graph is an error, so it cannot read an arbitrary path. Files are read by their crawled path and
  symlinks are not followed outside the root.
- **Size.** Every query answer is bounded by the number of matches, not by the size of the repository. `--find` takes an
  optional `--limit N` with a default of 50, and says when it truncated.
- **Errors.** An unknown file, line, or ID prints the usual one-line `anttrail: error:` message and exits non-zero.
- **Compact graph output.** Add `--compact`, which omits `path` and `edges` from JSON output. Both can be rebuilt from
  the node `id`s, and together they are about two thirds of the current output. The default output does not change.

### Query steps

1. `feat(cli): add --outline and --find`. Shared output formatter with tests for the line format.
2. `feat(cli): add --at`. Tests for nested sections, a line outside any node, and a Python method.
3. `feat(cli): add --show`. Tests for a section, a symbol, an unknown ID, and a file that changed since the crawl.
4. `feat(cli): add --compact`.

Exit criteria: every task in the Stage 1 table is answered in one call, and the benchmark shows AntTrail's answer is
smaller than the baseline for each of them.

## Stage 4: documentation and release

- Add `docs/agent-usage.md`. State plainly which questions the graph answers cheaply (structure, locating a node,
  reading one section) and which it does not (finding arbitrary text, which `grep` does better). Include the `grep` then
  `--at`
  pattern and a short example of each query option.
- Update `docs/graph-format.md` with the `Section` type, the ID scheme, and the duplicate-heading rule.
- Update the README command reference and capability list. Remove "Graph querying, filtering, and traversal (limited)"
  from the planned list once it is true, and keep the sentence that says AntTrail is not a query engine.
- Add the changes to `CHANGELOG.md` under the new version.
- Release as `0.2.0`. This adds features and a node type, and it is a pre-1.0 change.
- Re-run the original task with an agent and ask for the same kind of feedback. The benchmark measures output size, but
  the real acceptance test is whether the agent finds the tool faster than plain text search.

## Acceptance criteria

- The Stage 1 benchmark passes: for every task, AntTrail needs one call, and its answer is smaller than the baseline.
- `anttrail . --outline README.md` lists the README's headings with line ranges in under 1 KB.
- `anttrail . --show "README.md::Quickstart"` prints the Quickstart section and nothing else.
- `anttrail . --at README.md:57` names the section that contains that line.
- `anttrail . --compact` is at least 60% smaller than the full output on this repository.
- Existing commands and the default output are unchanged. The existing tests pass without edits.
- Output is identical across two runs, apart from `created_at`.

## Risks

- **Graph size.** Sections add nodes, and a documentation-heavy repository could add thousands. The query options and
  `--compact` exist because of this. `--section-depth` caps the growth when someone still wants the full graph.
- **Markdown edge cases.** Markdown has several dialects. The parser follows CommonMark for headings and code fences,
  and it does not try to handle headings inside HTML blocks or raw directives. Document this instead of widening the
  parser.
- **Stale ranges.** `--show` reads the file at query time, but the line range comes from the crawl. If the file changed
  in between, the lines could be wrong. Because each query crawls first, this only matters if a graph is saved and
  reused, so the saved-graph case needs a documented warning.
- **Crawl cost per query.** Each query re-crawls the directory. For typical repositories that takes milliseconds. Stage
  1 records the time, and a cache is only worth adding if the numbers say so.
- **CLI growth.** Five new options on one command make `--help` long. Grouping them under a "Query" heading in the help
  output keeps it readable, and subcommands can wait until a breaking release.
- **Schema drift.** A new node type changes the output for existing consumers. The changelog is the only signal, because
  `schema_version` is a free-form string you set.

## Decisions

1. **Edge type for sections.** Reuse `DECLARES`, so `validate()` and consumers need no change. A dedicated edge such as
   `HAS_SECTION` is more precise, but it adds a type for no behavior difference today.
2. **Query options on the existing command.** This keeps `anttrail DIRECTORY` working and avoids a breaking change.
   Subcommands (`anttrail query ...`) would read better, and they are an option for 1.0.
3. **Substring matching only.** It is predictable and cheap. Regular expressions and ranking are the first step toward
   becoming a query engine, which the README rules out.
4. **Duplicate headings get a numeric suffix.** This keeps every section reachable, unlike the Python rule of keeping
   the first binding.
5. **No Markdown dependency.** A line scanner handles headings and fences in about 60 lines and keeps installs small.

## Later

These are worth revisiting only if Stage 1 and the follow-up agent test show a gap:

- A cached or saved graph, and queries that read it without crawling.
- Other prose formats, in the order that real repositories use them.
- An MCP server or similar wrapper, so an agent can call the queries as tools without spawning a process.
- Docstring nodes for Python, so a lookup can return the description of a symbol without its body.

## Open questions

1. Should `--show` print a header line with the ID and range, or only the text? A header costs a few bytes and makes the
   output self-describing. It is easier for an agent to use, and harder to pipe.
2. Is `0.2.0` the right version, or should this wait for a release that also changes the schema's documented guarantees?
3. Should `--find` search heading text only, or also match the file path? Matching the path would let `--find readme`
   return the file as well as its sections.
4. Do you want the benchmark in CI as a required check, or only run by hand?
