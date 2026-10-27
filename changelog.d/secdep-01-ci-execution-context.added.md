- **Bind both committed security gates to their declarative execution context.**
  `tests/lint/test_security_gate_coverage.py` now parses the main-branch audit and
  pull-request test workflows, requires exactly one `make security` step in each,
  and fails if workflow or job defaults, unexpected workflow/job/step environment,
  a job container, or a step shell or working-directory override can skip,
  relocate, or interpose the unchanged command. Hostile mutations prove every new
  assertion fires. The existing fail-closed `if` and `continue-on-error` checks now
  share that helper, so they bind the pull-request gate as well as the daily audit.
  `SECDEP-01` now names those two workflow runs as the authoritative gate receipts
  while retaining its limits for arbitrary local Make callers and an externally
  selected vulnerability service. The contract also states that declarative-key
  checks do not prove runner-host state or prevent a preceding step from writing
  GitHub runtime environment files. No dependency, runtime, financial formula,
  model input, scenario, KPI, release, or HOLD changes.
