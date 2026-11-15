- The SECDEP-01 workflow guard now rejects three committed shapes that could silence the daily
  main audit while `run: make security` stays unchanged (#1512):
  - a `cancel-in-progress` that is not false, at workflow or job level in
    `.github/workflows/security-audit.yml`, because a cancelled run leaves no audit status for
    its commit;
  - a `concurrency` value written wholly as one expression, at either level, because it can
    evaluate to a mapping that cancels an in-progress run;
  - any `strategy` on the audit job, because an empty matrix expands to zero jobs and GitHub
    reports them as skipped.
- Limits: the guard bounds only this workflow's own in-progress cancellation. Concurrency
  groups are repository-wide and case-insensitive, so another workflow or job that joins the
  audit's group with `cancel-in-progress: true` could still cancel an in-progress audit; no
  committed group collides today. GitHub also still cancels a pending run when a newer run
  joins the same concurrency group (the default `queue: single` keeps at most one pending
  run; `queue: max` keeps up to 100, and the guard requires neither). The
  SECDEP-01 text now says so, and also says that the guard does not bind any preceding
  workflow step, which can change the checkout, the toolchain or the GitHub runtime
  environment files.
- Twelve negative controls in `tests/lint/test_security_gate_coverage.py` fail on the previous
  guard and pass now. `tests/lint/test_gwtf_canonical_source.py` pins the new SECDEP-01
  phrases. No workflow, Makefile recipe or finance behaviour changes.
