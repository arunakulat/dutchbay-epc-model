# Sprint 21 bootstrap — comprehensive analysis of the platform development plan

| Control | Value |
|---|---|
| Subject | `docs/source_materials/platform_strategy_2026/PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt` |
| Subject SHA-256 | `a1be78037cc4bc662541b8e9e6f1b167bb2451c2fe88f68d411fb6b6245bf444` |
| Repository base | `main` at `b87ee32`, 26 September 2026 |
| Prepared by | Claude Code cloud session, acting as sole coordinator |
| Review status | Not independently reviewed. `RECRUIT-01` class `R2_LOAD_BEARING`; the review pair is pending |
| Authority | None. This record adopts, schedules and authorizes nothing, and lifts no `HOLD` |

## 1. Purpose, method and reading rule

The project owner supplied a five-phase, twenty-week plan to rebuild this repository as a
multi-technology, multi-jurisdiction web platform, and asked for it to be analysed, evaluated,
recorded and discussed for the next sprint. This document is the evaluation.

Method:

1. The plan was read in full and split into 38 line items (section 3).
2. Each item was searched for in the code on `main`. Where an implementation exists, the
   implementing module was read and is cited as `path:line`.
3. Each finance item was cross-checked against the August 2026 audit findings register
   (`docs/audit/2026-08-controlled-successor/registers/findings_register.v2.json`) and its
   current-main overlay (`findings_current_state_overlay.v1.json`).
4. External factual claims about law, reference rates and licensing were checked against
   sources; the level of each check, and the claims that could not be verified, are in
   [`SPRINT_21_RESEARCH_NOTES.md`](SPRINT_21_RESEARCH_NOTES.md). Statements of engineering or
   finance practice are attributed to the repository record that states them where one exists;
   otherwise they are framed as questions or recommendations rather than asserted as fact.
5. One numerical check was run against the repository's own debt-sizing function (section 4, C1).

Reading rule: "exists" means code on `main` implements the item, not that the implementation is
reviewed, bankable or free of open findings. Where an audit finding touches an item, its state is
quoted from the overlay, which records most rows as not yet re-examined against current `main`.

## 2. The plan's starting premise against the repository

The plan describes the repository as "a localized, single-asset repository" built from "simple
Python/Excel scripts". The measured state on `main` at `b87ee32` does not match that description.

| Measure | Value | Command |
|---|---|---|
| Python in the six engine packages | 109,991 lines (`analytics` 73,979; `app` 13,135; `finance` 12,303; `wind_resource` 7,033; `solar_resource` 2,700; `api` 841) | `git ls-files <pkg> \| grep '\.py$' \| xargs cat \| wc -l` |
| Test modules | 392 | `git ls-files tests \| grep -c -E '(^\|/)test_[^/]*\.py$'` |
| Committed scenario YAML (top level) | 37 | `git ls-files 'scenarios/*.yaml'`, excluding `test/`, `overrides/`, `_scrtch/` |
| Optional dependency extras | 14 | `pyproject.toml` `[project.optional-dependencies]` |

The scenarios cover the Dutch Bay wind lender and equity cases, wind-solar and wind-BESS
hybrids, a solar-only case, Kalpitiya, Mullikulam (Mannar), Kolonnawa, two CEB 10 MW BESS
tender structures and the NSO 250 MW BESS portfolio. The repository is multi-technology and
multi-project already; it is single-jurisdiction (Sri Lanka).

The plan names no module, scenario, decision record, rule or audit finding of this repository.
Its proposals therefore have to be read as a generic target architecture and mapped onto the
code by this evaluation, which is what section 3 does.

## 3. Line-item assessment

Legend for the Assessment column: **Exists** (implemented on `main`); **Partial** (implemented in
part, the gap is named); **Gap** (not implemented); **Incorrect** (the item as written is
technically wrong, see section 4).

### 3.1 Phase 1 — foundation and system architecture

| # | Plan item | State on `main` (evidence) | Assessment | Recommendation |
|---|---|---|---|---|
| 1 | FastAPI API routing | `app/api/main.py` (FastAPI app, `/health`), `app/api/jobs_router.py` (`POST /jobs`, SSE `GET /jobs/{id}/events`), `app/api/auth.py` (JWT), `app/web/routes.py` (wizard, `report.html`/`.pdf`/`.xlsx`) | Exists | None |
| 2 | Polars with NumPy | NumPy throughout; pandas pinned `>=2.0,<3.0` (`pyproject.toml:23`) pending a KPI-oracle-verified migration (#593); no Polars | Gap, not a need | Do not migrate the engine. `docs/ARCHITECTURE.md` records about 0.05 s for a full run on a frozen AEP (not re-measured here); the costly stages are the producers, not dataframe operations. Admit Polars only inside a new module where profiling shows a need, behind an optional extra (`FRAMEWORK-01`) |
| 3 | PostgreSQL with TimescaleDB | No database. API users are a provisioned secret (`fly.toml`), job state is Redis (`app/jobs/redis_store.py`) | Gap, not a need at current scope | See section 5.2. Keep time series as content-addressed, hash-pinned files; add a database when the product needs persistent multi-user state (decision D2) |
| 4 | React/Next.js, Tailwind, AG Grid, Recharts | Server-rendered Jinja wizard (`app/web/routes.py:107`) with HTML, PDF and XLSX report downloads | Gap, not a need at current scope | See section 5.3; decision D2 |
| 5 | Docker with Kubernetes | `Dockerfile`; `docker-compose.yml` (Redis, web, worker); `fly.toml` (separate `web` and `worker` processes; web machines auto-start) | Partial: containers and a separately scalable worker exist; no Kubernetes | See section 5.4; no change without a measured scaling need |
| 6 | `Projects` / `Assets` tables, multi-technology | Scenario YAML with `generation.technologies`; type registry `finance/tech_types.py:25-44`; aggregation `analytics/portfolio/generation_aggregator.py`; shared-POI curtailment `analytics/portfolio/poi_curtailment.py:33` | Exists within a project; no multi-project portfolio consolidation was found | Keep configuration in YAML (`ARCH-01`, `FRAMEWORK-02`). A portfolio view is a separate, later decision |
| 7 | `Macro_Curves`: FX forwards, LIBOR/SOFR curves, inflation | FX curve explicit or parametric (`finance/cashflow_v14_fx.py:43`); interest-parity forward hedge (`finance/cashflow_v14_contracts.py:8`); CNY and EUR curve slots (`analytics/fx/fx_builder.py:52`, `:400`); FX calibration and history (`analytics/fx/`). Debt carries fixed rates per tranche; no floating-rate or swap logic | Partial; **Incorrect** on LIBOR (C2) | Floating-rate debt is a real gap, but material only if the term sheet specifies floating debt. Evidence first (F5-02), then a floating-rate tranche option on a current benchmark |
| 8 | `Tax_Regimes` table | Sri Lanka regime in `finance/cashflow_v14_tax.py`; `docs/FEASIBILITY_REPORT_CONTRACT.md` section 3.1 specifies versioned jurisdiction packs | Gap in form; **Incorrect** on "WDAT for EU" (C3) | Implement jurisdictions as packs under DBAY-FRC-001 (statute, effective date, sources, review), not as table rows (section 5.6; decision D3) |

### 3.2 Phase 2 — multi-technology generation

| # | Plan item | State on `main` (evidence) | Assessment | Recommendation |
|---|---|---|---|---|
| 9 | Solar with pvlib: irradiance, tilt, clipping | `solar_resource/pv_producer.py`: clear-sky scaled to measured GHI or a frozen hourly TMY; Erbs/DISC decomposition; Hay-Davies transposition; PVWatts DC; inverter clipping at AC nameplate; Faiman cell temperature | Exists | None |
| 10 | Solar tracking, single- and dual-axis | Fixed tilt only (`solar_resource/pv_producer.py`, module docstring) | Gap | Single-axis tracking is a bounded producer dolphin. Dual-axis only if a project specifies it |
| 11 | Wind power curves, Weibull, wake, air density | `wind_resource/bankable_aep.py:66` (IEC 61400-12-1 density correction), `:219` (PyWake wake, Bastankhah-Porte-Agel default); `weibull_fit.py`, `mcp.py`, `era5_*.py`, `power_curve_sourcing.py`, `layout_optimizer.py` (TopFarm) | Exists; a Weibull fit cannot drive hourly dispatch (C5) | No model build. The binding constraint is resource evidence: #1110 records that without on-site mast and MCP evidence there is no bankable resource claim (#1290 is in flight). The off-path AEP cluster in `docs/ARCHITECTURE.md` still awaits its wire-or-retire decision |
| 12 | 8760-hour dispatch replacing annual P50/P90 | Finance engine is annual (`analytics/aep_reconciliation.py:3`). Hourly series exist in producers (frozen TMY), shared-POI curtailment and grid QSTS (8,760-step records in `analytics/contracts_v14.py`). Sub-annual finance is Sprint 20 Lane A: A1 merged as #1225, reverted by #1232 for missing review, re-proposed with A2 in draft #1231 | Partial; **Incorrect** as a replacement for P50/P90 (C5) | Section 5.1. Continue Lane A. Keep hourly resolution in the producer and dispatch layer and aggregate it onto the finance period grid |
| 13 | BESS non-linear degradation by DoD and C-rate | `finance/bess_revenue.py`: geometric model and an NREL BLAST-style separable calendar-plus-cycle model driven by equivalent full cycles (DoD-dependent); SoH floor 0.70 (`:121`); models registry (`:132`) | Partial: DoD dependence exists (linear); no C-rate term | Calibrate to OEM warranty degradation tables before adding model forms. The NSO corpus holds an OEM warranty policy and LTSA workbook |
| 14 | SoH-triggered augmentation capex | Scheduled augmentation (`revenue.augmentation_schedule`; `finance/bess_revenue.py:741`) that restores SoH | Partial: scheduled, not triggered | A trigger mode that places the event in the year SoH crosses a configured threshold. Config-first, default unchanged |
| 15 | Arbitrage dispatch optimiser | None. The module states that it does not run a dispatch simulation (`finance/bess_revenue.py:68`). Revenue models are `capacity_charge` and `energy_tariff` | Gap; not applicable to the committed contracts (C9) | Defer to a merchant-market jurisdiction pack. For Sri Lanka, model the dispatch a tariff actually pays for: night-peak shifting and absorption of curtailed energy |
| 16 | Mini-hydro: flow duration curves | `hydro` and `run_of_river` are enum-only; billing one requires `allow_unvalidated_flat_cf: true` (`finance/tech_types.py:25-44`) | Gap | A hydro technology pack when a hydro project enters the pipeline. No committed scenario is hydro |
| 17 | Hydro power `P = η·ρ·g·Q·H`, seasonality | As item 16 | Gap; incomplete as written (C5) | Use net head, flow-dependent turbine efficiency, compensation flow and minimum turbine flow. Drive seasonality and dispatch from a daily flow series; a flow duration curve alone has no chronology |

### 3.3 Phase 3 — fiscal and multi-currency

| # | Plan item | State on `main` (evidence) | Assessment | Recommendation |
|---|---|---|---|---|
| 18 | Native-currency inputs per line (EUR turbines, LKR civils, USD tariff) | Capex in USD; tariff in LKR or converted from USD; debt tranches in LKR, USD and CNY (`analytics/fx/fx_builder.py:52`); EUR curve slot (`:400`) | Partial | A genuine extension. It must follow the migration path in `docs/CURRENCY_NUMERAIRE_DECISION.md` (alias, then one file per commit), and it waits on F5-02 |
| 19 | Translation to a base currency for debt sizing | Debt sizing runs on USD-view CFADS (`finance/cashflow_v14_contracts.py:8` docstring); revenue is LKR-primary by decision (`docs/CURRENCY_NUMERAIRE_DECISION.md`) | Exists, with open findings | Close P2-F5-01 (delivered, review pending), P2-F5-02 (blocked on external evidence), P2-F5-03 and P3-MCFX-01 before extending |
| 20 | FX hedging: forwards and cross-currency swaps | Forward hedge with hedge ratio, spread and parity forward curve (`finance/cashflow_v14_contracts.py:8`); hedging coverage (`analytics/fx/fx_builder.py:592`). No cross-currency swap | Partial; P3-COV-06 open | Design a swap only after F5-02 evidence fixes debt denomination and repayment numeraire. Whether an LKR hedge is obtainable at project tenor is a market-evidence question; the model must not assume a hedge that cannot be bought |
| 21 | Depreciation: straight-line, declining balance, MACRS | Straight-line and split plant/civil straight-line (`finance/cashflow_v14_tax.py:359`, `:396`) | Partial; US scope incomplete (C8) | Add methods inside jurisdiction packs, each with statute and effective date |
| 22 | Loss carry-forward, finite or indefinite | Vintage-tracked ledger with an expiry window (`finance/cashflow_v14_tax.py:495`); `loss_carryforward_years` must be `>= 0` and `0` disables carry-forward | Partial: no explicit indefinite mode; P2-F3-05 records that `0` means two different things on two construction paths | Add an explicit indefinite mode rather than a sentinel number, and resolve P2-F3-05 in the same dolphin |
| 23 | Tax holidays | `build_tax_holiday_map` (`finance/cashflow_v14_tax.py:460`); losses preserved through holiday years | Exists | None |
| 24 | Interest limitation ("thin capitalization") | Binary `interest_deductibility` only (`finance/cashflow_v14_tax.py:174`). Audit P2-F4-04 (open) already specifies the design | Gap; **Incorrect** as written (C4) | Implement P2-F4-04 as specified, after the Sri Lankan position is confirmed from the Inland Revenue Act primary text |

### 3.4 Phase 4 — project-finance structuring

| # | Plan item | State on `main` (evidence) | Assessment | Recommendation |
|---|---|---|---|---|
| 25 | "Static 70/30 sizing is insufficient" | Gearing is solved against the real amortisation schedule to hold the DSCR target (`finance/debt_v14.py:1251`) | Premise does not apply | None |
| 26 | CFADS | CFADS timeline and debt layer (`finance/debt_v14.py:921`) | Exists; P2-F4-01 (high) open: sizing runs on unlevered tax | Fix P2-F4-01. It moves KPIs, so `DOC-02`, `VERSION` and a `TEST-01` oracle apply |
| 27 | Sculpt principal to a target DSCR | `_sculpted_schedule` (`finance/debt_v14.py:867`), with senior credit-support fees netted inside the sculpt (#737); dual P50/P99 downside case (`:1323`) | Exists, beyond the plan's scope | None |
| 28 | Maximum debt from NPV of CFADS | `size_debt_with_dual_dscr` (`finance/debt_v14.py:1984`) sizes on the NPV of CFADS divided by the target DSCR | Exists; the plan's formula is **Incorrect** (C1) | Keep the code |
| 29 | Waterfall steps 1-3: revenue, opex and tax, senior debt service | Cashflow and debt layers | Exists | None |
| 30 | DSRA: sweep cash to fill six months | `_build_funding` (`finance/debt_v14.py:1593`) funds a DSRA at financial close when `Financing_Terms.dsra.fund_at_close` is set. The lender case declares `reserves.dsra_months: 6` (`scenarios/dutchbay_lendercase_2025Q4.yaml:502`) but does not set `fund_at_close` | Partial; P3-COV-05 (high) open | Establish the required structure from the term sheet (cash-funded, funded at close, or letter of credit), then configure it; add a letter-of-credit option |
| 31 | MRA for major overhauls | None found | Gap; P3-COV-08 (medium) open | A reserve mechanism, default off, sized from LTSA or O&M evidence |
| 32 | Shareholder distributions | `finance/equity_distribution_v14_hydra.py`: DSCR lock-up, sweep percentage, reserve months | Exists, with open findings P2-F3-01 (shortfall clamped to zero) and P3-COV-03 (critical: large scheduled-maturity balance with partial cash sweep) | Fix P2-F3-01; analyse P3-COV-03 before any mechanism change |

### 3.5 Phase 5 — bankability and interface

| # | Plan item | State on `main` (evidence) | Assessment | Recommendation |
|---|---|---|---|---|
| 33 | Scenario-matrix runner | Batch CLI `run_scenario_analytics_v14.py`; grid, Latin hypercube and pymoo plans (`analytics/sensitivity/optimizer.py`); global sensitivity (`analytics/sensitivity/global_sa.py`) | Exists; labelling issue (C6) | Label combined downsides as stress cases, not P90 |
| 34 | Monte Carlo P10/P50/P90 of equity IRR | `analytics/mc/engine.py`; Latin hypercube and Sobol samplers (`analytics/mc/samplers.py:19`, `:105`); correlation, convergence and covenant-breach modules; risk blocks under `FRAMEWORK-01` | Exists; open P2-MC-SENS-02 (delivered, review pending) and P5-WIND-003 (P50-to-P90 formula) | Close the findings. State percentile and direction explicitly for IRR (C6) |
| 35 | Three-statement model | `analytics/three_statement.py:157` with tie-out checks (`:113`), rendered in the lender report (`app/reports/report_model.py`, `app/reports/templates/report.html.j2`) | Exists; documented limitations (tax not re-credited for the full interest shield, 100% sweep, equity as the balancing item) | Interactivity is the only gap; it follows decision D2 |
| 36 | Web dashboard | Server-rendered wizard and report | Partial | Decision D2 |
| 37 | Excel export "maintaining all formulas" | Values-only workbooks, byte-reproducible (`analytics/executive_workbook.py`, `analytics/reproducible_workbook.py`) | Gap; **Incorrect** as framed (C7) | If a lender-auditable workbook is wanted, build it as an independent formula model and use it as a `TEST-01` oracle (decision D7) |
| 38 | "Weeks 1-20" phase schedule | Not applicable to code | **Incorrect** for this repository's delivery rules (section 6) | Decompose into dolphins (section 8) |

Summary: of 38 items, 14 exist, 11 exist in part, 11 are gaps and 2 are premises that do not
apply (items 25 and 38). Three of the gaps (items 2, 3 and 4) are gaps without a present need.
Section 4 records nine technical corrections; the items they touch are marked **Incorrect** or
cite the correction. Eleven items touch at least one open audit finding (section 7).

## 4. Technical corrections

Each correction states what the plan says, what is correct, the consequence of implementing the
plan as written, and the source.

**C1 — Debt capacity.** The plan sizes maximum debt as "the NPV of CFADS discounted at the debt
interest rate". Debt capacity is the present value of the *debt service the cash flow can
support*, which is CFADS divided by the target DSCR, discounted at the cost of debt over the
tenor and then capped by gearing. Discounting CFADS itself sizes debt at a DSCR of 1.00x: if the
full present value of CFADS is borrowed and sculpted over the same tenor at the same rate, debt
service equals CFADS in every period. At a 1.30x target the plan's formula oversizes debt by
exactly 30%. Receipt, using the repository's own function with 15 periods of flat CFADS of 10,
an 8% debt rate and a 1.30x target (full command in the research notes, section 2.2):

```text
repository sizing, NPV of CFADS / 1.30:  65.84214375327976
plan wording, NPV of CFADS:              85.5947868792637
ratio:                                   1.3
```

The code is already correct (`finance/debt_v14.py:1984`). The plan also omits the dual-case
sizing the code performs (P50 and a downside case, the binding one governs) and the gearing cap.

**C2 — LIBOR.** All 35 LIBOR settings ceased permanently; the last synthetic US dollar settings
were published on 30 September 2024 (FCA). A curve store designed in 2026 should hold SOFR or
term SOFR for USD debt and the applicable local benchmark for LKR debt. The Central Bank of Sri
Lanka moved to a single Overnight Policy Rate from 27 November 2024 (CBSL). Which benchmark an
LKR facility references is a term-sheet fact.

**C3 — "WDAT for EU".** No EU-wide tax depreciation schedule of that name was identified.
The writing-down allowance is a United Kingdom capital-allowances mechanism, a reducing-balance
allowance on pooled plant and machinery, and the United Kingdom is not an EU member. Depreciation
for tax purposes is set by each jurisdiction's own law, which is why it belongs in versioned
jurisdiction packs with statute and effective date (section 5.6).

**C4 — Interest limitation.** The plan cites an "EBITDA 30% rule under OECD BEPS Action 4".
Action 4 recommends a fixed-ratio rule within a corridor of 10% to 30% of EBITDA, with an optional
group-ratio rule (OECD, 2016 update). The fixed 30% is the EU Anti-Tax Avoidance Directive,
Article 4, which also permits a EUR 3 million safe harbour and an exclusion for loans funding
long-term public infrastructure projects; that exclusion can be material for a generation project.
A debt-to-equity limit ("thin capitalisation" in the narrow sense) is a different mechanism from
an earnings-based limit, and the Sri Lankan rule appears to be the former: secondary sources
describe section 18 of the Inland Revenue Act No. 24 of 2017 as a debt-to-capital-and-reserves
limit with carry-forward of disallowed interest. The primary text was not ingested in this
session and must be before any code relies on it. Audit finding P2-F4-04 already specifies a design with modes `none | debt_to_equity |
ebitda_ratio` and requires that confirmation first.

**C5 — Distributions cannot drive chronological dispatch.** The plan combines an 8760-hour dispatch
model with "hub-height wind speed data (Weibull distributions)" and with flow duration curves. A
Weibull fit and a flow duration curve are frequency distributions; they discard the order of
events. Dispatch, storage state of charge, curtailment against an export limit and seasonal
hydro all depend on sequence. Hourly dispatch needs chronological series: long-term-corrected
hourly wind (ERA5 adjusted by MCP to on-site measurement), a measured or typical-year irradiance
series, and a daily flow series for hydro. Hourly modelling also does not replace P50/P90.
Exceedance levels express uncertainty and inter-annual variability, which a single repeated year
understates; the open audit finding P5-WIND-003 concerns exactly the P50-to-P90 step.

**C6 — Probability labels.** "P90 Generation + High Inflation + High Capex" stacks downsides. Their
joint probability cannot exceed the 10% of the generation leg alone, and for largely independent
drivers such as wind resource, inflation and capex it is far below it. It is a legitimate
combined stress case and should be labelled as one, not as a P90. For equity IRR, "P10/P50/P90" is ambiguous because the
energy-yield convention reads P90 as a 90% exceedance level; state the percentile and its
direction. Trials with no defined IRR must be reported as undefined, not as zero (`FIN-01`).

**C7 — "Maintaining all formulas".** The engine is Python; the workbooks it writes hold values.
There are no spreadsheet formulas to maintain. A formula-bearing workbook is a second
implementation of the model. The plan's premise that lenders want to audit a spreadsheet is not
disputed here, and an independently built model is exactly the kind of oracle `TEST-01` asks
for; but it is a model build with its own reconciliation tests, not an export option. A formula
workbook written by Python also needs a recalculation step before its values can be compared:
openpyxl 3.1.5 stores `=A1*A2` and reads back no cached value until the workbook is recalculated
(research notes, section 2.5).

**C8 — United States tax scope.** The plan names MACRS as the US example. US renewable project
finance is dominated by the technology-neutral credits (sections 45Y and 48E) and the tax-equity
structures used to monetise them. The One Big Beautiful Bill Act of 4 July 2025 terminated those
credits for wind and solar facilities placed in service after 31 December 2027 unless
construction began by 4 July 2026. A US pack without credits and their current terms would not be
fit for purpose.

**C9 — BESS arbitrage.** Arbitrage earns revenue only where a market or tariff pays for moving
energy in time. In the committed CEB capacity-charge structure the buyer dispatches the asset and
pays an availability-based charge (`finance/bess_revenue.py`, module docstring), so an arbitrage
optimiser has no revenue basis there, and a single buyer paying contracted tariffs publishes no
spot price that could turn negative. What can matter in Sri Lanka is shifting solar energy into
the paid night-peak window and absorbing energy that would otherwise be curtailed, and only where
the tariff pays for it.

## 5. Architecture evaluation

### 5.1 Hourly resolution: where it belongs

Hourly resolution matters for:

- curtailment against a shared export limit (already modelled from hourly profiles,
  `analytics/portfolio/poi_curtailment.py:33`);
- storage dispatch and state of charge;
- time-of-use tariffs, such as a night-peak window;
- grid studies (already 8,760-step QSTS records under `analytics/grid/`);
- capture prices in merchant markets.

It does not matter for debt service, which follows the lender's payment period (the #1225 record
states lender convention as at least quarterly), nor for tax or depreciation, which are annual.
The sound architecture is therefore:

1. hourly producers (wind, solar, hydro) emitting chronological series;
2. an hourly dispatch step only where a contract pays for dispatch;
3. aggregation onto the finance period grid, with flows summed and balances taken at period end;
4. the finance engine at the period resolution lenders use.

Step 3 is what Sprint 20 Lane A is building. The A1 contract (merged as #1225, reverted by #1232,
re-proposed in draft #1231) states the aggregation rule by variable kind — flows sum, balances
take the period-end value, and there is deliberately no generic aggregate — and routes
sub-periods to debt periods through `annual_row_debt_period_map` rather than directly. The #1225
record warns that the debt layer already has a collision between two DSCR index spaces and that a
third axis added carelessly would compound it. A "25 years × 8760 hours" finance grid is that
third axis.

Volume and compute: one 25-year hourly series is 219,000 values, about 1.75 MB as 64-bit floats.
Data volume is not the constraint. Compute is, once dispatch is optimised inside a Monte Carlo:
10,000 trials of a daily optimisation over 25 years is about 91 million solves. The dispatch
method (rule-based, daily perfect foresight, or representative days) decides feasibility far more
than the dataframe library does.

### 5.2 Database

Model inputs here are frozen, hash-pinned exports (the wind export, the frozen TMY) and every run
carries a `run_manifest` with the configuration hash and engine version (`MRM-02`). Storing
inputs as mutable database rows would weaken that reproducibility unless the rows were themselves
content-addressed and immutable. Time series fit the existing evidence model better as
content-addressed files recorded in a manifest. A database is the right tool for mutable
multi-user state — accounts, job history, audit logs — which today is a provisioned secret and
Redis. TimescaleDB is dual-licensed: an Apache 2.0 core and Community features under the Timescale
License, which is free for self-hosting but restricts offering the database as a service; whether
a given host supports the extension must be checked. Decision D2 decides whether any of this is
needed.

### 5.3 Frontend

The live wizard is server-rendered and already produces HTML, PDF and XLSX outputs. A React or
Next.js client adds a second language and toolchain that the repository's gates do not cover:
`mypy`, `ruff`, the LibCST lint suite and the 95% coverage floor are Python-only. A TypeScript
client needs its own strict type checking, linting, tests, dependency audit, lockfile and update
policy before it meets the same standard. AG Grid's Excel export is an Enterprise feature under a
commercial licence; the Community edition is free. `docs/WEB_SERVICE_ROADMAP.md` records the
product scope as a small set of known clients, which does not require a client framework.

### 5.4 Orchestration

`fly.toml` already separates a public `web` process from a private `worker` process that drains
the arq queue, and machines start on demand. Heavy Monte Carlo work can scale out by adding worker
machines. Kubernetes adds cluster operation with no requirement that the current topology fails to
meet. Measure the Monte Carlo fan-out first.

### 5.5 Polars

pandas is capped below 3.0 until a migration verified against the KPI oracles is done (#593). An
engine-wide move to Polars would be a rewrite of every dataframe path with canon byte-identity at
stake, for no measured benefit. A new hourly module can use NumPy arrays directly.

### 5.6 Jurisdiction and technology packs, not tables

`docs/FEASIBILITY_REPORT_CONTRACT.md` (DBAY-FRC-001) already defines how the platform becomes
multi-jurisdiction: each jurisdiction and technology is a versioned pack declaring its
identifier, owner, effective and review dates, supported scope, sources, schema, tests,
limitations and review records, with a state of `unsupported`, `supported` or `assured`, and no
silent inheritance of Sri Lankan rules. A `Tax_Regimes` table holding rates and schedules without
statute, effective date and review would bypass every one of those controls. The same contract
lists "authorize a Python or native-language rewrite" among its non-goals.

## 6. Fit with the governing rules

| Rule | Conflict with the plan as written | Reconciliation |
|---|---|---|
| `DELIVERY-01` | Five phases over twenty weeks is a whale | Decompose into dolphins, each green and reversible (section 8) |
| `REFACTOR-01` to `REFACTOR-04` | A rebuild with no migration path | Strangler-fig migration: move, shim, update, deprecate |
| `TEST-01` | A rewritten engine has no oracle except the engine it replaces | Keep the current engine as the reference; each finance change answers to an independent oracle |
| `DOC-02` | Phases 3 and 4 move IRR, DSCR and NPV | `VERSION`, `CHANGELOG.md` and regression pins per KPI-moving dolphin |
| `ARCH-01`, `FRAMEWORK-02` | Rules and curves in database tables | Configuration in YAML, validated strictly before use |
| `FRAMEWORK-03`, `ARCH-04` | A new backend risks a second set of result types | Results through `analytics.contracts_v14` and `evaluate_with_overrides()` |
| `ARCH-02`, `R7` | A rewrite risks a second IRR and NPV implementation | IRR, XIRR and NPV stay in `finance/irr.py` |
| `DATA-01`, `DOC-03` | Tax and rate data without sources | Sourced packs, uncertainty marked |
| `MRM-01`, `MRM-02` | Mutable inputs | Seeds recorded; content-addressed inputs |
| `RECRUIT-01` | No review model | Finance dolphins are `R3_CONSEQUENTIAL`; each needs its review chain before merge, as #1232 shows |
| DBAY-FRC-001 | "Rewrite" is a stated non-goal | Extend through packs |
| #1110 `HOLD` | None of the plan lifts it | Remediation of the findings in section 7 is on the path to lifting it; a new platform is not |

## 7. Overlap with the audit programme (#1110)

The plan's most valuable content is in Phases 3 and 4, and it coincides with open findings of the
August 2026 audit. Every finding below has `hold_effect: blocks_board_lender_release` in the
current-main overlay.

| Finding | Severity | Overlay state | Plan item |
|---|---|---|---|
| P3-COV-03 Large scheduled-maturity balance with partial cash sweep | critical | open, not examined | 32 |
| P2-F4-01 DSCR and sizing on unlevered tax | high | open, not examined | 26 |
| P2-F5-01 FX curve anchored at close, indexed to operating years | high | implementation delivered, review pending | 19 |
| P2-F5-02 LKR tranche modelled as USD-denominated | high | blocked on external evidence | 18, 19, 20 |
| P3-COV-05 DSRA and payment support mischaracterised | high | open, not examined | 30 |
| P3-COV-06 No modelled structural FX mitigation | high | open, not examined | 20 |
| P3-MCFX-01 Canon omits calibrated FX | high | open, not examined | 19 |
| P5-WIND-003 P50 to P90 formula stated as exact | high | open, not examined | 12, 34 |
| P4-COMPLEX-01 Debt engine is one 327-line function | high | deferred, not examined | Phase 1 intent |
| P2-MC-SENS-02 DSCR breach-probability interval uses a naive strict comparison | high | implementation delivered, review pending | 34 |
| P2-F2-02 Half-year bridge charges a full-year coupon | medium | open, not examined | 12 (Lane A3) |
| P2-F3-01 Waterfall clamps a debt-service shortfall to zero | medium | open, not examined | 32 |
| P2-F5-03 Monte Carlo does not vary FX drift | medium | open, not examined | 34 |
| P3-COV-08 No major-maintenance reserve or multi-tier lock-up | medium | open, not examined | 31, 32 |
| P2-F4-04 Interest deduction uncapped | low | open, not examined | 24 |
| P2-F3-05 `loss_carryforward_years = 0` means two things on two construction paths | low | open, not examined | 22 |

The register's own dependency for P2-F5-02 states that authenticated lender and legal evidence of
debt denomination, repayment numeraire and transaction terms is required before implementation.
The plan's dual-currency and swap phase cannot be designed correctly before that evidence exists.

## 8. Recommendation and proposed sequencing

Do not adopt the plan as the Sprint 21 plan. Adopt its goals selectively, expressed as dolphins
mapped to existing seams and to the findings above. Proposed for the owner's decision:

**Lane A — continue Sprint 20 (sub-annual finance).**

- A2 (#1231): complete review cycle 3 and merge under its stated merge-boundary condition.
- A3: sub-annual debt service and DSCR series, with the two items the reviewers deferred to it
  (BESS augmentation smoothing; registering the new configuration keys). Relates to P2-F2-02.
- A4: allocation rule for tax and loss carry-forward.

**Lane B — bankability structure, one finding per dolphin.**

| Dolphin | Finding | KPI effect | Risk class |
|---|---|---|---|
| B1 Levered-tax CFADS basis | P2-F4-01 | Moves CFADS, LLCR, PLCR (register) | `R3` |
| B2 Waterfall shortfall treatment | P2-F3-01 | None on canon (register) | `R3` |
| B3 Major-maintenance reserve and multi-tier lock-up, default off | P3-COV-08 | None while off | `R2` |
| B4 DSRA structure options including letter of credit | P3-COV-05 | Only when configured from evidence | `R3` |
| B5 Financial-cost limitation | P2-F4-04 | Only when configured | `R3` |
| B6 Maturity balance and partial sweep: analysis first | P3-COV-03 | To be established | `R3` |

**Lane C — evidence, no code.**

- F5-02 lender and legal evidence through the existing intake (#1150).
- The Inland Revenue Act No. 24 of 2017 and its amendments, ingested through the governed
  MarkItDown workflow (`R26`), for B5.
- Reserve requirements (DSRA months and form, maintenance reserve) from the term sheet and the LTSA.
- Measured wind data (#1290).

A realistic Sprint 21 core is Lane A (A2, A3), B2 and B3, each designed to leave the committed
canon unchanged or to default to off, and the Lane C evidence requests; B1 is the one KPI-moving
dolphin worth preparing, with its oracle.

**Deferred, each gated by a decision.**

- An hourly dispatch layer on the period grid, after A3 and A4.
- SoH-triggered BESS augmentation; C-rate calibration to OEM warranty curves.
- Single-axis solar tracking.
- A hydro technology pack.
- A second jurisdiction pack with its depreciation methods, interest-limitation mode and credits (D3).
- A formula workbook as an independent oracle (D7).
- Floating-rate debt and interest-rate swaps, if the term sheet requires them.
- Per-line native-currency inputs, after F5-02.
- Database, client framework and orchestration changes (D2).

## 9. What the plan gets right

The evaluation is not a rejection of the plan's direction. The plan correctly identifies:

- that sub-annual resolution matters for bankable coverage ratios, which Sprint 20 Lane A is
  building;
- the absence of an interest limitation, a maintenance reserve, a correctly characterised DSRA
  and structural FX mitigation, which the audit found independently;
- native-currency inputs per cost line, which go beyond the current LKR and USD structure;
- hydro and solar tracking, which are genuine technology gaps;
- threshold-triggered BESS augmentation, a sensible refinement of the scheduled model;
- lender demand for auditable spreadsheet models, which an independent formula model can meet
  while also serving as a `TEST-01` oracle;
- separation of heavy compute into scalable workers, which is the current architecture.

## 10. Decisions required from the owner

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Sprint 21 direction: finding-led bankability work plus Lane A, or the plan's rebuild | Finding-led work plus Lane A |
| D2 | Web product scope: a small set of known clients, or a multi-tenant service | Keep the current scope until a client need is stated; D2 alone decides database, client framework and orchestration |
| D3 | A second jurisdiction: whether, which, and who owns its sources and review | Decide before any tax or depreciation generalisation |
| D4 | Keep the plan text public in the corpus, or reduce it to manifest-only before merge | Keep public; it contains no restricted content |
| D5 | Recruit the `RECRUIT-01` review pair for this pull request | Required before merge |
| D6 | Confirm the sprint number | "Sprint 21" |
| D7 | Whether a lender-auditable formula workbook is wanted | If yes, scope it as an independent oracle |

## 11. Assumptions

- The next sprint is Sprint 21. The last numbered sprint in history is Sprint 20 (Lane A,
  #1225 and #1231).
- The plan text as received is the text the owner intended to supply.
- Audit findings are cited at their register state; current-main state is as the overlay records
  it, and most rows there are not yet re-examined.
- External law, rates and licensing are as found on 26 September 2026 in the sources listed in the
  research notes.

## 12. Limitations

- One coordinator produced this evaluation; it has not been independently reviewed. Under
  `RECRUIT-01` it needs a domain reviewer (project finance and renewables) and a separate
  assurance reviewer before it can steer work.
- Two external points rest on secondary sources: the Sri Lankan section 18 mechanism (primary text
  not ingested) and the United Kingdom allowance details (`gov.uk` was blocked by the session's
  network policy).
- No performance profiling was done. Statements about compute rest on documented timings and
  arithmetic.
- Evidence held on the owner's workstation or in the private `DutchBay_RAG` repository was not
  accessible.
- The "exists" assessments rest on reading code on `main`, not on re-running the full suite; they
  say nothing about bankability or review status.
