# `legacy/` — archived, non-live artifacts

Obsolete code, one-off scripts, and historical snapshots are isolated here (GWTF R12)
so the active tree (`finance/`, `analytics/`, `wind_resource/`, `solar_resource/`,
`api/`, `app/`, the canonical `scripts/` tooling) stays clean. Nothing under `legacy/`
is on a live execution path, in CI, or in the coverage gate.

- `dev_scripts/` — one-off developer/operations shell scripts and notes from earlier
  sprints (fix/cleanup/phase/rollback/deploy/sprint-validation helpers, plus the stray
  "make clean zip" instructions). Verified to be referenced by no workflow, Makefile,
  `pyproject.toml`, or doc before archiving (#490, QUAL-7/8). Retained for history; do
  not wire them back onto a live path.
- `sprint_snapshots/` — dated sprint-completion / regression-suite snapshot docs that
  describe the state at a past sprint and have drifted from live state (#490, QUAL-10).
  Kept as a historical record, not as current documentation.
