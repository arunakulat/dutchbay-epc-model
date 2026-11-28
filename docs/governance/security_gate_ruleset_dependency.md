# Security Gate Tooling, Invocation Surface, and Ruleset Dependency (#1413)

This record documents the security gate's tooling pins, workflow invocation surface, and external
repository ruleset dependency for issue `#1413`.

## 1. Pinned Security Tooling

Both security-gate workflows — the daily `Lock Advisory Audit` job in
`.github/workflows/security-audit.yml` and the pull-request `Security Scan` job in
`.github/workflows/test-suite.yml` — install their analysers from the shared requirements file
`.github/requirements-security-tooling.txt`:

```text
-c ../requirements.txt
bandit==1.9.4
pip-audit==2.10.1
```

- Exact `==` pins match `requirements.txt` (`bandit==1.9.4`, `pip_audit==2.10.1`), so CI and local
  `make security` execute identical analyser versions.
- `-c ../requirements.txt` constrains transitive dependencies (`requests`, `urllib3`,
  `CacheControl`, etc.) to the locked environment.
- Unpinned `pip install bandit pip-audit` or range specifiers are rejected by
  `tests/lint/test_security_gate_coverage.py` and `tests/lint/test_security_gate_tooling_1413.py`.

## 2. Pinned CI Invocation Surface

Both workflows invoke `run: make security` as an exact single-line command:

- `make -i security` (which ignores non-zero exit codes) and
  `make security PIP_AUDIT_IGNORES=...` (which injects CLI-level allowlist overrides) are rejected
  by the workflow guards in `tests/lint/test_security_gate_coverage.py` and
  `tests/lint/test_security_gate_tooling_1413.py`.

## 3. Repository Ruleset `17414541` Dependency (Out-of-Tree Control)

Whether a red `Security Scan` blocks a merge and whether draft PRs are refused until checks pass
is governed outside the repository tree by GitHub repository ruleset `17414541`
(`"main branch protection"`). No in-tree test can enforce or observe GitHub ruleset state.

- **Indirect gate path:** `Security Scan` is not listed directly in ruleset `17414541`; it blocks
  merges through `Test Summary`'s `needs` dependency in `.github/workflows/test-suite.yml`.
- **Live ruleset verification (2026-11-27):** Queried via
  `gh api repos/arunakulat/dutchbay-epc-model/rulesets/17414541`:
  - `enforcement`: `active`
  - `strict_required_status_checks_policy`: `true`
  - `do_not_enforce_on_create`: `false`
  - Required status checks (all 5 bound to GitHub Actions, `integration_id: 15368`):
    1. `Test Summary` (`integration_id: 15368`)
    2. `fastlane` (`integration_id: 15368`)
    3. `smoke` (`integration_id: 15368`)
    4. `Verification receipts (VERIFY-01)` (`integration_id: 15368`)
    5. `Verification intake (INTAKE-01)` (`integration_id: 15368`)

Any future change to ruleset `17414541` (for example, unbinding `integration_id: 15368` or
dropping `Test Summary` from required checks) would weaken the draft-gate and merge-blocking
guarantees independently of the in-tree workflow files.
