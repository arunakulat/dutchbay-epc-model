- **`VERIFY-01` (GWTF rule 72, new *Verification* category)** — a claimed check without a
  receipt is not a check. Verification claims carry the command and its result; a check that
  was **not** run is declared as `not run — <reason>` rather than left silent. The rule
  generalises `TEST-03`/`TEST-04`/`TEST-05` and the audit reproduction registers and carries
  an explicit yield clause: where it appears to conflict with any of them, the *specific*
  rule wins, keeping `TEST-05` undiluted.
- **`PR Receipts` CI check** — `.github/workflows/pr-receipts.yml` +
  `scripts/ci/check_pr_receipts.py` fail a pull request whose receipts table is absent,
  empty, or carries a silent Result cell; a declared `not run — <reason>` passes and bot
  authors are exempt. The pull-request body is passed through the environment, never
  interpolated into `run:`, and that is pinned by test. Promoting the job to a *required*
  status check is a repository-ruleset setting and remains an owner decision.
