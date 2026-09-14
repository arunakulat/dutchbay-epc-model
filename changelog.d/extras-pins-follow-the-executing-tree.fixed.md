- `app.ops.extras.declared_extras` now reads declared pins from whichever artifact governs
  the code that is actually *executing* -- the `pyproject.toml` beside the package when there
  is one, and the installed distribution's recorded metadata otherwise -- instead of metadata
  alone. `app/` is deliberately not a packaged directory, so the print core always loads from
  a checkout, and ENV-01 puts the active checkout first on `PYTHONPATH` so `analytics` and
  `finance` do too; one non-editable install in the shared governed venv was therefore serving
  eighteen worktrees at differing commits, reporting pins that described whichever checkout
  last built it. Observed on 2026-09-14: a build declaring `weasyprint<70,>=69` outlived
  #1256's `>=70,<71` bump, so reconciling the venv to the pinned 70.0 produced nine
  `DbplDependencyError` failures in `tests/app/test_dbpl.py` -- the guard rejecting the exact
  version the lock requires -- and a venv built by `./setup_venv.sh` alone, which installs no
  project distribution at all, made the `[report]` extra declare nothing and failed every DBPL
  PDF outright. Both are fixed without installing anything, so no build byproduct lands in a
  checkout and no single install has to be correct for every worktree. `ExtraStatus` gains a
  `spec_source` field (`pyproject` / `metadata` / `none`), surfaced on `/health/readiness`, so
  the provenance of a pin is recorded rather than inferred. Deployed behaviour is unchanged:
  in the image the editable install's source and `/app/pyproject.toml` are the same tree. CI
  never saw either failure, because it installs with `pip install -e`, whose metadata is
  rebuilt at every install. No runtime, financial formula, scenario or KPI change.
