# Standards watch: external re-checks, business confirmations, and gated canon-movers

Status: **Tracking** (opened 2026-07, extended 2026-08-23). This is a **living watch list**, not
a decision. It records items the model must periodically re-check, with their review dates and
current status, so a deferred item is a **tracked deferral** and not a silent omission. Nothing
here changes any computed KPI.

It carries two families, which share that discipline but arise differently:
**(1)** external-standard revisions and lender term-sheet business confirmations, opened under
#620 and held in the first table; and **(2)** the **gated canon-movers** register added
2026-08-23, which gives every gated KPI-moving change an owner and a calendar review date.

## Why this file exists

Issue #620 ("Standards-watch: IFC Framework Phase I re-check, 6-mo DSRA, ATB vintages") bundled
three provenance / standards items. One (the ATB-vintage citation refresh) was an autonomous docs
change and has **landed** (#620a, see below). The other two are **deferrals**, not build items:
one waits on an external standard-setter's output (~Q4 2026), the other is a one-line business
confirmation the analyst must obtain from the lender side. Left in the issue tracker alone they
risk being lost; recorded here they are owned and dated.

## Watch items — external standards and business confirmations (#620)

| # | Item | Type | Review / trigger date | Current status |
|---|---|---|---|---|
| 1 | **IFC Sustainability Framework Phase I output** | External-standard re-check | ~Q4 2026 (on IFC publication) | **Open — do NOT pre-empt.** The 2012 IFC Performance Standards remain in force; the model's ESIA/safeguards references (`docs/knowledge_base/02_dutch_bay_project_dossier.md`, `03_kalpitiya_60mw_and_esia.md`) cite the 2012 PS and must **not** be pre-emptively rewritten to a draft. Re-check when the Phase I revision is published; only then decompose any citation/gap updates into dolphins. |
| 2 | **6-month DSRA regime vs CEB-PPA lender term sheet** | Business confirmation | On receipt of an executed/indicative term sheet | **Open — one-line confirmation pending.** The engine funds a **6-month** Debt Service Reserve Account (`reserves.dsra_months: 6` in `scenarios/dutchbay_lendercase_2025Q4.yaml`; resolved by `finance/debt_v14.py::_build_funding` with a 6.0-month fallback and `dsra.target_months → Financing_Terms.dsra_months → Financing_Terms.reserves.dsra_months` precedence — the resolver name `_compute_dsra` previously cited here never existed in `finance/`; it only ever appeared in this file, commit `28afe30`). This matches the flat-LKR, no-escalation CEB standardized PPA assumption but is **not yet lender-confirmed** — financing is uncommitted (no executed term sheet; see the `debt_terms` evidence note). Confirm the 6-month target against the intended term sheet; if the lender specifies a different reserve, update the scenario config (KPI-moving → user-gated). **Checked 2026-07-11 (#920):** no executed/indicative term sheet exists — swept `~/Downloads` (only three tariff/financials workbooks remain post the 2026-07-11 re-clone; no term-sheet / mandate / facility document) and the repo (the `debt_terms` evidence-register note in `scenarios/dutchbay_lendercase_2025Q4.yaml` still records "No executed term sheet (financing uncommitted)", tier `assumption`). CEB standardized PPA verified **silent on DSRA** from the documents, not asserted: the SPPA commercial-terms record (`docs/knowledge_base/02_dutch_bay_project_dossier.md` §4 — basis/term, tariff, curtailment/deemed energy, availability LD, carbon, interconnection, payment security) carries **no reserve-account covenant**; its only reserve-like term is CEB's own payment security in the *seller's* favour (escrow + ~3-month standby L/C). A DSRA is a lender covenant, not a PPA term; a repo-wide grep for DSRA/debt-service-reserve in `docs/knowledge_base/` hits only the PF-methodology doc. **6-month target retained** as the market-standard assumption per `docs/knowledge_base/05_project_finance_methodology.md` §1.5 (DSRA "commonly the **next six months** of debt service", funded at close, topped up from the waterfall, released at maturity). Engine re-verified at `finance/debt_v14.py` L1339/L1356–1368; the full four-rung precedence order + fallback is now pinned by `tests/finance/test_dsra_fund_at_close.py::test_dsra_months_full_precedence_order_and_fallback`. **Trigger unchanged (armed — re-confirm on receipt of a term sheet).** |
| 3 | **NREL ATB benchmark vintages in the evidence register** | Citation refresh | Re-check on each new ATB release (annual) | **DONE (#620a, commit `0f24863`).** The generic NREL citations in the lendercase evidence register carry their explicit **ATB 2024/2025** vintage, and the ATB 2024 financial-cases anchor (P50 DSCR ~1.25× contracted solar / ~1.3–1.4× contracted wind at a ~2.5% real rate) is recorded on the DSCR benchmark ranges (`docs/knowledge_base/05_project_finance_methodology.md`) and, as cross-check context, on the `debt_terms` evidence note in `scenarios/dutchbay_lendercase_2025Q4.yaml`. `as_of` dates kept; KPI oracle byte-identical. Re-check when NREL publishes a new ATB vintage. |

## Provenance (verified 2026-07-03 against main `03fdeda`, not asserted)

- **DSRA regime** — `finance/debt_v14.py` (~L1158–1222) wires `Financing_Terms.dsra_months` /
  `reserves.dsra_months` into an up-front-funded reserve of `target_months` of year-1 debt
  service, default **6.0** months; the canonical lender scenario sets `reserves.dsra_months: 6`.
- **IFC PS references** — `docs/knowledge_base/02_dutch_bay_project_dossier.md`,
  `03_kalpitiya_60mw_and_esia.md`, `DEEP_RESEARCH_VALIDATION.md` cite the 2012 IFC Performance
  Standards.
- **ATB vintage refresh (#620a)** — commit `0f24863` ("docs(provenance): refresh NREL ATB
  benchmark vintages in the evidence register (#620)"), touching
  `docs/knowledge_base/05_project_finance_methodology.md` and
  `scenarios/dutchbay_lendercase_2025Q4.yaml` only.

---

## Gated canon-movers (hard-items register)

Opened 2026-08-23 (decision D1b/D1-ii/D1-x, see
[`AGENTIC_DELIVERY_PRACTICE.md`](AGENTIC_DELIVERY_PRACTICE.md) §5.3). **Nothing in this
section changes any computed KPI**; it records ownership and review dates for changes that
*would*.

### Why this register exists

`DELIVERY-01` governs how **big** an increment is; nothing governed how **hard** it is.
External practitioner evidence (`AGP-SRC-001`) reports that unattended agentic delivery
drifts reliably toward easier work — documentation, lint, smoke tests, provenance — and that
pattern is visible here: merged work skews strongly KPI-neutral while the changes that would
move the canon stay gated.

**The gating is correct.** A KPI-moving change is the analyst's call, and several of these
are properly blocked on evidence that does not exist yet. The failure this register guards
against is narrower: a gate that quietly becomes a lapse. From outside, "deferred pending
lender evidence" and "forgotten" look identical unless a date is attached.

Hence the register's one rule: **a calendar review date is mandatory even where a trigger
exists.** Trigger-only tracking is precisely what lets a deferral go quiet — if the trigger
never fires, nothing ever asks the question again. The trigger stays; the calendar date is
added beside it.

### Register

| # | Item | Tracker | Direction on canon | Gate | Calendar review | Status |
|---|---|---|---|---|---|---|
| G1 | **F5-02** — make debt denomination and repayment numeraire explicit before canonical re-baseline | #1095 → **#1110** | **Raises equity IRR** (audit estimate ≈ +1.8 pp), *opposite in direction* to F5-01, which has landed (#1034, 2026-08-16) | Transaction evidence. The analyst-generated synthetic term sheet is explicitly **not** lender evidence; authenticated lender/legal documents are required before binding canon | **2026-11-30** | **Open — consolidated, not resolved.** #1095 was closed `NOT_PLANNED` on 2026-08-20 as a *documented queue consolidation*: its technical acceptance criteria moved to #1110 and the closing note states the finding is not resolved. The controlled-successor registers still carry F5-02 as a separately-closeable finding. **F5-01 and F5-02 must never be netted, rhetorically or technically** |
| G2 | **6-month DSRA vs the CEB-PPA lender term sheet** | #920 | Depends on the lender's reserve requirement | Business confirmation on receipt of an executed/indicative term sheet | **2026-11-30** | Open. Detail is held in watch item 2 above — **cross-referenced here, not duplicated**. Trigger armed since 2026-07-11; the calendar date is what this register adds |
| G3 | **Canon-gated credibility defaults for lender runs** | #962 | KPI-moving by construction (per-PR defaults + re-baseline) | User-gated | **2026-11-30** | Open |
| G4 | **Authenticated real AEP/QSTS financial outcome and finance-wiring decision** (`#923-B`) | #1078 | KPI-moving if the finance wiring is enabled | Blocked on G5 | **2026-11-30** | Open, `blocked` |
| G5 | **Authenticated real DutchBay POC feeder evidence** — ingest (#1075) and engineering validation (#1076) | #1075, #1076 | None directly; unblocks G4 | Blocked on obtaining authenticated third-party evidence | **2026-11-30** | Open, `blocked` |
| G6 | **Controlled-successor remediation queue and release gate** | #1110 | Umbrella for G1 and the 111-row findings register | Condition-gated: `HOLD` lifts only on an explicit `RELEASED` disposition | **2026-11-30** | Open, blocking. Condition-gating is correct for a release gate; the calendar date exists so the *conditions* are re-read, not to force the gate |

### Review procedure

At each calendar review, for every row: confirm the gate still holds and say why, or move the
item. An item may be closed out of this register only by being **done**, or by an explicit
recorded decision not to do it — never by going stale. A review that changes nothing is a
valid outcome and should be dated in the Status cell, exactly as watch item 2 records its
2026-07-11 re-check.

Out of scope for this register: #924 (full feasibility study) and #925 (mobile epic) are
user-gated *deliverables*, not canon-movers, and are tracked in the issue queue alone.

## Sources

- `DutchBay_Code_Audit_CodeGrounded_2026-07-01.md` (§1a verification table) and
  `DutchBay_Enhancement_Benchmarking_2026-07-01.md` (§4 register, §5 roadmap), against
  v15.2.0 / main `132df24` (byte-identical to the reports' `dd66b23` baseline).
- Issue #620 (P3, standards-watch).
