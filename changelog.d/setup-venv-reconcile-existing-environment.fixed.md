- `./setup_venv.sh` now reconciles an already-provisioned environment against
  `requirements.txt` instead of only validating it. GWTF R21 step (2) is "create or
  reconcile", but the existing-environment branch installed nothing and the health
  contract checks that the governed distributions are *present*, not that they match
  the lock -- so a pin raised on `main` survived indefinitely in a shared local
  environment while the script still reported `Environment ready` and exited 0.
  Observed on 2026-09-14: weasyprint stayed at 69.0 for a day after #1256 raised it to
  70.0 for PYSEC-2026-3940, failing
  `tests/integration/test_report_jobs_tooling.py::test_governed_report_jobs_versions_are_installed`
  in every local worktree and leaving the advisory open locally; `scipy-stubs` and
  `websocket-client` had drifted too, silently, because no test asserts their versions.
  CI was never affected -- it installs fresh from the lock. No runtime, financial
  formula, scenario or KPI change.
