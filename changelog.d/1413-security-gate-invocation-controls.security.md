- **The security gate's invocation has named controls for the two bypasses in #1413.** Both
  workflow guards in `tests/lint/test_security_gate_coverage.py` now carry negative controls
  for `make -i security`, `make --ignore-errors security` and
  `make security PIP_AUDIT_IGNORES=...`, which exact-equality on the gate step already refused
  but no test showed. The module docstring records what no in-tree test can pin: repository
  ruleset 17414541 decides whether a red gate blocks a merge, and on 2026-11-21 its
  `Test Summary`, `fastlane` and `smoke` checks were not bound to the GitHub Actions
  integration. Binding them is the owner's change. Tests only; no KPI changes.
