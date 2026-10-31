- **The required `Security Scan` is hardened against a stale, partial or one-sided advisory
  answer (#1464).** On 2026-10-27 the gate reported a lock pinning `hydra-core==1.3.7` clean
  minutes after the same workflow redded the same pin on `GHSA-wf6j-7hvr-gr93`, and on
  another run reported one of two live advisories (#1353 D-10). The cause is not
  established, and this change does not claim one. It removes known weaknesses instead.
  Neither job that runs `make security` restores pip's cache any more, which pip-audit's
  PyPI service reads by default. `make security` gained a third pass that asks OSV rather
  than PyPI, sharing the same allowlist. A new canary step,
  `scripts/ci/check_audit_canary.py`, fails the job unless every feed reports two known
  advisories before the gate's own verdict is trusted. `bandit` and `pip-audit` are
  installed from one pins file held to the lock, with their versions printed to the log.
  `tests/lint/test_security_gate_coverage.py` and `tests/lint/test_pip_audit_allowlist.py`
  hold all of it, with negative controls.
