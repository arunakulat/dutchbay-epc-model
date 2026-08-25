- **`VERIFY-01` fails closed — PR Receipts is a required status check** (#1139) — the rule
  text, the workflow header and `docs/AGENTIC_DELIVERY_PRACTICE.md` §5.6 all previously
  recorded the promotion as an outstanding owner decision, and all three now record that it
  is done: a pull request without receipts cannot merge to `main`. `VERIFY-01` therefore has
  the same fail-closed character as `TEST-05` rather than being enforced by a visible failing
  check plus review. The ruleset matches the job's rendered name, pinned by
  `tests/lint/test_pr_receipts_policy.py`, so a rename cannot silently stop the check
  reporting and block every merge. Bot authors are exempted inside the checker rather than by
  a job-level condition, so the job still reports and dependency bumps are unaffected. The
  limit is unchanged and still stated: the gate checks that a Result cell *says* something,
  never that it is *true*.
