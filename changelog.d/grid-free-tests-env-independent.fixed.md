# changelog.d/grid-free-tests-env-independent.fixed.md
- **Grid-free tests made environment-independent** — six `tests/grid/*_grid_free.py`
  tests asserted optional-dependency-ABSENT behaviour (the CASPER `_require_*` guards and
  closed-form fallbacks) by relying on `pandapower` / `opendssdirect` / `andes` genuinely
  missing from the venv, so they failed in any dev environment with the `[grid]` extra
  installed (local `make test` red on a green `main` — the #859 local/CI-divergence class).
  Absence is now SIMULATED per-test with a poisoned `sys.modules` entry
  (`monkeypatch.setitem(sys.modules, "<lib>", None)`), which raises the same `ImportError`
  whether or not the library is installed. No engine code touched; KPI-neutral.
