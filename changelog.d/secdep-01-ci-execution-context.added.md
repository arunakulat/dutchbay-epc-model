- **Bind both committed security gates to their declarative execution context.**
  `tests/lint/test_security_gate_coverage.py` now parses the main-branch audit and
  pull-request test workflows, requires exactly one `make security` step in each,
  and fails if workflow or job defaults, unexpected workflow/job/step environment,
  a job container, a runner other than `ubuntu-latest`, a job `needs`, or a step
  shell or working-directory override can skip, relocate, or interpose the
  unchanged command. A `needs` on a job that never runs skips the gate, and GitHub
  reports that as skipped rather than failed, which on the daily main audit would
  pass in silence. Each workflow has its own hostile controls, so the pull-request
  gate's guard is observed firing as well as the daily audit's. The existing
  fail-closed `if` and `continue-on-error` checks now share that helper.
  `SECDEP-01` names those two workflow runs as the authoritative gate receipts and
  keeps its limits for arbitrary local Make callers, an externally selected
  vulnerability service, runner-host state and a preceding step writing GitHub
  runtime environment files. Carries forward the change first proposed in #1446.
  No dependency, runtime, financial formula, model input, scenario, KPI, release,
  or HOLD changes.
