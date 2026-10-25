- **`REVIEW-01`: review comes before the full suite, and the lane count follows the risk** — a
  new canonical rule in `go_with_the_flow_rules_v3_0_clean.csv`, on the project owner's decision
  of 2026-10-25. A writer opens the pull request as a draft, freezes the head and posts one
  `Evidence pack` comment; the review lanes bind to that draft head; only then is it marked ready
  for review, so the full sharded suite runs once. A subject change after review still restarts
  both reviews (`RECRUIT-01` module 3 §6), and `MERGE-01`'s green is unchanged.
- **One review lane for three bounded low-risk classes** — `RECRUIT-01` module 1 gains §3.1:
  presentation-only code, test-only guard tightening, and record corrections are `R1_ROUTINE`
  and take one lane. Dependency bumps, CI and merge gates, governance, contracts, schemas,
  oracle-defining tests, security, data ingestion, finance and KPI behaviour and
  writer-authorizing handovers stay `R2` or higher; a mixed change takes its highest class, and
  when unsure the class is `R2`. `AGENTS.md`, the steward skill and `RECRUIT-01`'s own lane
  statement route to it, and `tests/lint/test_review_first_policy.py` pins every control with a
  negative control per control.
- The `test-suite.yml` gate that defers the sharded suite on draft pull requests is **not** in
  this change. It follows once #1386 settles that workflow, and the rule says `AUTOMATION
  PENDING` until then.
