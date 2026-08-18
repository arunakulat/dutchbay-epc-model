- **Python 3.12 is now the baseline — this unblocks #923** — `requires-python` moves to
  `>=3.12` and the lock is regenerated on 3.12 with `scipy==1.18.0` / `scipy-stubs==1.18.0.1`.
  The driver is the D6b self-curtailment finance wiring: the moment
  `grid.qsts.finance_wiring.enabled` is flipped, `cashflow_v14_params` stops short-circuiting
  and pandapower becomes a **runtime dependency of the canonical path**. On 3.11 that was
  impossible to satisfy — `pandapower==3.3.0` requires `scipy~=1.15` and 3.5.4 requires
  `scipy<1.17` there, while the lock pinned `scipy==1.17.1` and `[dev]`'s `scipy-stubs`
  required `>=1.17.1`, so installing grid alongside the gate toolchain silently downgraded
  scipy off the lock **and** broke mypy's stubs. On 3.12 pandapower 3.5.x wants `scipy~=1.18`
  and all three resolve together cleanly.
- **`[grid]` is now IN the lock and composed into `[feasibility]`** — `pandapower` moves off
  the exact `==3.3.0` pin to an abstract `>=3.5,<4` floor (pyproject is the abstract source;
  the lock carries the exact pin), and `andes` / `opendssdirect` join it. `tests/grid/` goes
  from **576 passed / 19 skipped to 595 passed / 0 skipped** — every grid test now runs,
  including the andes dynamics and OpenDSS legs that had never executed in CI. The reproduce
  kit's `run_all.sh` step 7 (grid screen) no longer skips, and `[feasibility]` is once again a
  single install covering the whole kit.
- **KPI-neutral, verified** — the canon reproduces within the oracle gate under 3.12 /
  scipy 1.18. Observed drift is 1–2 ULP (`equity_irr` ~6e-16 relative, `total_cfads_usd`
  ~2e-16), roughly seven orders of magnitude inside the `pytest.approx(abs=1e-9 / rel=1e-9)`
  tolerances the canon test asserts, so **no oracle re-baseline is required**. The full suite
  passes on the regenerated lock.
- **Toolchain and CI follow the baseline** — `black`/`ruff` `target-version` to `py312`,
  `mypy` `python_version` to 3.12 (both `mypy.ini` and `[tool.mypy]`), the Dockerfile to
  `python:3.12-slim-bookworm`, `.pre-commit-config.yaml` `language_version` to `python3.12`,
  and `setup_venv.sh` + the SessionStart hook now prefer `python3.12`. The test-suite matrix
  collapses from the per-event 3.11/3.12 split (#959) to a single 3.12 leg, since 3.11 is no
  longer a supported target; the stale matrix commentary is rewritten to match, with a note on
  how to restore a second leg if a future floor/ceiling pair needs gating.
- **Still user-gated: this unblocks the #923 flag, it does not flip it.** Enabling
  `grid.qsts.finance_wiring.enabled` remains a separate, KPI-moving decision requiring a real
  feeder QSTS run, a `kpi_oracle` before/after diff and explicit sign-off (measured impact at
  8% self-curtailment: projIRR −1.01pp, eqIRR −1.64pp, min_dscr −0.0092).
