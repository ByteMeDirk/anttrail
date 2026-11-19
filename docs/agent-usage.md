# Agent usage

AntTrail helps an agent find where something is in a repository without reading the whole repository. This page says
which questions it answers cheaply, which it does not, and how to combine it with `grep`.

## What the graph answers well

| Question                                    | Command                              |
|---------------------------------------------|--------------------------------------|
| What are the headings of this file?         | `anttrail . --outline docs/usage.md` |
| Which functions and classes does it define? | `anttrail . --outline src/app.py`    |
| Where is a section or symbol named X?       | `anttrail . --find X`                |
| Which section or method contains line N?    | `anttrail . --at PATH:N`             |
| What does this section or symbol say?       | `anttrail . --show ID`               |

Each answer is limited by the number of matches, not by the size of the repository. A line has the form
`PATH:LINE_START-LINE_END`, a tab, the node type, a tab, and the node ID. Pass the path and range straight to a file
read, or pass the ID to `--show`. In `--outline`, each line is indented by two spaces for each level of depth.

## What the graph does not answer

AntTrail indexes names and positions. It does not index the text under a heading or the body of a function. To find a
phrase, a call site, or a configuration key, use `grep`. A text tool also stays smaller than AntTrail for answers that
fit on one line, such as listing the files in a directory with `ls`.

## Combine `grep` with `--at`

Search for text with `grep -n`, then ask AntTrail which section or symbol each hit sits in. For example, if a hit is on
line 57 of `README.md`, the output looks like this (the sections depend on your file):

```bash
grep -n "retry" README.md
# 57:Set the retry count with --retries.

anttrail . --at README.md:57
# README.md:52-61	Section	README.md::AntTrail/Quickstart/Write graph output to a file
# README.md:17-153	Section	README.md::AntTrail/Quickstart
# README.md:1-204	Section	README.md::AntTrail
# README.md	File	README.md
```

The first line names the innermost node, and the lines after it are its ancestors within the file. A line outside any
section or symbol returns the file alone.

## Read one section

If you know the heading, find its ID, then show it:

```bash
anttrail . --find "Quickstart" --type Section
# README.md:17-153	Section	README.md::AntTrail/Quickstart

anttrail . --show "README.md::AntTrail/Quickstart"
```

`--show` reads only a node that is in the graph, and only from a file inside the crawled directory. If the file has
changed since the crawl, it stops with an error. Run the command again to crawl the current files.

## Limits on matches

`--find` matches names without regard to case, and it matches substrings only. It lists at most 50 nodes, and the last
line says how many matched if there were more. Use `--limit N` to change the maximum, or `--type` to narrow the matches
to `Directory`, `File`, `Class`, `Method`, `Function`, `Variable`, or `Section`.

## Smaller graph output

When you need the whole graph, add `--compact`. It leaves out each node's `path` and all edges, and it is about two
thirds smaller. Rebuild a path from the crawled directory and the node `id`. The edge from a node's parent is implied by
the `id`.

To measure how these answers compare with `ls` and `grep`, run `uv run python benchmarks/run_benchmark.py`.
