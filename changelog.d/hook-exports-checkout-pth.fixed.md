The cloud SessionStart hook now writes a path-only `dutchbay-checkout.pth` into the
selected environment's `site-packages`, naming the active checkout, so the project
imports from any working directory rather than only from the repository root.

Before this, the hook's `PYTHONPATH` export was written to `CLAUDE_ENV_FILE`, which
only the harness sets. The manual invocation documented in `CLAUDE.md` sets no env
file, and a hook is a subprocess that cannot export into the shell that started it,
so a hand-run hook left `import analytics` working only from the checkout root. That
was a regression against the earlier hook, which had made the project importable
everywhere as a side effect of the `pip install -e` that #1376 correctly removed.

The `.pth` is not an installation and does not reinstate one: it writes no
`dist-info`, no `direct_url.json` and no checkout `egg-info`, so the environment
contract still reports `editable_project_install` false and `project_install_url`
null. `dutchbay_environment.py` collects a `.pth` into `foreign_checkout_paths` only
when the path names a *different* checkout, so naming the active one is what the
contract permits. The file holds one path on one line and is rewritten, never
appended, so it cannot accumulate entries and a moved checkout self-corrects.
