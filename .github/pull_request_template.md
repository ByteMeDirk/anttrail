## Summary

<!-- What does this change do, and why? Link the issue it closes, for example "Closes #12". -->

## Pull request title

<!-- The title becomes the commit message on main. Use `type(scope): summary`, for example `fix(graph): skip symlink loops`. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change (changes the CLI, the graph schema, or the Python API)
- [ ] Documentation
- [ ] Build, CI, or dependencies
- [ ] Refactor with no change in behavior

## Checklist

- [ ] The pull request title follows Conventional Commits.
- [ ] I added or updated tests, including a regression test for a bug fix.
- [ ] `uv run ruff check .`, `uv run black --check .`, and `uv run pytest` pass locally.
- [ ] I updated `CHANGELOG.md` for any change a user would notice.
- [ ] I updated `docs/graph-format.md` and the README if the output or options changed.
- [ ] I described any breaking change in the summary above.

## Notes for the reviewer

<!-- Anything that needs a closer look, a decision, or follow-up work. Delete this section if it does not apply. -->
