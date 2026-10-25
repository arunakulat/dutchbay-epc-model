- **Two blind spots in the dependency audit, both measured before being fixed.** First,
  `make security` audited 310 of the lock's 312 pins. `pip-audit -r requirements.txt` resolves
  the file in a temporary virtual environment, but `VirtualEnv.post_setup` runs
  `pip install --upgrade pip wheel setuptools` in that environment before the resolve, landing
  `packaging` and `wheel` at exactly the versions this lock pins; pip then reports neither as
  to-install and pip-audit audited neither. `packaging==26.3` and `wheel==0.48.0` were
  unaudited lock pins, and the omission was version-coincidental — it would appear and
  disappear as upstream moved, announced by nothing. `security` now also runs
  `pip-audit --no-deps --disable-pip -r requirements.txt`, pip-audit's pre-resolved path,
  which audits all 312 in under a second; both passes share one `PIP_AUDIT_IGNORES`, so a
  suppression cannot hold in one mode and not the other. A new `audit-declared` target offers
  that pass alone as a fast local pre-flight. `audit` is deliberately left as the single
  unflagged resolve-mode command, because that is the canonical spelling of the effective
  suppression set that #1386's proposed `SECDEP-01` fence reads through `make -n audit`.
  Resolve mode is kept, not replaced: it is the only pass that sees a package the lock does
  not pin, which is how `cloudpickle` was audited before #1387 pinned it. Still out of scope
  in both passes and now stated rather than implied: `pip` itself, which the lock deliberately
  leaves unpinned; tracked as a residual on #1353.
- **Second, nothing reported `main`'s own audit state between Mondays.** `Security Scan` runs
  on `pull_request` and on `test-suite.yml`'s weekly Monday schedule, never on a push to
  `main`. The last scheduled run before 2026-10-25 was Monday 2026-10-19 (run 39226566738,
  `8c4d0761`, success); seven advisories landed against the unchanged lock on 2026-10-23/24
  and the next run was not due until Monday 2026-10-26. Because the gate audits the whole lock
  rather than the diff, the only signal was every open pull request reddening at once, arriving
  as though it were somebody's change. A new `Security Audit` workflow runs the same
  `make security` daily, on pushes to `main` and on manual dispatch. It is bandit plus
  pip-audit with no project install, so it costs a couple of minutes rather than the ~63 of
  the sharded suite whose own `push: main` trigger was dropped as duplication, and it is
  deliberately not triggered on `pull_request`, where `Security Scan` already gates every
  change. `tests/lint/test_security_gate_coverage.py` pins both remedies — both passes, the
  shared allowlist, the untouched `audit` alias, the daily cadence, and the equality between
  what `main` audits and what the merge gate audits — with a negative control per assertion
  plus two hermetic pip-audit oracles proving the flags select the pre-resolved path and that
  the venv prologue is still the reason resolve mode skipped those pins. The workflow half
  also rejects the shapes that honour the triggers and neuter the run: an `if:` on the
  `make security` job or step, which would silence the daily cadence, and
  `continue-on-error`, which would let a red audit report success on `main`. No runtime, financial
  formula, scenario or KPI change.
