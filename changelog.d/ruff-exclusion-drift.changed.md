# changelog.d/ruff-exclusion-drift.changed.md
- **Lint-gate exclusion-drift cleanup** — `ruff.toml` carried four phantom exclusions
  (`analytics/sensitivity_visualization.py` plus three long-deleted root files) and three
  stale ones. `analytics/fx`, `api` and `constants.py` are now INSIDE the gate: the bare
  `"api"` entry had also been shadow-excluding `app/api/` (ruff matches basenames), so
  findings were sitting unseen in both trees after the repo-wide bugbear fixes. Brought
  the newly-gated code up to standard: 8× `zip(..., strict=True)` in `analytics/fx`
  (equal length is an existing invariant — `FXHistorySeries.__post_init__` enforces it —
  so `strict=True` is a no-op assertion, per the #752 convention), 5× `raise … from exc`
  in `api/` (the #758 convention), 3× `Annotated[T, Depends(...)]` route dependencies in
  `app/api/jobs_router.py` (FastAPI-recommended; runtime-identical), and the
  `analytics/fx/__init__` module docstring moved above `from __future__` so it is a real
  docstring (`__doc__` was `None`). KPI-neutral; canon pins pass.
