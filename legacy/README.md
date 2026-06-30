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
- `stress_tests_v14.py` — the `StressTestEngine` (interest-rate / market-downturn /
  inflation stress scenarios). **Built but never wired** into any CLI, pipeline, report, or
  app; quarantined here from `analytics/` in #473 (MC-2/3) so the production tree honestly
  reflects what runs. Still exercised by `tests/legacy/test_stress_tests_v14.py` so it keeps
  working if reactivated, but excluded from the analytics coverage gate. Its `var_95_usd` /
  `cvar_95_usd` fields are **deterministic stress losses, not statistical VaR/CVaR** (MC-4) —
  real tail risk lives in `analytics/core/risk_metrics` + `analytics/sensitivity/tail_risk`.
  To reactivate: wire it into a Hydra CLI + the report and route NPV/IRR through the
  `evaluate_with_overrides` gateway (dropping the direct `finance.irr` import).
