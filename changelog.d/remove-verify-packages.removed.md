- **Removed the dead `VERIFY_PACKAGES.sh` script.** It was a December-2025 "Phase 1-2"
  verification artifact that sourced the nonexistent `.venv311` and checked five
  modules/tests that no longer exist (`finance/tax_profile.py`, `finance/wacc_integration.py`,
  `finance/debt/__init__.py`, `finance/core/epc_helper.py`, `tests/test_phase_1_2_refactoring.py`),
  so it could not run. It is unreferenced anywhere in the repo and is superseded by `make test`
  and `check_venv.sh`.
