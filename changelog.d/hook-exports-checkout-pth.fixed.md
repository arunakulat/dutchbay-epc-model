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
contract permits. The file holds one path on one line and is written on every
session start -- including a warm start, where the matching manifest stamp skips the
dependency install -- and rewritten rather than appended, so it cannot accumulate
entries and a moved checkout self-corrects.

One consequence is worth stating plainly: a virtual environment that one checkout's
hook has stamped is now refused for any *other* checkout. `validate_environment`
raises on a non-empty `foreign_checkout_paths`, so a second checkout pointed at the
first's `.venv` — through `DUTCHBAY_VENV`, say — now fails the contract with
`path-contaminated by another DutchBay checkout` where it previously passed. That is
the contract working as intended, because the `.pth` really would make the second
checkout import the first's code. The hook itself never shares an environment: it
selects `$REPO/.venv` only and rewrites the `.pth` on every start, so any checkout
that runs the hook corrects the file to name itself.
