# Platform plan evaluation — implementation record and review recruitment

This is the `RECRUIT-01` record for pull request #1296: the writer's checkpoint receipt, the risk
classification, the reviewer capability profiles and the profile receipt, written before any
reviewer is dispatched (module 1 sections 2 and 5; module 2 section 4; module 3 section 2). The
frozen subject is listed in `docs/PLATFORM_PLAN_SUBJECT_MANIFEST.tsv`, committed with this record.

## 1. Task and risk classification

| Field | Value |
|---|---|
| Task | Record the owner-supplied platform development plan in the evidence corpus, evaluate it for Sprint 21, and persist the result (#1296) |
| Risk class | `R2_LOAD_BEARING`: data ingestion into the evidence corpus, a registration in a lint test that gates the corpus, a sprint planning record and a successor handover record |
| Why not `R3` | No finance or KPI behaviour, no lender- or Board-facing evidence, no grade or release logic, no security boundary and no production authority changes |
| Stricter controls that apply | `AGENTS.md` "Four ways a corpus commit goes wrong"; `DATA-01`; `DOC-03`; `VERIFY-01`; `PERSIST-01` |
| Reviewer roles triggered | One task-domain reviewer and one separate assurance reviewer (module 1, section 3) |
| Owner direction on review | "follow repo rules, harness, frameworks" (decision D5, 26 September 2026) |

## 2. Writer checkpoint receipt

| Field | Value |
|---|---|
| Coordinator | Claude Code cloud session `session_01Xmv5MBtYeqKTJvsJXphk6F` |
| Writer | The coordinator, as sole writer |
| Repository and worktree | `arunakulat/dutchbay-epc-model`, primary checkout `/home/user/dutchbay-epc-model` in an ephemeral cloud container; `git worktree list` showed no other worktree at start |
| Branch | `claude/laughing-mccarthy-wffp1k` (fixed by the cloud session) |
| Protected base and merge base | `b87ee32f8031a9b81b222c90020ed10af2c18131`, unchanged through every commit |
| Commits before this record | `46a21a55` corpus, evaluation and handover; `7458252f` evidence tightening; `bda9300b` owner decisions D1, D2, D4 and D5 |
| State | `CHECKPOINT_VERIFIED`, then `FROZEN` at the commit that adds this record |
| Environment | Python 3.12.3 from the checkout-local `.venv` provisioned by `.claude/hooks/session-start.sh`; full history and tags fetched |
| Active `HOLD` | The #1110 Board and lender `HOLD` is unaffected |

**Deviation, declared.** No writer lease record was issued before the patch. The coordinator ran the
start-of-task checks (`git status --short --branch`, `git worktree list`, branch verification
before every commit) but did not record a lease ID, allowlist or target hashes in advance, because
the review procedure was engaged only after the owner's decision D5. The lease is recorded here
retroactively as `PLATFORM-PLAN-W1`: its allowlist is exactly the changed paths of the subject
manifest, and it expires at this checkpoint. Any further change to a subject object needs a fresh
lease and restarts both substantive reviews (module 3, section 6).

Writer checks and exact results are the receipts table of #1296's body; the checks not run are
declared there. In summary: the corpus guard passed 34 tests and was observed to fail twice under
negative controls; the lint and docs suites passed except five sandbox tests that fail identically
on unmodified `main`; ruff, ruff format, black, isort and mypy were clean on the one changed Python
file; the area manifest verified under `sha256sum -c --strict`. The full suite and a financial
regression were not run locally.

## 3. Reviewer capability profiles

Both reviewers are distinct subagent instances, started cold, with no access to the writer's
context and no access to each other's disposition. Each runs in an isolated git worktree. Their
identities are the agent identifiers assigned at dispatch, recorded in their review records.

### 3.1 `R-DOM-1` — task-domain reviewer

| Field | Value |
|---|---|
| Role | Independent task-domain reviewer, read-only |
| Mission and deliverable | One structured review record (module 3, section 4) judging whether the evaluation's substantive claims are correct and fairly stated |
| Competencies required | Project-finance debt sizing and sculpting; DSCR and CFADS; tax, depreciation and interest limitation; FX and hedging; wind, solar, BESS and hydro resource modelling; Monte Carlo practice; audit-register semantics |
| Minimum method | An oracle for correction C1 that does not use the repository's sizing function; a sample of at least ten `path:line` claims checked against the candidate's code; the audit states in section 7 of the analysis re-read from the JSON registers; the plan file's fidelity invariants checked |
| Authorities not held | Merge, release, lender, Board, professional, publication, issue-closure and `HOLD`; any repository, pull request or issue mutation |

### 3.2 `R-ASR-1` — assurance reviewer

| Field | Value |
|---|---|
| Role | Independent assurance reviewer, read-only, separate from `R-DOM-1` |
| Mission and deliverable | One structured review record challenging contract boundaries, failure modes, verification quality, disclosure control, authority language and unintended scope |
| Competencies required | GWTF rule semantics; `RECRUIT-01`, `VERIFY-01`, `DATA-01` and `PERSIST-01`; manifest integrity and the corpus guard; disclosure control; `DOC-03`; the framework-expansion lint |
| Minimum method | Independent negative controls of the guard registration in a scratch copy, not the reviewer's worktree; `sha256sum -c` of the area manifest; the four corpus-commit failure modes checked; a sample of the pull request's receipts re-run; authority and `HOLD` language checked in every changed document |
| Authorities not held | As for `R-DOM-1` |

### 3.3 Common terms

- **Ingress, in authority order:** `AGENTS.md`; `CLAUDE.md`; the complete
  `go_with_the_flow_rules_v3_0_clean.csv`, including the unabridged `FRAMEWORK-01`, `FRAMEWORK-02`
  and `FRAMEWORK-03` rows; the four `RECRUIT-01` modules; the subject objects; the evidence code the
  analysis cites; the audit registers; the predecessor findings listed below. Each reviewer returns
  an ingress receipt naming paths read, the commit, and sources not read (module 4, section 3).
- **Mutation state:** read-only. No file, index, ref, branch, worktree, pull request or issue
  mutation. Scratch work only under `/tmp`, outside every worktree.
- **Stop conditions:** a candidate commit or tree that differs from the frozen values returns
  `BLOCKED_WITH_RECEIPT`; incomplete ingress returns `NO_EVIDENCE`.
- **Output and persistence:** the reviewer's final message is its complete record. The coordinator
  persists it verbatim as `docs/PLATFORM_PLAN_DOMAIN_REVIEW_001.md` or
  `docs/PLATFORM_PLAN_ASSURANCE_REVIEW_001.md` in a documentation-only receipt commit.
- **Findings:** each finding takes one ledger state from module 3, section 5. One veto blocks.

## 4. Applicable predecessor findings

| ID | Source | What recurred before |
|---|---|---|
| PF-1 | `AGENTS.md`, "Four ways" item 1; #1211, #1234 | Stale parent pin; incomplete manifest; an entry for a path git cannot hold |
| PF-2 | `AGENTS.md`, "Four ways" item 2 | A "manifest only" claim contradicted by quoted restricted content |
| PF-3 | `AGENTS.md`, "Four ways" item 3 | A review record re-publishing what a fix removed |
| PF-4 | `AGENTS.md`, "Four ways" item 4; `docs/NSO_OFFER_RESUPPLY_DOCUMENTATION_REVIEW_RECORD_2026-09-04.md` | One handling statement written in several places and disagreeing; a false receipts table |
| PF-5 | #1283, #1286; `tests/lint/test_framework_expansions_match_csv.py` | Invented expansions of the framework acronyms |
| PF-6 | #1292 | A reviewer's acceptance asserted without a record |
| PF-7 | #1232 | Load-bearing work merged on green CI without its review chain |

## 5. Profile receipt

Task and risk class: section 1. Coordinator and writer state: section 2. Reviewers: `R-DOM-1` and
`R-ASR-1`, section 3. Source hierarchy: section 3.3. Worktree and base: section 2; each reviewer
works in its own isolated worktree at the frozen candidate. Allowlist: the writer's is the subject
manifest's changed paths; the reviewers' is read-only. Acceptance criteria: both reviewers return
`ACCEPT` bound to the frozen subject manifest, with no finding left in
`BLOCKS_CURRENT_CANDIDATE`, then rebind to the final delivery head. Authority exclusions: no
reviewer, check or merge confers grade, release, audit, lender, Board, publication, issue-closure
or `HOLD` authority.
