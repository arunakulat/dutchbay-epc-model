- **`VERIFY-01` is safe to promote to a required status check, and honest about what it
  proves** — two changes ahead of the #1139 ruleset decision. (1) The job name
  `Verification receipts (VERIFY-01)` is now pinned by
  `tests/lint/test_pr_receipts_policy.py`. A branch ruleset matches a required check by the
  job's rendered name, stored as a plain string; nothing asserted that string, so renaming
  the job would have made the required check stop reporting and blocked **every** merge to
  `main` until an admin edited the ruleset — silent at review time, discovered in
  production. The pin also asserts the workflow name (`PR Receipts`) is *not* that string,
  since requiring the workflow name matches nothing and enforces nothing, silently.
  (2) The gate's real limit is now stated where contributors meet it — the rule text, the
  workflow header and the PR template all record that it checks whether a Result cell
  **says** something, not whether it is **true**. A table of plausible but stale numbers
  passes; green means "nothing was left silent", never "the checks were verified". This is
  not a hypothetical: #1128 passed the gate carrying two figures measured before its own
  merge. Disclosure is what the gate buys, and silence is the failure that cannot be caught
  downstream.
