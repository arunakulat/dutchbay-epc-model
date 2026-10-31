# Agent session routing

This note tells a session where to look. It covers local Codex, Claude Code and any other agent
host. It restates no rule. Every rule it names lives in `go_with_the_flow_rules_v3_0_clean.csv`
or in a file a rule there names as canonical. Where this note and a source disagree, the source
wins and this note is stale. Correct it, don't follow it.

## Authority

This note grants no merge, review, lease or approval authority to any session.

- `MERGE-01` says *when* a green pull request may merge. `REVIEW-01` names the merge coordinator
  as the party that merges. Reading this note does not make a session the merge coordinator.
- The coordinator recruits each worker to a written profile, and that profile names the
  authorities the worker does not hold, merge among them, unless they are separately and
  explicitly granted (`RECRUIT-01` module 1 §2,
  `docs/governance/recruit_01/01_capability_and_risk.md`). One delivery coordinator holds lease
  authority (module 2 §1).
- Required reviewers must be distinct from the writer, from the coordinator and from each other
  (module 3 §1, `docs/governance/recruit_01/03_independent_review_and_attestation.md`).
- Every session posts under the same login. The steward skill
  (`.claude/skills/steward/SKILL.md`) says how a record is attributed to the session that wrote it.
- `AGENTS.md` "Authority and scope" states how user instructions, the canonical CSV and the
  gateway rank. `RECRUIT-01` treats prior statements as claims to verify. `AGENTS.md` "Session
  continuity" says a handover loses to the CSV and `AGENTS.md`.

## Start of a session, by host

| Host | Read |
|---|---|
| Local Codex on the owner's Mac | `AGENTS.md` "Required Codex task origin and Python runtime" (`THREAD-01`, `ENV-01`) |
| Claude Code in a cloud container | `CLAUDE.md` "What changes in a cloud session" |
| Any other host | `AGENTS.md` in full, then the notes below |

Notes for a host this table does not name:

- A session with no checkout cannot run `dutchbay_bootstrap_rules.py`, `tests/lint` or the two
  checkers under `scripts/ci/`. Its receipts say so as `not run - <reason>` (`VERIFY-01`).
  It does not claim Mac, worktree or environment verification it did not perform.
- A writer lease needs the worktree and environment preflight in `RECRUIT-01` module 2 §2
  (`docs/governance/recruit_01/02_writer_lease_and_recovery.md`). A session that edits only
  through the GitHub file API cannot complete that preflight.
- Before pushing a file written through an API, diff the whole file against its base. On
  #1498's branch a file-API write replaced `go_with_the_flow_rules_v3_0_clean.csv` with a
  placeholder for five commits before a later commit restored it.
- On a draft pull request the test shards and the Coverage Gate report success without running
  (`REVIEW-01`). They are not test evidence on a draft head.

## Before the first edit

`INTAKE-01` and `AGENTS.md` "Start every task safely" give the order. `scripts/ci/check_pr_intake.py`
compares creation times: for a human or agent pull request, the work record must exist before the
pull request does. A record posted afterwards cannot clear it.

## Rules and formats

`CLAUDE.md` "Rules and formats that govern this repository" lists the formats the repository checks
or relies on: receipts (`VERIFY-01`), commits (`R18`), changelog fragments, handover records
(`PERSIST-01`), review records (`RECRUIT-01`), the evidence corpus (`DATA-01`) and PDFs (`DBPL-01`).
They apply on every host. Cite the framework principles by ID (`FRAMEWORK-01`, `FRAMEWORK-02`,
`FRAMEWORK-03`) and read their meanings in the CSV.

`tests/lint/test_agent_session_routing.py` checks that every rule ID and repository path this note
cites still exists and that the authority line above is present.
