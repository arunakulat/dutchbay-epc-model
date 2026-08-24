# Session handover — 2026-08-24, successor 3

Durable restart record per **PERSIST-01**. Successor to
[`docs/SESSION_HANDOVER_2026-08-24_2.md`](SESSION_HANDOVER_2026-08-24_2.md).
The predecessor remains authoritative for its governance and audit-control
receipts except where this record updates live state. This successor was
written immediately before a user-requested machine restart.

**Session:** Codex desktop, 2026-08-24.
**Protected main at cutoff:** `f2b6bed8bf5121f650a957afcfe643beb2ce0515`.
**Active worktree:**
`/Users/aruna/Downloads/dutchbay-wt-1110-f5-02-lender-pack`.
**Active branch:** `codex/1110-f5-02-lender-pack`.
**Branch base:** exact current `origin/main` at `f2b6bed8bf5121f650a957afcfe643beb2ce0515`.
**Restart state:** coherent local work is preserved on the task branch; it has
not been pushed, opened as a PR, merged or represented as release-clearing
evidence.

---

## 1. Bootstrap after restart

`AGENTS.md` is the startup contract. Re-read it, re-fetch `origin/main`, and
re-run the governed environment and rule bootstrap before editing:

```bash
export DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
"$DUTCHBAY_VENV/bin/python" -VV
cd /Users/aruna/Downloads/dutchbay-wt-1110-f5-02-lender-pack
DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
git status --short --branch
git worktree list
git fetch origin
```

Put this worktree first on `PYTHONPATH`; do not create a checkout-local virtual
environment. At the cutoff, the persistent environment was Python 3.12.13.

## 2. Superseded capture-time statement about #1138

Successor 2 was drafted before its author saw the already-created
`dutchbay-wt-1138-lendercase-responsiveness` worktree. Its statement that #1138
was next/not-yet-started is therefore superseded. The first #1138 lendercase
dolphin already had an owner at that capture time, and the full programme is
now complete:

- PR #1146 — lendercase responsiveness guard — merged;
- PR #1147 — capex responsiveness guards — merged;
- PR #1148 — Kalpitiya responsiveness guard — squash-merged as
  `acfaf3145f390ee0ca09c7de9994137bdcd25cc5`;
- PR #1149 — Mullikulam responsiveness guard — squash-merged as
  `f2b6bed8bf5121f650a957afcfe643beb2ce0515`; and
- issue #1138 is closed.

Do not rewrite the merged predecessor; this additive successor is the
PERSIST-01 correction.

## 3. #1074 recovery and cleanup are complete

The eleven deletions in the obsolete #1074 worktree were confirmed by the
owner to be accidental. They were recovered exactly, the recovered branch was
checked for patch equivalence against the squash-merged `main` tree, and only
then was the obsolete worktree removed. Its local branch was deleted and stale
worktree metadata was pruned. No #1074 source-retention exception remains open.

## 4. #1139 and #1140 state

Issue #1139 was audited against the live repository ruleset. The strict
required contexts remain `Test Summary`, `fastlane` and `smoke`. The PR-receipt
verification context is visible and useful, but promotion to a required status
check remains an owner decision. No repository setting was mutated without
that decision. Audit comment:
<https://github.com/arunakulat/dutchbay-epc-model/issues/1139#issuecomment-5390930412>.

Issue #1140 remains date-gated for **2026-11-30** and does not lift the #1110
HOLD or merge F5 evidence classes. Review-state comment:
<https://github.com/arunakulat/dutchbay-epc-model/issues/1140#issuecomment-5390932925>.

## 5. #1110 remains on governed release HOLD

The release HOLD is substantive, not merely administrative. The source corpus
still lacks lender-confirmed primary transaction evidence for F5-02, including
facility denomination; drawdown currency; principal-accounting currency;
interest basis and payment currency; repayment and conversion mechanics;
hedging; reserve obligations; fees; security and remedies; and related
regulatory/tax terms. A generated questionnaire or locally reproducible test
cannot substitute for that external evidence or authorize canon/release.

The latest gate audit at this cutoff recorded:

- 51 architecture pointers marked `not_examined`, plus five deferred pointers;
- 23 #1110 gates: two satisfied-but-unchecked, 18 unsatisfied, two blocked on
  external F5-02 evidence, and one with stale wording;
- 11 method controls still classified `required_not_run`; and
- five old controls unavailable because their original evidence stream is not
  recoverable. New, versioned reproductions may establish current behavior but
  must not overwrite or masquerade as the missing originals.

The 11 required-not-run controls are:

```text
P4-CFG-1-SCHEMA-GUARD
P4-CFG-2-YAML-SAFE-LOAD
P4-F1-CI-GATE-RUNS
P5-REPRO-A14-001
P5-REPRO-C1-001
P5-REPRO-C2-001
P5-REPRO-C8-001
P5-REPRO-D4-001
P5-REPRO-LLCR-001
P5-REPRO-RISK-001
P5-REPRO-WIND-001
```

The five unavailable historical controls remain explicitly unavailable:

```text
P2-SCRATCH-R1_F1_CHECK
P2-SCRATCH-R1_F1_CHECK2
P2-SCRATCH-R1_F1_CHECK3
P2-SCRATCH-R2_CHECK
P2-SCRATCH-R2_FEE
```

The separately named current reproductions are:

```text
P2-REPRO-F1-01-SCALE-V1
P2-REPRO-F1-05-CAPEX-TIMING-V1
P2-REPRO-F1-CANON-TIMELINE-V1
P2-REPRO-F2-DEBT-SEAMS-V1
P2-REPRO-F2-FEE-BASIS-V1
```

Formal independent examination still requires dedicated 56-row architecture
and 23-row gate ledgers. Scout mappings are preparation, not adjudication.

## 6. Active F5-02 lender-input dolphin

The current worktree owns the first #1110 dolphin. Its purpose is to make the
missing F5-02 evidence collectable, safe to re-ingress, and fail-closed without
promoting blank templates, synthetic reproductions or internal decisions into
lender facts.

Current task files are:

- `.gitignore` — excludes returned/completed confidential F5-02 material;
- `analysis_tools/f5_02_lender_return.py` — strict safe-YAML validator and
  structural/closure-candidate rules;
- `scripts/validate_f5_02_lender_return.py` — Hydra CLI that emits a minimal
  five-field public receipt;
- `docs/audit/lender-input/DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml`
  — 53-requirement lender questionnaire with no pre-populated canonical values;
- `docs/audit/lender-input/DUTCHBAY_F5_02_INTERNAL_DECISION_RECORD_TEMPLATE_v1.yaml`
  — separate repository-owned decision record, defaulting to HOLD/off;
- `docs/audit/lender-input/DUTCHBAY_1110_NONCANONICAL_QA_AND_REINGRESS_CHECKLIST_v1.md`
  — downloadable operating checklist for non-canonical QA, reconstructions and
  controlled re-ingress;
- `tests/lint/test_f5_02_lender_input_pack.py` — positive and adversarial
  controls; and
- `changelog.d/1110-f5-02-lender-pack.added.md`.

The validator currently enforces, among other controls:

- duplicate-key, alias, unsafe-tag and multi-document refusal;
- YAML-1.2-like boolean handling so `YES`/`NO`/`ON`/`OFF` remain strings;
- exact project/facility requirement coverage;
- typed entity shapes and unique identifiers;
- decimal-string amount/rate values with explicit units and ISO currencies;
- facility-scoped claim citations and traversed embedded evidence references;
- confirmed-value completeness and evidence eligibility;
- separate repository-owned decision authority;
- refusal to validate a returned/closure input inside the public repository;
  and
- an exact five-field non-confidential public receipt.

The pack remains an evidence request and method control. It does not clear
F5-02, #1110 or release.

## 7. Verification state at restart

Completed before the last adversarial folds:

- focused pack tests: passed;
- complete `tests/lint`: **272 passed**;
- controlled pack validation: PASS while retaining release HOLD; and
- changed-file pre-commit checks: passed.

After folding the latest two-lens findings—confirmed-value completeness,
evidence eligibility, nested evidence traversal, typed scalars, public-path
refusal and receipt minimization—the focused suite was rerun and reported:

```text
36 passed in 3.45s
```

The complete lint suite and changed-file harness must be rerun after restart
because those broader receipts preceded the final folds. A full repository
pytest run was started, then deliberately interrupted at approximately 7% on
the user's restart request; its exit status was 2 and it is **not** a pass or a
failure receipt. No pytest process remained at handover time.

Two final adversarial-review agents had been asked to re-review the folded
state, but their terminal reports had not been collected before restart. Run a
fresh independent two-lens review if their state does not survive the restart.

## 8. Exact continuation sequence

1. Re-bootstrap using section 1 and reconcile the branch with any new
   `origin/main` change without losing local work.
2. Verify the local checkpoint tree and rerun the 36 focused tests.
3. Rerun complete `tests/lint`, Ruff check/format, Black, strict mypy,
   `git diff --check`, the controlled pack validator and changed-file hooks.
4. Re-run the proportionate full repository tests. Record only concise
   receipts; routine runtime logs remain ephemeral.
5. Complete independent two-lens adversarial review and fold any real defect.
6. Only after all local controls pass: normalize the checkpoint if needed,
   push, open one narrow PR, wait for every required/aggregate CI check, and
   merge only when current and green.
7. Continue #1110 sequentially in separate dolphins: the 56-row architecture
   examination ledger, the 23-row gate ledger, additive current-main F5-01
   reconciliation, the #1111-to-current delta ledger, independent FX/Monte
   Carlo QA, P4 controls, and separately versioned method reproductions.

Do not reinterpret a reconstruction as same-stream verification. Independent
review must use a separate implementation, existing oracle, invariant,
closed-form result, or other evidence not authored by the change being tested.

## 9. Resource and confidentiality boundary

At this cutoff, the only active task worktree was the F5-02 lender-pack
worktree plus protected `main`. Filesystem free space was approximately 11 GiB.
Do not create another full worktree while this dolphin is active unless the
resource position is rechecked and the concurrent writer has an explicit
owner.

No lender-returned or completed confidential YAML belongs in this public
repository. Returned evidence must be held in the designated private ingress
location, hashed and catalogued there, validated by explicit path, and reduced
to the minimal public receipt only after governed review.
