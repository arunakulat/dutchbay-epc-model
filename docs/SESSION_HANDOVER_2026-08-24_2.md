# Session handover — 2026-08-24, successor 2

Durable record per **PERSIST-01**. Successor to
[`docs/SESSION_HANDOVER_2026-08-24.md`](SESSION_HANDOVER_2026-08-24.md). The
predecessor remains authoritative for its canon vector, governance changes,
environment traps and pre-existing open items except where this record updates
their live state.

**Session:** desktop session, 2026-08-24.
**Entry point:** clean `main` at `2b87214`.
**Exit:** clean `main` at `5cbda3e`.
**Nature:** audit-control erratum and continuity update. No model, scenario,
contract, dependency pin or canonical KPI was changed.

---

## 1. Bootstrap — use AGENTS.md, not this handover

`AGENTS.md` remains the startup contract. The canonical source remains
`go_with_the_flow_rules_v3_0_clean.csv`; derive its active population with
`dutchbay_bootstrap_rules.py` rather than copying a fixed rule count into an
instruction.

The persistent local runtime passed at session start:

```text
selection_source  DUTCHBAY_VENV
python_prefix     /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
python_version    3.12.13
active_checkout   /Users/aruna/Downloads/dutchbay-epc-model
import_path       /Users/aruna/Downloads/dutchbay-epc-model/analytics/__init__.py
status            PASS
```

The bootstrap derived `72` active v3.0 rules at this cutoff. That number is a
dated receipt, not a standing instruction.

## 2. Main moved after the predecessor

The predecessor recorded an exit at `3a175f8`. Before this session began,
`main` had advanced through:

- #1142, which published the predecessor handover and updated its AGENTS.md
  pointer;
- #1129, DBPL malformed-table-row fail-loud behavior;
- #1132, MCP campaign-threshold naming; and
- #1143, governed synthetic-lane MCP wiring fenced from canonical finance.

Those merges were observed from current Git history; this session did not
re-audit their substantive acceptance evidence.

## 3. Issue #1141 is closed

Issue #1141 identified a stale fixed-count instruction in the immutable
2026-08-19 audit programming record and the related captured RS-F3 pointer.
PR #1144 delivered the correction as an additive control and squash-merged as
`5cbda3e595a1d73046a50f8cf2ab925d686bed05`.

The historical programming record was not edited. Its SHA-256 remains:

```text
7e22468672ff52cd70b669fb85a2dd16087477785f432b8b14ff74940877e799
```

The additive file is
`docs/audit/2026-08-controlled-successor/03_AUDIT_ERRATA_2026-08-24.md`.
It records the dated 72-rule receipt, replaces the standing fixed-count
instruction with a source-derived instruction, and classifies RS-F3's “63 of
66” wording as a preserved historical pointer rather than a current
population. RS-F3 remains `not_examined` pending separate adjudication.

The audit successor remains on **HOLD**. Closing #1141 does not lift #1110,
change a finding disposition, or provide Board, lender or release evidence.

## 4. Verification receipts for #1141

Local receipts on source commit `7de7ce5`:

- controlled pack validator: `PASS`, `release_status=HOLD`, 57 manifest
  entries, `ruleset_count_erratum=PASS`;
- focused pack tests, including two negative controls: `3 passed`;
- complete `tests/lint`: `236 passed`;
- Ruff check and format, Black, strict mypy, `git diff --check`, canonical GWTF
  bootstrap and all staged hooks: passed; and
- negative controls proved refusal when the immutable record digest drifted or
  the source-derived instruction was removed.

PR #1144 CI completed with 17 successful checks, three governed skips and no
failures or pending checks. Grid Study, report qualification and stochastic
qualification were correctly skipped by the changed-path policy for this
audit-documentation change. The squash-merged tree exactly matched the tested
source tree `f1c315f3aed0ab15a2d8529f34b27985dfe3b81a`.

Post-merge validation on `main` returned the same controlled-pack `PASS` and
retained `release_status=HOLD`.

## 5. Open items and safe next work

The predecessor's open-item table changes as follows:

- **#1141 is complete** through PR #1144.
- **#1138 remains the next actionable TEST-01 compliance programme.** It is
  four dolphins, one scenario oracle per PR: capex cases, Kalpitiya 5 USc,
  Mullikulam and lendercase. Each guard must perturb genuine drivers through
  `evaluate_with_overrides`, exclude solved targets such as sculpted
  `min_dscr`, assert movement rather than direction or magnitude, and include
  a frozen-output negative control.
- **#1139 remains an owner decision.** Do not promote `PR Receipts` to a
  required repository status check without that decision. The job is visible
  and passed on PR #1144, but it is not yet a required-check setting.
- **#1140 remains date-gated** for 2026-11-30.

The pre-existing release/evidence items remain open: #1110; authenticated
real-feeder chain #1075, #1076 and #1078; and #962, #920, #924, #925 and #788.
No attempt was made here to move their gates.

## 6. Disk and worktree boundary

At session start, free space was 5.9 GiB. After protected delivery and cleanup
it was 4.7 GiB, below the predecessor's observed approximately 5.4 GiB needed
for a full worktree. Do not begin a code or finance-test dolphin by silently
falling back to shared `main`.

This handover-only correction used a sparse documentation worktree because it
needed only `AGENTS.md`, the handover chain and `changelog.d/`. That is not a
valid substitute for a complete worktree when implementation, tests, package
resolution or repository-wide inspection is required. Free sufficient disk or
obtain an explicitly safe complete worktree before starting #1138.

At this cutoff, the unrelated
`/Users/aruna/Downloads/dutchbay-wt-1074-synthetic-provenance-report` worktree
remains active on `codex/1074-synthetic-provenance-report` at `3a8a92f`. This
session did not modify or clean it.

## 7. Boundary

No engine or canon-mover was executed. No scenario fixture, expected KPI,
financial contract, dependency version, QSTS evidence classification or
release decision changed. The next session must re-fetch `origin/main`,
re-check issue and PR state, re-run the persistent-environment receipt and
derive the active GWTF population before acting.
