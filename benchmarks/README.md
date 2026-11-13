# Benchmark

This benchmark measures whether AntTrail answers a question with less output than plain
text tools do. It needs no network access and no language model.

## Run the benchmark

From the repository root:

```bash
uv run python benchmarks/run_benchmark.py
```

The script prints one row for each task, then the size of a full graph for the fixture
and for this repository. To make the script exit with status 1 unless AntTrail's answer
is smaller than the baseline for every task, add `--check`:

```bash
uv run python benchmarks/run_benchmark.py --check
```

## Tasks

Each task is a question an agent might ask. The script runs them against
`benchmarks/fixtures/sample_repo`, a small project with Markdown guides and Python
modules.

| Task               | Question                                              | Text-tool baseline                                  |
|--------------------|-------------------------------------------------------|-----------------------------------------------------|
| `list_directory`   | Which files are in `docs/`?                           | `ls docs`                                           |
| `file_outline`     | What are the headings of `docs/usage.md`?             | `grep -n '^#' docs/usage.md`                        |
| `section_text`     | What does `usage.md` say under "Configure pricing"?   | `grep -n '^#'`, then read the lines of the section  |
| `find_class`       | Where is the class `Cart` defined?                    | `grep -rn 'class Cart' src`                         |
| `enclosing_symbol` | Which method contains the `subtotal` line of `cart.py`? | Read `src/shop/cart.py` and scan upward           |

## Read the results

The columns report the number of tool calls and the bytes of output that the agent has
to read.

| Column           | Meaning                                                                          |
|------------------|----------------------------------------------------------------------------------|
| `Text tools`     | The baseline from the table above.                                               |
| `AntTrail today` | Printing the full graph. A dash means the graph does not hold the information.   |
| `AntTrail query` | The targeted answer from Stage 3 of the Phase 3 strategy. A dash means it does not exist yet. |
| `Verdict`        | `smaller`, `larger`, or `cannot answer`, using the query answer if there is one. |

The baselines are simulated in Python with the same output format as the real tools, so
the sizes are the same on every operating system. They favor text tools in two ways: the
agent reads exactly the right lines of a section, and `grep` output for the class gives
no end line, so the baseline does not count the extra call that an agent needs to read the
whole class.

The full-graph size has the absolute paths and the timestamp replaced with fixed values,
so it does not depend on where you check out the repository. The crawl time and the
numbers for this repository vary from run to run, so treat them as a guide.

## Add a task

1. Add a function that returns an `Answer` for the baseline, and add a `Task` to
   `TASKS` in `run_benchmark.py`.
2. Set `anttrail_today` to `full_graph_answer` if the graph already holds the
   information. Leave `anttrail_query` empty until the query option exists.
3. Run `uv run pytest tests/test_benchmark.py`.

The benchmark is not a required check yet. Stage 3 of the Phase 3 strategy decides
whether `--check` runs in CI.
