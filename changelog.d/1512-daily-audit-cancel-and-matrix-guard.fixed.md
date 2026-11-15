- The SECDEP-01 workflow guard now rejects three committed shapes that could silence the daily
  main audit while `run: make security` stays unchanged (#1512):
  - a `cancel-in-progress` that is not false, at workflow or job level in
    `.github/workflows/security-audit.yml`, because a cancelled run leaves no audit status for
    its commit;
  - a `concurrency` value written wholly as one expression, at either level, because it can
    evaluate to a mapping that cancels an in-progress run;
  - any `strategy` on the audit job, because an empty matrix expands to zero jobs and GitHub
    reports them as skipped.
- Limit: the guard bounds only in-progress cancellation. GitHub still cancels a pending run
  when a newer run joins the same concurrency group, and no committed key prevents that. The
  SECDEP-01 text now says so, and also says that the guard does not bind any preceding
  workflow step, which can change the checkout, the toolchain or the GitHub runtime
  environment files.
- Ten negative controls in `tests/lint/test_security_gate_coverage.py` fail on the previous
  guard and pass now. `tests/lint/test_gwtf_canonical_source.py` pins the new SECDEP-01
  phrases. No workflow, Makefile recipe or finance behaviour changes.
