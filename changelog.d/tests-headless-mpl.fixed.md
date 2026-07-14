# changelog.d/tests-headless-mpl.fixed.md
- **Test suite pinned to the headless matplotlib backend** — `tests/conftest.py` now
  forces `Agg` (env + `matplotlib.use`) before any test can import pyplot. Chart-emitting
  tests (e.g. the capital-risk NPV-distribution PNG) previously instantiated the platform
  GUI backend on developer machines; on macOS the `macosx` backend hard-segfaulted the
  pytest process (exit 139) in sandboxed/SSH shells with no window server. Linux CI was
  never affected (no `DISPLAY` → Agg fallback), so this makes local runs match CI.
  Test-infra only; KPI-neutral.
