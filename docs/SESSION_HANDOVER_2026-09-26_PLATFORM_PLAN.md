# Session handover — 2026-09-26: platform development plan recorded and evaluated

Status at writing: delivered on branch `claude/laughing-mccarthy-wffp1k` as a draft pull request;
independent review pending; not merged. The pull request and any review records bound to its
head are the authority for later state, not this pre-merge snapshot.

## Scope and predecessor

This is a scoped successor to `docs/H08_DELIVERY_HANDOVER.md`, in the way H08 was scoped to H08.
It adds one workstream and changes nothing else. Every statement of H08 stands as H08 left it,
including its declaration that the repository startup record is
`docs/SESSION_HANDOVER_2026-09-07.md`. A session that reads this record first should read H08
next and follow its chain; then return here for this workstream's open items.

## What happened

The project owner supplied a five-phase, twenty-week plan to rebuild this repository as a
multi-technology, multi-jurisdiction web platform, with the instruction "analyze, evaluate,
memorize, add to corpus and discuss" for the next sprint. This session:

1. Recorded the plan verbatim as a new corpus area,
   `docs/source_materials/platform_strategy_2026/`, SHA-256
   `a1be78037cc4bc662541b8e9e6f1b167bb2451c2fe88f68d411fb6b6245bf444`. Its handling is stated
   once, under `PLATFORM-PLAN-HANDLING-2026-09-26` in that area's `MANIFEST.sha256`, and the
   anchor is registered in `tests/lint/test_nso_corpus_manifest_integrity.py`.
2. Evaluated it in `docs/SPRINT_21_BOOTSTRAP/`. The verdict is not to adopt the plan as the Sprint
   21 plan but to take its goals as finding-mapped dolphins and continue Sprint 20 Lane A. Read
   the executive summary first.
3. Recorded the owner's decisions, given in this session as replies to the recommendations:
   **D1** finding-led work with Lane A, not the rebuild ("yes"); **D2** known clients now,
   multi-tenant as the planned extension ("known clients currently - plan to extend to
   multi-tenant"); **D4** keep the plan text public ("keep on public branch"), now the recorded
   publication authority in the handling note; **D5** review under the repository's rules, the
   harness and the framework principles ("follow repo rules, harness, frameworks").
4. Changed no finance code, configuration, scenario, KPI, `VERSION` or ruleset row.

## Open items for this workstream

1. **Open owner decisions: D3, D6 and D7** (executive summary, "Decisions"): a second
   jurisdiction; the sprint number, assumed to be 21; a formula workbook as an independent oracle.
2. **`RECRUIT-01` review.** The pull request is `R2_LOAD_BEARING` (data ingestion, a guard-test
   registration, a planning record). It needs a project-finance domain reviewer and a separate
   assurance reviewer before merge, recruited under D5. The pull request and the review records
   bound to its head are the authority on whether that is done. Do not merge on green CI alone;
   the A1 revert (#1232) is the precedent.
   *Update, 28 October 2026:* it merged on 29 September 2026 without the pair. The post-merge
   domain review returned REJECT, and its blocking findings are corrected through #1477 to #1483
   (analysis, section 13). The assurance review is still owed under #1371.
3. **Evidence to request before the finance dolphins** (analysis, Lane C): F5-02 lender and legal
   evidence; the Inland Revenue Act No. 24 of 2017 and amendments, for interest limitation; the
   term-sheet reserve requirements; measured wind data. (#1290 has since merged a partial
   met-mast export held under a `HOLD` on annual or lender-grade use; it is not that evidence.)

## Traps found this session

- **Withdrawn on 28 October 2026 (#1483).** This bullet said that `finance/period_grid_v14.py` was
  not on `main` and that text treating Sprint 20 A1 as landed was stale. It was true at this
  record's base, `b87ee32`. It stopped being true when this record merged: before the merge the
  pull request's head took in #1231 (`d3157e0d`), which restored A1 and landed A2, so
  `finance/period_grid_v14.py` and `finance/subannual_rows_v14.py` are on `main` from `e35ea9f2`.
  Text that treats A1 as landed is correct; do not distrust it on this record's word.
- `SPRINT_BOOTSTRAP_PROC_R1` requires a "5-pass analysis" that no file in the repository defines.
  The bootstrap README records the passes actually performed rather than inventing a definition.
- `scripts/list_session_handover_records.py` took 50.3 s of wall time in this container with this
  record committed (`time` around the resolver). `AGENTS.md` requires the owner to optimise and
  review the resolver before its runtime exceeds 60 seconds. The figure is from a cloud container,
  not the owner's workstation, and was not repeated.
- This container's network policy blocked `eur-lex.europa.eu`, `www.fca.org.uk`,
  `www.ag-grid.com` and `www.gov.uk`, so external claims were verified at the level recorded in
  the research notes. PDFs must go through the governed MarkItDown workflow in any case (`R26`).

## Environment and verification

Cloud container, Python 3.12.3 from the checkout-local `.venv` provisioned by
`.claude/hooks/session-start.sh`; full history and tags fetched. Evidence on the owner's
workstation and in the private `DutchBay_RAG` repository was not reachable. The receipts for this
change are in the pull request body.

## Authority

This record authorizes no implementation. It confers no grade, release, audit, lender, Board,
publication, issue-closure or `HOLD` authority, and it does not move the startup pointer.
