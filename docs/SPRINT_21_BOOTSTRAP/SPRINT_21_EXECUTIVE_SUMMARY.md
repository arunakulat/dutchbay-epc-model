# Sprint 21 bootstrap — executive summary

**Subject:** the platform development plan received from the project owner on 26 September 2026,
recorded verbatim at `docs/source_materials/platform_strategy_2026/`.
**Base:** `main` at `b87ee32`. **Status:** evaluation draft, not independently reviewed; it adopts,
schedules and authorizes nothing.

## Verdict

The plan should not be adopted as the Sprint 21 plan. Its goals are largely sound, but it is a
generic blueprint that does not describe this repository, it contains technical errors that would
produce wrong numbers or wrong law if implemented as written, and its most valuable content is
already on the repository's own remediation path. The recommended course is to take its goals
into Sprint 21 as small, finding-mapped dolphins and to continue the sub-annual cashflow work
already in progress.

## Key findings

1. **The starting premise is wrong.** The plan describes "a localized, single-asset repository"
   of "simple Python/Excel scripts". The six engine packages hold 109,991 lines of Python, with
   392 test modules, 37 committed scenarios across wind, solar, BESS and hybrids for several
   projects, a FastAPI service with JWT, async jobs and SSE progress, and a Fly.io deployment.
2. **Most of the plan already exists.** Of 38 line items, 14 are implemented and 11 partly
   implemented. Several exceed the plan's specification: dual P50/downside DSCR sizing,
   fee-inclusive sculpting, separable calendar-and-cycle battery ageing, PyWake wake modelling,
   an interest-parity FX hedge, a vintage-tracked loss carry-forward with expiry, and a
   three-statement output with tie-out checks.
3. **Nine technical corrections are needed.** The most consequential: the plan sizes maximum
   debt as the NPV of CFADS, which is sizing at 1.00x coverage and oversizes debt by the target
   DSCR factor, 30% at 1.30x (checked numerically against the repository's own function). It
   also relies on LIBOR, which ceased in September 2024; cites a "WDAT for EU" depreciation
   schedule that this review could not identify (the writing-down allowance is a United Kingdom
   mechanism); misstates the OECD interest-limitation recommendation; drives hourly dispatch
   from Weibull and flow-duration distributions, which carry no chronology; and proposes battery
   arbitrage, which has no revenue basis under the committed CEB contracts, where the buyer
   dispatches the asset.
4. **Its finance content is the audit's open work.** Eleven items touch findings of the August
   2026 audit that block Board and lender release under #1110, including a critical finding on
   scheduled-maturity balance and cash sweep, debt sizing on an unlevered tax basis, DSRA
   characterisation, the absent maintenance reserve and the LKR tranche currency. That work
   should be done, finding by finding, not by building a parallel engine.
5. **The infrastructure rewrite has no present need.** A database, a React client, Kubernetes
   and a Polars migration answer a multi-tenant product that has not been decided. Today's scope
   is a small set of known clients, served by the existing stack. The global feasibility contract
   DBAY-FRC-001 already defines how the platform becomes multi-jurisdiction, through versioned
   packs, and lists a rewrite among its non-goals.
6. **Hourly resolution belongs in producers and dispatch, not in the debt engine.** Lenders
   test coverage quarterly or semi-annually. The right design aggregates hourly results onto the
   finance period grid that Sprint 20 Lane A is building (draft #1231).
7. **The schedule conflicts with the delivery rules.** Five phases over twenty weeks is the
   "whale" that `DELIVERY-01` forbids.

## Recommended Sprint 21 scope

For the owner's decision:

- **Lane A:** complete review of #1231 (A1 and A2), then A3, sub-annual debt service and DSCR.
- **Lane B:** B2, the waterfall shortfall treatment (P2-F3-01), and B3, a maintenance reserve and
  multi-tier lock-up mechanism defaulting to off (P3-COV-08). Prepare B1, the levered-tax CFADS
  basis (P2-F4-01), as the one KPI-moving dolphin, with its independent oracle.
- **Lane C, evidence only:** the F5-02 lender and legal evidence; the Sri Lankan Inland Revenue
  Act text for the interest-limitation dolphin; reserve requirements from the term sheet and
  LTSA; measured wind data (#1290).

Everything else in the plan is deferred to later sprints, each behind a named decision.

## Decisions required

| ID | Decision |
|---|---|
| D1 | Sprint 21 direction: finding-led bankability work with Lane A (recommended), or the rebuild |
| D2 | Web product scope: known clients, or a multi-tenant service. This alone decides database, client framework and orchestration |
| D3 | Whether to add a second jurisdiction, which one, and who owns its sources and review |
| D4 | Keep the plan text public in the corpus, or reduce it to manifest-only before merge |
| D5 | Recruit the `RECRUIT-01` domain and assurance reviewers for this pull request |
| D6 | Confirm the sprint number, assumed to be 21 |
| D7 | Whether a lender-auditable formula workbook is wanted, scoped as an independent oracle |

## What this session did

- Recorded the plan verbatim as a new corpus area with a SHA-256 manifest and a single handling
  note, `PLATFORM-PLAN-HANDLING-2026-09-26`, registered in the corpus guard.
- Wrote this bootstrap: the comprehensive analysis, these notes and the research notes.
- Wrote a successor handover record so the next session finds this work.
- Changed no finance code, configuration, scenario or KPI.
