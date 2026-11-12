# Contributing to AntTrail

Thanks for helping with AntTrail. This page explains how to set up the project, how changes get into `main`, and what a
pull request needs to pass.

## Set up

You need Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ByteMeDirk/anttrail.git
cd anttrail
uv sync
uv run anttrail --version
```

## Run the checks

CI runs the same commands, so run them before you push:

```bash
uv run ruff check .
uv run black --check .
uv run pytest
```

To fix formatting and import order automatically:

```bash
uv run ruff check --fix .
uv run black .
```

## Branching model

AntTrail uses trunk-based development.

- `main` is always releasable. Nobody pushes to it directly.
- Work happens on short-lived branches, ideally merged within 2 days. Break large changes into smaller pull requests.
- Name branches `type/short-description`, for example `feat/symbol-depth` or `fix/symlink-loop`.
- Every change merges by pull request using squash merge, so each pull request becomes one commit on `main`.
- If a change is not ready for users, merge it with the new behavior turned off instead of keeping a long-lived branch.

## Commit messages and pull request titles

AntTrail follows [Conventional Commits](https://www.conventionalcommits.org/). Because pull requests are squash merged,
the pull request title becomes the commit message, so it must follow the format:

```text
type(scope): summary
```

Types:

| Type       | Use for                                 |
|------------|-----------------------------------------|
| `feat`     | A new feature                           |
| `fix`      | A bug fix                               |
| `docs`     | Documentation only                      |
| `test`     | Adding or changing tests                |
| `refactor` | A change that does not alter behavior   |
| `perf`     | A performance improvement               |
| `build`    | Packaging or dependency changes         |
| `ci`       | Workflow changes                        |
| `chore`    | Anything else that does not touch `src` |
| `revert`   | Reverting an earlier commit             |

Scopes: `cli`, `graph`, `parser`, `models`, `ci`, `docs`, `deps`. The scope is optional.

Write the summary in the imperative mood, in lowercase, without a trailing period: `fix(graph): skip symlink loops`.
Mark a breaking change with `!` after the type or scope (`feat(cli)!: rename --depth`) and describe it in a
`BREAKING CHANGE:` footer.

## Open a pull request

1. Create a branch from an up-to-date `main`.
2. Make the change, and add or update tests for any behavior you touch.
3. Update `CHANGELOG.md` under the unreleased version for any change a user would notice. Update `docs/graph-format.md`
   if the graph output changes.
4. Run the checks above.
5. Open a pull request and fill in the template.

A pull request can merge when:

- The required status checks pass.
- All review conversations are resolved.
- The branch is up to date with `main`.

## Write tests

- Put tests in `tests/`, in the file that matches the module (`test_graph.py` for `graph.py`).
- Put fixture files in `tests/assets/` or `tests/python_assets/`.
- Test behavior that a user can observe, such as the graph that comes out for a given directory, and avoid asserting on
  private helpers.
- Add a regression test with every bug fix.
- Do not make network calls in tests.

## Style

- Follow the existing code. Ruff and Black enforce formatting, import order, and a set of lint rules.
- Add type hints to public functions and models.
- Prefer returning values over printing. Only `cli.py` should write to the terminal or exit the process.
- Raise specific exceptions with a message that tells the user what to do next.

## Release process

Only the maintainer publishes releases.

1. Update `version` in `pyproject.toml`, run `uv lock`, and set the date in the `CHANGELOG.md` heading.
2. Merge that change to `main`.
3. Create a GitHub release from a new tag named `vMAJOR.MINOR.PATCH` that matches the version in `pyproject.toml`.
4. The `Publish to PyPI` workflow builds the package and publishes it. It fails if the tag is not on `main` or does not
   match the package version.

PyPI never accepts the same version twice, even after a deletion, so a failed or yanked release needs a new version
number.

## Report a security problem

Do not open a public issue. Follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contribution is licensed under the [Apache License 2.0](LICENSE), the same license
as the project.
