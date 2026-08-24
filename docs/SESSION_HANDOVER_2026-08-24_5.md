# Session handover — 2026-08-24, successor 5

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-24_4.md`](SESSION_HANDOVER_2026-08-24_4.md).
The predecessor remains authoritative for its historical receipts except where this
record updates live state.

## 1. Live repository, environment and coordination state

**Protected main at this cutoff:**
`e788fe3b40bf0ffd3bcc3d40043bb94cfa6de5f4`.

**Active worktree:**
`/Users/aruna/Downloads/dutchbay-wt-1110-gate-ledger`.

**Active branch:** `codex/1110-remediation-gate-ledger`.

**Branch base:** exact `origin/main` at
`e788fe3b40bf0ffd3bcc3d40043bb94cfa6de5f4`.

At this authored cutoff the 23-gate candidate is uncommitted, unpushed and not a pull
request or merged result. Check live Git and GitHub state before continuing; do not
promote this capture-time statement into a permanent conclusion.

The only permitted local Python remains
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, verified as Python 3.12.13.
`check_venv.sh --no-bootstrap` passes with imports resolving from this worktree, and
`dutchbay_bootstrap_rules.py` loads all 72 active GWTF v3.0 rules. No checkout-local
environment was created.

This Codex task remains rooted at `/Users/aruna/Downloads`, so the built-in post-PR
monitor is blind under ENV-01. Use explicit repository context for GitHub operations
and the active worktree first on `PYTHONPATH`.

The pre-edit conflict audit found:

- only the present Codex task active; the other relevant DutchBay task was idle and
  had completed its F5-02 verification/count-inventory work;
- one clean repository worktree on `main`, followed by creation of this dedicated
  worktree and branch;
- no existing `codex/1110-remediation-gate-ledger` branch or path;
- six open dependency pull requests (#1128 and #1064-#1068), touching only
  `requirements.txt` and/or `constraints.txt`; and
- issue #1110 OPEN with all 23 source checkboxes unchecked.

Recheck this mutable coordination surface before commit, push and merge.

## 2. Architecture control predecessor is merged but execution remains open

The 56-row architecture plan from successor 4 was squash-merged through protected PR
[#1151](https://github.com/arunakulat/dutchbay-epc-model/pull/1151) as
`e788fe3b40bf0ffd3bcc3d40043bb94cfa6de5f4`, from exact reviewed head
`b3d727ac8ff0ecb858f29654fac17e7777942289`.

The reviewed feature and merged trees were equal at
`3e1309f84d81af0123abbcdce061f574d4fab4fd`. Exact-head CI recorded 17 successes
and three declared scope skips. Post-merge focused validation passed and the feature
worktree and branches were retired.

Issue #1110 was automatically closed at merge because GitHub interpreted a negated
closing-keyword phrase in the PR body. The body was corrected and the issue was
reopened at `2026-08-24T11:29:43Z`. Future pull-request prose must say that issue
#1110 remains OPEN without placing a GitHub closing keyword immediately before the
issue number.

PR #1151 publishes an immutable plan only: all 56 architecture examinations remain
pending, unreviewed and result-hash-free. It does not complete the architecture gate
or lift HOLD.

## 3. Active dolphin — immutable 23-gate programme plan

The current dolphin turns the authoritative issue #1110 queue into a portable,
machine-validated pre-execution control surface. The source is a byte-preserved
snapshot of the OPEN issue body at GitHub `updated_at=2026-08-24T11:29:43Z`:

`docs/audit/2026-08-controlled-successor/registers/history/`
`github_issue_1110.remediation_and_release_gates.20260824.9f7348f7.md`

- snapshot-file SHA-256:
  `cf8d4709e4939589284a57dbda8cc0e6249da0abb28b5a10f9eda8e4d735bd02`;
- exact issue-body bytes: 5,371;
- exact issue-body SHA-256:
  `9f7348f7a5c56f8aff45a5074e323d96abda418567f8cfd0eefb16f43855e0b9`;
- source checkboxes: 23 total, zero checked, 23 unchecked.

The live issue remains authoritative for subsequent state. The snapshot prevents a
future live GitHub edit from silently changing the meaning or denominator of this v1
plan.

`programme_gate_plan.v1.json` maps the exact source population to 11 strictly ordered
execution stages. Each row carries stable ID, source ordinal/section, owner,
independent reviewer role, initial evidence-state classification, known prerequisite
artifacts, dependencies, evidence requirements, completion criteria, one negative
control and limitations. The schema cannot carry completion, reviewer identity,
result hash or closure authority.

The deterministic JSON/CSV descendants retain all 23 rows as:

- source checkbox `unchecked`;
- gate status `pending`;
- independent reviewer identity null;
- completion artifact/hash null;
- `closure_authorized=false`;
- `blocks_board_lender_release`; and
- release status `HOLD`.

F5-01 is L01. F5-02 is intentionally two distinct gates: P06 obtains authenticated
lender/legal transaction evidence; L03 may decide treatment only after P06. Synthetic
term sheets, ERA5 placeholders, synthetic QSTS, compile-only output and software-path
success cannot satisfy either F5-02 gate.

R07 is the independent RELEASED-or-HOLD decision. P09 consolidates the versioned
corrigendum/release pack after that decision. R08 is the only closure-action gate and
depends on both R07 and P09. V1 authorises no closure.

## 4. Candidate identities at this cutoff

| Artifact | SHA-256 |
|---|---|
| frozen issue snapshot | `cf8d4709e4939589284a57dbda8cc0e6249da0abb28b5a10f9eda8e4d735bd02` |
| `registers/programme_gate_plan.v1.json` | `6a2fc2a0616fa6298446198d1c273a8e929e56d1f2f52c2947efd568bb13f3ff` |
| `registers/programme_gate_ledger.v1.json` | `8ecc509fe4b63b13e41a2c27ee9c4bcfacd404a1d967c349c4138d27e573a1df` |
| `registers/programme_gate_ledger.v1.csv` | `b45cc71580bb0956b38bf44cfbfcdb34c6aac3186ca525076e4c364afb90b79c` |
| gate builder | `c295fb038c87c7c89c06aa7f5e3a9339bbe4cad3239176e724d63a9dc7faf486` |
| pack validator | `eb5f2b65d07b32a88b82d4bca677283a25d148f4659d1191ecb6584b5fa0c29d` |
| focused audit-pack tests | `5ff50ce0386ef8a3c4c8c05b907bd6c7960ebb6550fb6ca55ef1903de67ef764` |
| 67-entry publication manifest | `260c70f562109289afaf551de6c3ca0cb8752a17de21b69bf7d18d8733eada99` |

These hashes are candidate identities, not remote or merged identities. Recompute after
any correction and before delivery.

## 5. Local validation at this authored cutoff

All valid commands used the governed persistent Python 3.12 environment with this
worktree first on `PYTHONPATH` and bytecode disabled.

- deterministic gate builder: PASS; 23 records, 23 pending, zero completion hashes,
  zero closure-authorized, release HOLD;
- exact live-body comparison at capture and the later conflict refresh: PASS; state
  OPEN, `updated_at` unchanged and the 5,371-byte body hash equal to the frozen source;
- 30 unique known-artifact references: 30/30 exist in Git at pinned cutoff
  `e788fe3b40bf0ffd3bcc3d40043bb94cfa6de5f4`;
- repository-safe pack validator: PASS/HOLD with 67 manifest entries, 23 pending
  programme gates, 56 pending architecture examinations, 111 findings, 42 sources, 72
  architecture pointers and 34 reproductions;
- complete focused audit-pack tests: 25 passed, one known Hypothesis warning;
- complete `tests/lint`: 346 passed, one known Hypothesis warning;
- cross-layer GWTF/CASPER/CESSPIT/CCCDIR, compatibility, provenance, API/report,
  finance, grid and integration slice: 468 passed, one expected skip and three SWIG
  deprecation warnings;
- exact OpenDSS test that crashed under xdist: one passed serially;
- complete `tests/grid`: 875 passed serially, one known Hypothesis warning;
- Ruff repository-wide: PASS;
- Black repository-wide: 705 files unchanged;
- isort repository-wide: PASS, four configured skips;
- strict CI library/application mypy: 255 source files PASS;
- relaxed real-error scripts mypy: 63 source files PASS;
- focused strict mypy over the builder and validator: PASS;
- `pip check`: PASS;
- Bandit over the new and changed pack scripts: 1,024 lines, no issues;
- repository engine/application Bandit scan: 71,845 lines, no Medium or High issue;
- pinned `pip-audit -r requirements.txt`: no known vulnerabilities;
- changed-file pre-commit: Black, Ruff, isort, large-file, AST, EOF, whitespace,
  conflict, debug and protected-branch controls PASS; and
- `git diff --check`: PASS.

One ordinary full xdist/coverage attempt is **not a valid green receipt**. At 53%, a
macOS xdist worker segfaulted while importing `dss_python_backend` for
`tests/grid/test_curtailment_qsts_dynamics.py`; pytest replaced the worker and
eventually reported 5,942 passed, 18 skips, one crashed test and 91% incomplete
coverage because that worker returned no coverage data. The exact test and all 875
grid tests then passed serially in fresh processes. Treat the xdist run as an isolated
native concurrency diagnostic, not a test assertion failure and not a coverage PASS.
Protected GitHub CI on the exact pull-request head remains the complete-suite and
coverage merge authority.

## 6. Release and evidence boundary

The correct current posture remains:

- issue #1110: OPEN;
- programme gates: 0 of 23 completed;
- architecture examinations: 0 of 56 completed;
- F5-01: separate current-main reconciliation remains required;
- F5-02: external transaction evidence remains absent;
- wind resource: no on-site mast/MCP evidence and no bankable resource claim;
- release status: HOLD;
- Board/lender synthesis: do not regenerate yet.

The separate GWTF population-correction inventory remains outside this dolphin. Verify
its current contents and deliver the live-statement corrections only through a later
documentation-only change that preserves immutable and dated historical receipts.

## 7. Exact continuation sequence

1. Rebuild both programme-gate descendants and the non-self-referential publication
   manifest after every candidate change.
2. Run the pack validator, all focused audit-pack tests, complete lint tests,
   formatting, exact CI mypy gates, pre-commit and proportionate cross-layer regression.
3. Perform a fresh adversarial review of source population, dependency ordering,
   F5 separation, synthetic-evidence boundaries and R07/P09/R08 closure semantics.
4. Re-fetch `origin/main` and re-run the conflict audit before commit. Inspect every
   intervening file; do not blindly rebase across overlapping audit-pack work.
5. Stage only the gate-ledger dolphin, inspect the cached diff, commit, push and open a
   narrow pull request. In PR prose, say “Issue #1110 remains OPEN”; never use a negated
   GitHub closing-keyword phrase adjacent to the issue number.
6. Wait for every required and aggregate check on the exact current head. Merge only
   when current, CLEAN/MERGEABLE and terminal green; then prove tree identity and run
   post-merge focused validation before retiring the worktree and branches.
7. Continue separately with current-main F5-01 and #1111-to-current delta
   reconciliation, independent FX/Monte Carlo QA, P4 controls, versioned reproductions
   and the verified 72-rule live-statement correction inventory.
8. Regenerate the Board/lender synthesis last. Only R07 can record RELEASED, and R08
   remains the sole authorised closure-action gate after P09 consolidation.
