# Session handover - 2026-08-28, successor 5

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-28_4.md`](SESSION_HANDOVER_2026-08-28_4.md).
The predecessor remains authoritative for the global feasibility-report contract, primary-source
ledger, audit queue, evidence boundaries and implementation sequence. This successor records only
Dolphin 0: the prose-first Global Feasibility Report Master Template v1 and its DBPL print
projection. It neither implements the future machine package nor changes a release gate.

## 1. Exact repository and delivery cutoff

At the final fetch, protected `main`, `origin/main` and the writing branch base were clean and
identical at `d6f27e49d2f97931c9613fd836113b454fdf5ddd`. The protected primary checkout was not
edited and remained clean.

The isolated writing surface is:

- path: `/Users/aruna/Downloads/dutchbay-wt-global-report-template`;
- branch: `codex/global-feasibility-report-template`;
- base: `d6f27e49d2f97931c9613fd836113b454fdf5ddd`;
- state at handover: intended changes uncommitted for primary review;
- push/pull request/merge: not performed; and
- merge policy: do not push, open a pull request, merge or enable auto-merge without the owner's
  authorized delivery step.

Do not retire the worktree before the intended changes and ignored final PDF have been reviewed and
their required durable disposition is known.

## 2. Dolphin 0 outcome

The delivered tracked files are:

- [`docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md`](GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md)
  - controlled prose authoring architecture, version 1.0.0;
- `README.md` - documentation-index entry;
- `changelog.d/global-feasibility-report-master-template.added.md` - KPI-neutral change record; and
- this PERSIST-01 successor.

`config/feasibility_sections.yaml` remains the only source of truth for section identity and order.
The template repeats those identities only as a tested prose projection: exactly 20 IDs, once each,
in exact YAML order. It does not introduce a competing taxonomy or a machine schema.

The template contains 2,092 lines and 15,794 whitespace-delimited words. Controlled opening matter
separates document identity, audience, scope/cutoffs, distribution/reliance, status, grade, evidence,
review and release. Every numbered section carries:

1. a purpose and decision question;
2. required narrative;
3. required inputs/outputs or, for Section 20, required appendices/registers;
4. minimum exhibits;
5. evidence, review and applicability expectations;
6. jurisdiction and technology applicability;
7. cross-section reconciliation;
8. a fillable drafting block;
9. explicitly fictional example wording; and
10. author/check/review/release responsibility boundaries.

The global boundary is explicit. Unknown jurisdictions must not inherit Sri Lankan assumptions;
Sri Lanka is only the first reference pack when activated and labelled. Hybrid and shared assets,
inactive technologies, unsupported packs, synthetic/advisory lanes and applicable capabilities
receive visible treatment rather than silent omission. “Marrying the codebase” means every
applicable product capability is executed or explicitly dispositioned, not that every helper or
inactive lane runs.

The template is target authoring architecture. It does not claim that current HTML/PDF/XLSX/JSON/API
surfaces already conform, that all approximately 200 modules compose, or that any project is
feasible, bankable or released.

## 3. DBPL runtime artifact and visual receipt

The final runtime artifact is intentionally ignored by Git and retained at:

`output/pdf/Global_Feasibility_Report_Master_Template_v1_DBPL.pdf`

It was generated through `app.reports.dbpl.print_core.render_dbpl_pdf` with the complete governed
`[report]` stack and a two-pass provenance stamp. Direct/generic WeasyPrint was not used. The final
receipt is:

- PDF SHA-256:
  `b98d3e6cfd205e70e2891a7186aebd7d107cfbdf1e174888cce36a9865ce0b6b`;
- source Markdown SHA-256:
  `2029b57d53b279e1163889b5b707cc3ff3248095f1ea0de9904b40a780dab09e`;
- production code identity: `d6f27e49d2f97931c9613fd836113b454fdf5ddd`;
- size/pages: 378,771 bytes, 70 A4 portrait pages;
- metadata: title correct, WeasyPrint 69.0 producer, PDF 1.7, tagged `yes`, suspects `no`;
- print result: `pdf/ua-1`, stylesheet applied, complete report extra available;
- fonts: bundled Source Serif 4, Source Sans 3 and Source Code Pro families only; eight subset
  faces reported by `pdffonts`, all embedded and Unicode; no substituted fonts; and
- syntax/stream check: `qpdf --check` passed.

The task-local Markdown-to-DBPL projection helper was removed after validation because this Dolphin
was expressly prose-first and did not authorize a new renderer or production command. The final
artifact, source and receipts are preserved, but the repository does not yet have a one-command
master-template PDF reproducer. Treat that as future renderer integration work rather than claiming
automated byte-for-byte regeneration today.

All 70 pages were rasterized with Poppler. Five final contact sheets were inspected, supplemented
by original-resolution checks of the cover/control page, section starts, tables, fictional-example
pages, closing checklist and provenance page. A pixel-level furniture screen found the controlled
banner and document footer on 70/70 pages. No clipping, overlap, broken table, incomplete caveat,
unlabelled continuation or unresolved visual defect remained.

The final PDF was re-ingressed with the governed MarkItDown command and independently extracted
with `pdftotext -layout`. Both paths preserve all 20 IDs in order. The page-preserving extraction
contains the controlled banner and document identity on 70/70 pages. Normalized unique-source-token
visibility was 99.958%; the sole expected projection exception was the source filename for the
governing contract in the duplicate Markdown control table, because the DBPL base deliberately
replaces that table with the controlled DBPL document-control block.

## 4. Governed startup, source basis and checks

The runtime remained `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` on Python 3.12.13, with this
worktree first on `PYTHONPATH`. `check_venv.sh --no-bootstrap` passed, and the canonical bootstrap
loaded 72/72 active GWTF v3.0 rules. The unmodified CASPER, CESSPIT and CCCDIR definitions were
re-ingressed before drafting.

The authoring pass inspected the governing report contract and source ledger, the section taxonomy,
live report model/orchestration/renderer, evidence and run-manifest machinery, API/workbook routes,
DBPL print core/style/template/font controls and relevant tests. No new external proposition was
introduced, so no competing or supplementary research ledger was created.

Focused repository verification passed:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
  -p no:cacheprovider \
  tests/analytics/test_feasibility_sections.py \
  tests/app/test_feasibility_report_wiring.py \
  tests/app/test_dbpl.py \
  tests/app/test_dbpl_fonts.py \
  tests/lint/test_compile_changelog.py -q

137 passed in 6.27s
```

The final contract screen also passed: 20/20 ordered taxonomy parity, all required prose blocks in
20/20 sections, fictional-example/placeholder separation in 20/20 sections, 29 local Markdown
links resolved, no prohibited Unicode dash characters in the template, and 20/20 PDF ID parity
through both extraction paths. `codespell`, `aspell`, `hunspell`, `vale` and `markdownlint` were not
installed; language review therefore used structured heading/phrase screens plus full manual prose
and rendered-page review rather than claiming an unavailable automated spelling gate.

## 5. Boundaries and retained current gaps

This Dolphin changes no calculations, schemas, orchestration, renderer, finance behavior,
jurisdiction/technology pack, public grade vocabulary or audit gate. In particular:

- `run.mode=lender` and legacy `report_grade` remain execution posture only;
- target grade, achieved grade, evidence strength, independent review and package release remain
  separate;
- current optional `ReportContext` content can still be absent without the future complete
  disposition model;
- current XLSX production still reruns the pipeline independently and is not yet bound to one
  canonical report object;
- current jurisdiction defaults are not made globally safe by this prose template;
- automated authorship/provenance is not human Prepared, Checked, Reviewed or Approved identity;
- a tagged PDF and green structural tests do not establish accessibility conformance, lender
  acceptance, bankability, project facts or professional authorization; and
- release remains `HOLD`; P01, P02 and P03 remain independently controlled; F5-01 and F5-02 remain
  separate; authenticated F5-02, resource and real-grid evidence remain absent where previously
  recorded.

## 6. Next controlled step

The immediate next step is primary review of the prose, tracked diff, runtime PDF and receipts. If
accepted, the owner may authorize a cohesive commit and the normal push/PR/exact-head CI workflow.
Do not represent this uncommitted writing checkpoint as merged or implemented behavior.

After Dolphin 0 is accepted, Dolphin 2 may implement the typed machine package and strict
taxonomy-parity/negative-control contracts described by DBAY-FRC-001. It must extend the existing
section SSOT, preserve finance and release boundaries, and avoid a language rewrite. Re-query the
live repository, open PRs/issues and exact audit state before that work begins.
