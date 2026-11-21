- **R2 and R3 pull requests need their independent review pair to be green (#1486).** Owner
  decision 2026-11-21: a new check, `Independent review (RECRUIT-01)`
  (`scripts/ci/check_pr_review_pair.py`, workflow `.github/workflows/pr-review-pair.yml`), reads
  the body's `Risk class:` line and, for R2 or R3, passes only when an accepting domain record
  and an accepting assurance record are on the pull request, each bound to its exact head, each
  with a matching stated SHA-256, and neither from a session that wrote a commit on it. It runs
  from the base commit, so a pull request cannot weaken the check that judges it, and is
  deferred on drafts. `MERGE-01`, `REVIEW-01`, `RECRUIT-01` module 3 (new §4.1, the record
  header), `AGENTS.md`, `Rules to follow.md` and the PR template name it. Making it a required
  check in the `main` ruleset is the owner's settings step. No KPI changes.
