# Session handover — 2026-08-28, successor 4

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-28_3.md`](SESSION_HANDOVER_2026-08-28_3.md).
The predecessor remains authoritative for the startup preflight, protected-primary synchronization,
worktree/resource ownership checks, open audit queue, dependency order and release/evidence
boundary. This successor changes only the later repository cutoff and records Dolphin 1 of the
global commercial feasibility-platform programme.

## 1. Exact repository and delivery cutoff

At the Dolphin's final pre-commit fetch, protected `main` and `origin/main` were clean and identical
at `f84a241593c2518ecb5c87d92b190bf358682e67`, the merge of PR #1185. The protected primary
checkout remains clean at that SHA.

The writing worktree is:

- path: `/Users/aruna/Downloads/dutchbay-wt-report-contract`;
- branch: `codex/global-feasibility-report-contract`;
- pull request: [#1186](https://github.com/arunakulat/dutchbay-epc-model/pull/1186);
- first contract commit: `ac4982e239e4d025ee6d8d2fd462b6b4b300d9b3`; and
- merge policy: do not merge or enable auto-merge without the owner's explicit go-ahead.

PR #1186 was open and non-draft when this successor was written. Its first-head CI had started and
the required verification-receipts check had passed; other checks were still running. This
successor adds a later commit, so only checks bound to the final PR head are authoritative. Re-query
the PR head, branch currency and required checks rather than relying on this dated observation.

## 2. Dolphin 1 outcome

Dolphin 1 defines the target meaning of a complete DutchBay global feasibility-report package. It
does not implement the package and does not claim current conformance. The delivered files are:

- [`docs/FEASIBILITY_REPORT_CONTRACT.md`](FEASIBILITY_REPORT_CONTRACT.md) — the normative target
  contract;
- [`docs/FEASIBILITY_REPORT_CONTRACT_SOURCES.md`](FEASIBILITY_REPORT_CONTRACT_SOURCES.md) — the
  primary-source proposition and ingress ledger;
- `README.md` — documentation index entry; and
- `changelog.d/feasibility-report-contract.added.md` — KPI-neutral change record.

The contract preserves `config/feasibility_sections.yaml` as the sole owner of the ordered 20
section identities. It requires a future immutable `FeasibilityReportPackage` to carry every
section and applicable capability as an execution or explicit disposition, with separate state
for:

1. run posture;
2. applicability;
3. production outcome;
4. evidence sufficiency;
5. independent review;
6. achieved assessment grade; and
7. package release authority.

It also defines the 20-section minimum-content matrix, cross-section reconciliations, source and
evidence metadata, capability and limitation registers, run/artifact binding, cross-format semantic
parity, DBPL fail-loud behavior, 17 conformance controls and a seven-Dolphin implementation
sequence.

## 3. Material current-state findings

The contract records the following current gaps without changing them:

- `run.mode` and legacy `report_grade` are execution posture only, never assurance or release;
- the present authored-coverage resolver has only `complete`, `draft` and `not_applicable`, is soft
  by default, and cannot express the required orthogonal states;
- optional report components may currently disappear as `None` or render omission without a
  complete disposition;
- HTML, generic PDF and API-oriented paths share `app.reports.report_model.ReportContext`, but no
  complete canonical package exists;
- `/v1/cases/report.xlsx` independently reruns the pipeline through
  `analytics.executive_workbook.emit_executive_workbook_from_pipeline`;
- a generic report PDF is not a DBPL artifact;
- `app.models.WindFarmInputs` inherits committed Sri Lankan base variants and is not a safe global
  jurisdiction boundary; and
- evidence scoring, module coverage and the current run manifest are useful foundations, not
  report-grade, bankability or release certificates.

The global product boundary is explicit: Sri Lanka is the first deeply developed reference pack,
not a hidden default for unknown jurisdictions. “Marrying” the codebase means each applicable
product capability is registered, reachable, tested and report-visible as executed or explicitly
dispositioned; it does not mean every helper or inactive technology executes for every project.

## 4. Research and verification receipts

The governed runtime remained
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` on Python 3.12.13, with the active worktree first
on `PYTHONPATH`. `check_venv.sh --no-bootstrap` passed, and the canonical bootstrap loaded 72 active
GWTF v3.0 rules.

The specialist used 13 official standards-owner, regulator or multilateral sources. Only EP4 and
the World Bank/ESMAP grid guide PDFs were interpreted; both were downloaded from official URLs,
hashed, converted through the governed MarkItDown tool, and checked against page-preserving
extraction. Their hashes and pinpoint locations are retained in the source ledger. The temporary
research workspace was removed after the minimum durable receipt was captured.

Independent primary-agent verification on the final contract files produced:

- focused pytest command over `tests/analytics/test_feasibility_sections.py` and
  `tests/lint/test_compile_changelog.py`: `40 passed in 0.18s`;
- contract integrity: all 20 taxonomy IDs present once and in order; canonical N/A token, live
  `ReportContext` path and local Markdown links passed;
- pre-commit over the four changed files: every applicable hook passed; Python-only hooks skipped
  because no Python file changed; and
- `git diff --check`: passed.

These are structural and documentation receipts. They do not prove lender acceptance, project
facts, financial correctness, audit completion or release readiness. GitHub CI on the exact final
PR head remains the merge authority.

## 5. Decisions retained for the owner and later Dolphins

The implementation sequence can start without changing the contract, but the following decisions
remain deliberately visible:

1. whether `decision_grade` and `lender_grade` remain public product labels or receive more
   conservative display labels while retaining machine semantics;
2. how legacy `report_grade` is renamed or permanently documented as execution posture;
3. whether current evidence-score wording containing “bankable” is renamed immediately or first
   receives a non-grade disclaimer;
4. which institutional authority may move a jurisdiction pack from `supported` to `assured` and,
   separately, authorize package release; and
5. confirmation that Dolphin 2 implements the typed machine package by extending/parity-testing
   the existing section SSOT rather than creating another YAML taxonomy.

The recommended next implementation Dolphin is the machine contract and taxonomy-parity slice.
It should add typed package/state/register contracts plus strict cross-field and negative-control
fixtures, without moving finance behavior, altering the live audit gates or beginning a language
rewrite.

## 6. Release and audit boundary

PR #1186 and this handover do not alter the governed audit programme. Issue #1110 remains open;
release remains `HOLD`; P01, P02 and P03 remain independently controlled; F5-01 and F5-02 remain
separate; authenticated F5-02, resource and real-grid evidence remain absent where previously
recorded. A green PR, taxonomy parity, report coverage, evidence score or `run.mode=lender` cannot
clear those gates.

Start the next task with section 1 of successor 3, then re-query PR #1186 and the live audit queue.
Do not retire this worktree or branch while the PR is open. If the owner later authorizes a merge,
verify exact-head required CI, protected merge, main synchronization and tree equivalence before
safe worktree/branch removal.
