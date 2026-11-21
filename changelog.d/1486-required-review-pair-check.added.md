- **R2 and R3 pull requests need their independent review pair to be green (#1486).** Owner
  decision 2026-11-21: a new check, `Independent review (RECRUIT-01)`
  (`scripts/ci/check_pr_review_pair.py`, workflow `.github/workflows/pr-review-pair.yml`), reads
  the body's `Risk class:` line and, for R2 or R3, passes only when an accepting domain record
  and an accepting assurance record are on the pull request, each bound to its exact head, each
  with a matching stated SHA-256, and neither from a session that wrote a commit on it, and no
  counted reviewer's latest record at that head withholds acceptance (one veto blocks). A
  Dependabot pull request with no class line is read as R2; a `TRAIN-01` train needs one pair
  per car. It runs on `pull_request_target` from `main`'s workflow and script with no
  pull-request code executed, so a pull request cannot weaken the check that judges it, and is
  deferred on drafts. It cannot authenticate the session a record declares, so the coordinator
  still verifies independence. `MERGE-01`, `REVIEW-01`, `RECRUIT-01` module 3 (new §4.1, the record
  header), `AGENTS.md`, `Rules to follow.md` and the PR template name it. The owner's settings
  steps are to allow `pull_request_target` for this workflow in the Actions event policy
  (GitHub blocks it in public repositories from 2 December 2026) and to make the check required
  in the `main` ruleset. No KPI changes.
