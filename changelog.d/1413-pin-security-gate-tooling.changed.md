- **Pin security gate tooling, invocation surface, and ruleset dependency (#1413).** Verified
  that `.github/workflows/security-audit.yml` and `.github/workflows/test-suite.yml` install
  `bandit==1.9.4` and `pip-audit==2.10.1` via `.github/requirements-security-tooling.txt` with
  `-c ../requirements.txt` and invoke exact `make security`. Added
  `tests/lint/test_security_gate_tooling_1413.py` with positive and negative controls, and
  recorded the external repository ruleset `17414541` (`integration_id: 15368`) dependency in
  `docs/governance/security_gate_ruleset_dependency.md`.
