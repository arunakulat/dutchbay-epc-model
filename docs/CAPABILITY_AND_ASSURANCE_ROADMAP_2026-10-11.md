# DutchBay capability and assurance roadmap

**Control date:** 11 October 2026, 11:05 UTC

**Repository basis:** `main` at `f3b674c873b85be629f33ae21a30a6cd74361726` (tree `fc6c581d1868b6a601c8d8955d8948b3e443b528`); 1,554 commits; `VERSION` 15.6.1.

**Purpose:** a prioritized implementation and evidence queue for the existing DutchBay EPC model. This is planning analysis, not a change to a model input, financial result, issue disposition, release, or `HOLD`.

## 1. Decision in one page

Continue the existing contract-driven Python finance platform. Give the next capability budget to the parts that can alter a lender case or resolve a known evidence gap: period-correct CFADS and debt service, debt and reserve findings, site resource evidence, authenticated grid inputs, and contract-specific hybrid dispatch. Keep hourly physics in resource and dispatch producers; aggregate audited energy and cash events onto the finance payment grid. Add jurisdictions, tenant infrastructure, and a second workbook only when their source and user decisions are in hand.

The repository has serious software capability, but software maturity is not the same as project evidence or professional reliance. The latest published artifact is v15.6.1. [Issue #1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) is OPEN with a Board/lender circulation `HOLD`; the separate F-5 bar on quarterly CFADS and intra-year DSCR covenant use also stands. Neither this roadmap nor any implementation PR changes those states.

The 26 September [owner platform plan](source_materials/platform_strategy_2026/PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt) remains a source of goals, not an adopted 20-week implementation specification. The [Sprint 21 evaluation](SPRINT_21_BOOTSTRAP/SPRINT_21_EXECUTIVE_SUMMARY.md) records the owner's decisions to use finding-led work and Lane A (D1), serve known clients now while planning for multi-tenancy (D2), keep the plan public (D4), and follow repository review controls (D5). The second jurisdiction (D3), sprint number (D6), and independent formula workbook (D7) remain open choices. This roadmap does not decide them.

The [global feasibility report contract](FEASIBILITY_REPORT_CONTRACT.md) (`DBAY-FRC-001`) is the longer-range product target: a traceable assessment spanning technical, resource, power-system, geospatial, environmental, social, regulatory, commercial, financial and risk matters across formats. It explicitly says implementation conformance is incomplete and requires jurisdiction support states. It is a better acceptance frame for eventual platform completeness than a list of libraries or screens. The proprietary [evaluation and audit licence](../LICENSE) also means public code visibility cannot be interpreted as third-party commercial deployment rights.

### First delivery sequence

1. Resolve the five queued PRs through their existing owners and review lanes; remove install-incompatible dependency proposals from the active merge path only on an explicit recorded disposition. In parallel, optimize the handover resolver under [#1342](https://github.com/arunakulat/dutchbay-epc-model/issues/1342), since this cloud run took about 47 seconds against a 60-second governance threshold.
2. Finish A3/A4 period and event-calendar semantics and the F-03 schema gate. Keep F-5 in force until independent financial review supports a specific use of quarterly figures.
3. Address the highest-impact finance findings as separate reversible PRs, starting with maturity/partial-sweep analysis and levered-tax CFADS basis. Request transaction, reserve, tax, mast, and feeder evidence concurrently; those requests must not be converted into assumed values.
4. Build the operational evidence path already sequenced in [#1330](https://github.com/arunakulat/dutchbay-epc-model/issues/1330). Use its results to challenge pre-construction AEP when real post-COD data exist.
5. Prototype a chronological hybrid dispatch contract only after selecting an eligible revenue arrangement. Validate energy conservation, state of charge, degradation and cash-flow aggregation independently before proposing canonical finance use.

### Working queue at this cutoff

Priority is based on consequence, dependency and evidence availability, not on the age of a PR. “Owner” below names the accountable role or existing issue, not a new person appointed by this document.

| Work | Priority | Prerequisite | Accountable path | Observable exit |
|---|---|---|---|---|
| PR queue and incompatible pins | Immediate | Current PR heads and owner/review records | Existing PR coordinators | Each of five PRs has a reviewed merge or recorded blocked/closed disposition. |
| A3/A4 and F-03/F-5 | P0 | #1231 source and covenant terms | Finance writer and independent finance review | Period bridge/event/calendar tests and exact F-5 disposition. |
| Audit-critical debt/tax | P0 | Finding-by-finding reproduction | #1110 finance workstream | Independent oracle and KPI delta per corrective PR. |
| Transaction, resource and feeder ingress | P0 | Issuer documents and use authority | #920, #1075 and source owners | Reviewed, immutable evidence packages or explicit unresolved gaps. |
| Controlled audit successor | P0 | Recovery, registers and independent reviews | #1110 and #1158–#1162 | The issue's own release checklist and explicit final decision. |
| Real-feeder QSTS decision | P1 | #1075 → #1076 | #1078 | Engineering-validated study, finance oracle and owner decision. |
| Wind/solar evidence bridge | P1 | Site measurements, equipment and loss sources | Resource specialists | Independently reviewable AEP and uncertainty case. |
| Post-COD operations | P1 | Frozen D1 contract | #1330 D2 → D5 | Reconciled operational AEP and EYA bridge. |
| Contract-specific hybrid dispatch | P1 | Revenue/dispatch right and chronological inputs | BESS/finance specialists | Conserved-energy pilot and independent finance oracle. |
| Versioning, delivery friction and report parity | P2 | Current consumer inventory | Documentation, runtime and assurance owners | Clear user route, measured process improvement, truthful output labels. |
| Jurisdiction, formula workbook and scale changes | P3 | D3/D7 and measured demand | Product owner and specialists | Separate scoped decisions and evidence-backed acceptance. |

## 2. What the 11 October assessment gets right, and what changes the queue

| Assessment statement | Reconciliation against current source | Planning consequence |
|---|---|---|
| Finance, wind, solar, BESS, sensitivity, grid, reports, API and jobs are implemented | The named packages and canonical Hydra/evaluation route are present. `pyproject.toml`, `README.md`, `finance/`, `analytics/`, `wind_resource/`, `solar_resource/` and `app/` support the software inventory. | Extend existing contracts and consumers instead of creating a second platform. |
| Core finance is high maturity | The code has multi-tranche sizing, fee-aware sculpting, tax, FX, covenants and regression guards. [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110), [#962](https://github.com/arunakulat/dutchbay-epc-model/issues/962), and the [Sprint 21 analysis](SPRINT_21_BOOTSTRAP/SPRINT_21_COMPREHENSIVE_ANALYSIS.md) still identify finance-material findings. | Treat “high” as software depth, not a completed lender-grade assurance finding. Fix each financial issue with an independent oracle and a before/after KPI disclosure. |
| Sub-annual cash flow now exists | [#1231](https://github.com/arunakulat/dutchbay-epc-model/pull/1231) merged A1/A2. `finance/subannual_rows_v14.py` allocates annual rows; it does not recalculate within-year tax, FX or discrete augmentation. The [10 October handover](SESSION_HANDOVER_2026-10-07_MERGE_COORDINATION.md) carries F-5 and F-03 to A3/A4. | The first finance work is period semantics and event timing, not a new 8,760-hour debt engine. |
| Grid is substantial but advisory | `analytics/grid/` and the [screening scope](knowledge_base/grid_screening_scope.md) implement QSTS and other screens. `finance/self_curtailment_v14.py` already has a default-off guarded path for self-curtailment. Real/site feeder ingress, execution and finance decision remain open in [#1075](https://github.com/arunakulat/dutchbay-epc-model/issues/1075), [#1076](https://github.com/arunakulat/dutchbay-epc-model/issues/1076) and [#1078](https://github.com/arunakulat/dutchbay-epc-model/issues/1078). | Complete and validate the real evidence chain; avoid describing finance wiring as absent or treating an in-house screen as a utility-accepted study. |
| Wind producer is mature | The ERA5/Weibull/PyWake pipeline and frozen export are present. The September [met-mast 617725 record](source_materials/met_mast_617725_2025/README.md), merged through [#1290](https://github.com/arunakulat/dutchbay-epc-model/pull/1290), covers about 232 days, has unresolved site/instrument/timezone facts, and is not an annual or lender-ready resource assessment. | Separate software validation from on-site measurement, MCP, independent energy-yield review and site transfer. |
| BESS lacks deep dispatch | `finance/bess_revenue.py` already has capacity-charge and energy-tariff models, separable calendar/cycle fade and augmentation capex in CFADS. `finance/bess_lcos.py` explicitly uses fixed cycles and no simulated dispatch. | Preserve the existing degradation route. Add chronological dispatch only against a contract that pays for it; integrate actual throughput, SoH and augmentation with a single conserved energy ledger. |
| Governance overhead may crowd out capability | Recent history includes release, handover, provenance, dependency and CI work; that observation is true. Commit counts alone do not measure useful velocity or the cost of preventing bad evidence. | Instrument delivery time and rework by workstream, then remove duplicative state and automate repeated checks without weakening the evidence gates. |
| v14 labels conflict with 15.x version | `VERSION` and `pyproject.toml` say 15.6.1; canonical entrypoints and many modules retain `_v14` identifiers. | Publish one reader-facing explanation: 15.6.1 is the product release; v14 is the stable model/API contract generation. Rename imports only with a migration and compatibility case. |
| Full hybrid lender package is incomplete | The grid study, lender transaction evidence, resource evidence, hybrid dispatch economics and final #1110 release gates are separate outstanding controls. | Define completeness by evidence and accepted contract scope, not by counting available modules. |

The assessment's maturity grades are useful directional judgments, but they are not measured release grades. This document uses source-verified states—implemented, incomplete, blocked on evidence, or decision needed—in place of a single overall “bankability” score.

## 3. Live PR queue and immediate handling

The following is the complete open PR list retrieved at the control date. Status is mutable; re-read the exact head, required checks, review and merge state at the next action. “Green” below means reported jobs succeeded, not independent semantic review or delivery authorization.

| PR | Current head and observed state | Required next action |
|---|---|---|
| [#1343](https://github.com/arunakulat/dutchbay-epc-model/pull/1343), `mpmath` Dependabot ignore | `d14d2691`; draft; CI reported success. It inserts an ignore for major/minor updates into `.github/dependabot.yml` and a changelog fragment. The PR records a review request and an existing owner interpretation of review count. | Finish the recorded independent review and reconciliation; resolve draft/final-head state through the PR's coordinator. It prevents new incompatible proposals but does not repair #1344. |
| [#1344](https://github.com/arunakulat/dutchbay-epc-model/pull/1344), `mpmath` 1.3.0 → 1.4.1 | `f3241d1e`; blocked; install-dependent checks fail. The governed environment's installed `sympy 1.14.0` metadata requires `mpmath<1.4,>=1.1.0`. | Do not treat this as a code regression or merge candidate. Track a compatible SymPy/`mpmath` pair or record an owner-approved close/deferral. Do not “fix” it by loosening the lock. |
| [#1345](https://github.com/arunakulat/dutchbay-epc-model/pull/1345), `charset-normalizer` 3.5.1 → 3.5.2 | `4e2e69e7`; one lock line; checks green, no submitted review observed. | One independent dependency review under the owner's 7 October PR-specific direction; refresh after intervening merges and merge only on current required CI/review conditions. |
| [#1346](https://github.com/arunakulat/dutchbay-epc-model/pull/1346), `bitarray` 3.10.1 → 3.11.0 | `9f391907`; one lock line; checks green, no submitted review observed. | Same one-review and exact-current-head procedure as #1345; assess installed consumer compatibility, not only test count. |
| [#1326](https://github.com/arunakulat/dutchbay-epc-model/pull/1326), `llvmlite` 0.49.0 → 0.50.0 | `876fa6dd`; behind and failing install-dependent checks. Installed `numba 0.67.0` requires `llvmlite<0.50,>=0.49.0dev0`. | Wait for a compatible `numba` release or record an owner-approved close/deferral. Preserve [#1229](https://github.com/arunakulat/dutchbay-epc-model/issues/1229) as a separate short-circuit compile/SIGSEGV issue; this bump does not prove its repair. |

The queue is dependency maintenance, not the capability roadmap itself. Do not let incompatible lock proposals consume finance or evidence implementation capacity. The current lock remains internally valid and the governed Python 3.12 environment passed its 311-pin contract at this cutoff.

## 4. Delivery contract for every roadmap item

Each item below is a candidate small, complete PR, not a lease to edit every named file. Start from the then-current `origin/main` in an owned worktree. Before implementation: record the bounded subject, active writer, exact file allowlist, source hierarchy, semantic risk class, and independent oracle. Freeze the implemented object and obtain the `RECRUIT-01` reviews applicable to that class. A required specialist or owner decision remains a genuine gate. Submit command/result receipts under `VERIFY-01`; run the relevant focused checks and GitHub required checks on the current PR head. Finance behavior changes need the `TEST-01` independent oracle, an explicit KPI delta, `VERSION` and `CHANGELOG.md` treatment under `DOC-02`, and no unreviewed canonical rebaseline. QSTS execution claims need the exact-head GitHub Grid Study under `TEST-05`.

An implementation can be merged while a programme `HOLD` persists. A merged PR changes software state only; it does not itself create a resource assessment, utility acceptance, lender sign-off, audit release, or Board circulation authority.

## 5. Prioritized, dependency-aware to-do

### P0 — restore truthful near-term financial and evidence boundaries

#### P0.1 — Complete A3/A4 and the F-5 exit evidence

**Current basis.** `finance/period_grid_v14.py` defines the operating grid. `finance/subannual_rows_v14.py` allocates annual flows; year-1 bridge service, tax timing and discrete BESS augmentation are not yet an independently computed quarterly waterfall. The [10 October handover](SESSION_HANDOVER_2026-10-07_MERGE_COORDINATION.md) records F-03 and F-5 explicitly.

**Dolphins.** (a) Register and fail on unsupported `cashflow.resolution` and `cashflow.within_year_profile` during v14 preflight, with a negative control (F-03). (b) Define an event calendar for bridge interest/service, capex, tax and working-capital dates; reconcile each event and each period to the annual totals without moving the committed annual canon in default mode. (c) Align debt service, CFADS and DSCR on the same period index with independent analytic cases for a bridge period, a lumpy quarter and a no-event year. (d) Document the A4 tax/LTCF allocation treatment and which rows are allocated versus computed. Review any proposal to cite quarterly figures for covenants against the exact F-5 condition.

**Acceptance.** A negative test rejects bad resolution/profile at preflight; flow sums and balance endpoints tie to annual records; quarter-specific stress tests find an intra-year trough and a discrete-event dip; period labels and units are unambiguous; independent finance review states which figures may be used. F-5 stays in force until its own controlling reviewer/authority path records the change.

#### P0.2 — Adjudicate audit-critical debt and tax behavior one finding at a time

**Current basis.** The [controlled #1110 queue](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) and [Sprint 21 audit map](SPRINT_21_BOOTSTRAP/SPRINT_21_COMPREHENSIVE_ANALYSIS.md) identify P3-COV-03 (scheduled-maturity balance with partial sweep), P2-F4-01 (unlevered-tax CFADS sizing), P2-F3-01 (shortfall clamp), P3-COV-05 (DSRA/payment support) and P3-COV-08 (maintenance reserve/lock-up). The debt engine already sculpts against DSCR; a replacement sizing engine is not indicated.

**Dolphins.** First reproduce P3-COV-03 with a small closed-form debt schedule and define the contractual maturity disposition before changing code. Then correct P2-F4-01 with an independent tax/debt oracle and quantify changes to DSCR, LLCR, PLCR, IRR and debt capacity. Handle shortfalls, DSRA form/funding, and MRA/lock-up separately. A DSRA or MRA requirement needs authenticated term-sheet/LTSA support; the six-month scenario field alone does not establish cash-funding terms. Keep F5-01 and evidence-dependent F5-02 on distinct rollback surfaces.

**Acceptance.** Every finding has a before/after reproduction, exact affected scenarios, source basis, independent oracle, impact disclosure and trace to its register; one fix cannot silently close another. No synthetic term sheet becomes lender evidence. The audit register and #1110 release checklist remain the authority for final programme disposition.

#### P0.3 — Ingest the missing transaction, tax, wind and feeder evidence

**Current basis.** [#920](https://github.com/arunakulat/dutchbay-epc-model/issues/920) and #1110 require lender/legal terms for debt denomination, repayment numeraire, reserve structure and F5-02. The [met-mast package](source_materials/met_mast_617725_2025/README.md) is partial and not site-verified. [#1075](https://github.com/arunakulat/dutchbay-epc-model/issues/1075) is externally blocked on real POC feeder material and use authority. The Sri Lankan interest-limitation primary text has not been adopted into a source-backed implementation.

**Dolphins.** Maintain four independent evidence requests: (1) executed lender/PPA and legal terms, including currency, hedge, DSRA, MRA, payment security and covenant dates; (2) applicable Inland Revenue Act text, amendments, effective dates and tax opinion for the proposed limitation; (3) mast metadata, calibration/maintenance, raw completeness, site identity and representativeness, longer seasonal coverage, independent MCP/EYA review; (4) issuer-authorized feeder topology, POC, impedances, source equivalent, time-series, controls and OEM model limits. Register every raw value, location, precision, limitation and publication right under `DATA-01`.

**Acceptance.** An independent source reviewer can reproduce provenance and identify unresolved fields; the package fails closed on missing, inconsistent, replaced or unauthorized material. A request for evidence is completed as a request when sent, but a modelling dependency remains blocked until usable evidence arrives and is reviewed. Never relabel a synthetic fixture as site evidence.

#### P0.4 — Close the #1110 audit control path without claiming a release early

**Current basis.** #1110 has unchecked recovery, findings, source, reproduction, architecture, finance, corrigendum and final review gates. [#1158](https://github.com/arunakulat/dutchbay-epc-model/issues/1158)–[#1162](https://github.com/arunakulat/dutchbay-epc-model/issues/1162) hold specific independent tasks.

**Dolphins.** Complete clean-room recovery and external manifest attestation; reconcile all 111 findings, 42 source claims and 72 architecture pointers against their exact historical and current objects; execute or explicitly disclose each reproduction that remains required-not-run/unavailable; regenerate the synthesis from controlled registers only after the underlying evidence has been reconciled. Commission independent final calculation, citation, layout, accessibility and release review.

**Acceptance.** The exact #1110 release checklist is satisfied and a separately authorized reviewer records an explicit `RELEASED` disposition before Board/lender circulation. This roadmap intentionally sets no substitute release rule.

### P1 — make resource, grid and hybrid pathways evidence ready

#### P1.1 — Complete authenticated real-feeder QSTS and finance decision

**Dependency.** P0.3 feeder package → [#1075](https://github.com/arunakulat/dutchbay-epc-model/issues/1075) → [#1076](https://github.com/arunakulat/dutchbay-epc-model/issues/1076) → [#1078](https://github.com/arunakulat/dutchbay-epc-model/issues/1078).

**Dolphins.** Verify the externally pinned feeder manifest and study inputs; execute the site-representative full-horizon study with convergence and energy-accounting receipts; obtain qualified engineering review; produce a before/after finance oracle showing gross energy, delivered energy, deemed-paid and self-curtailed energy, revenue, NPV, IRR and minimum DSCR. Deemed-paid and plant self-curtailment must remain separate. Only after owner sign-off should a final small scenario PR consider `finance_wiring.enabled=true` and an evidence-supported canonical eligibility flag. Maintain the in-house screen's `bankable=false` classification absent a separately accepted utility/OEM study.

**Acceptance.** Synthetic/model-only controls fail to pass as real; Grid Study succeeds on the exact PR head; accounting identities and KPIs reconcile; the report exposes all evidence and study limits; the decision records either enablement or an explicit decision to stay default-off.

#### P1.2 — Turn wind and solar outputs into independently challengable energy cases

**Current basis.** Wind and solar producers, frozen exports and adapters exist (`wind_resource/`, `solar_resource/`). The 617725 mast record cannot alone establish a long-term site AEP. Solar software maturity likewise does not prove site irradiance, losses or contractual energy yield.

**Dolphins.** For wind, complete site identity, measurement QA, full-season coverage, long-term reference selection, MCP transfer, wake/electrical/availability loss accounting and independent P50/P75/P90 uncertainty review. For solar, pin measured or qualified irradiance/TMY provenance, module and inverter data, temperature/soiling/clipping/availability assumptions, and independent yield comparison. For both, preserve frozen input and output hashes, explicit units, uncertainty contributors, adapter `validate` versus `overwrite` behavior, and a negative control for stale or mismatched exports.

**Acceptance.** A second analyst can derive or challenge the energy bridge from source objects; resource-to-finance totals reconcile; missing site evidence is surfaced as a limitation rather than upgraded by a successful pipeline run. IEC 61400-12-1 requires measured power curves and derived energy figures to include uncertainty assessment; apply the actual relevant standard and contract scope rather than treating a generic source ID as certification of this project's AEP ([IEC catalogue](https://webstore.iec.ch/en/publication/68499)).

#### P1.3 — Deliver the post-COD operations sequence already defined in #1330

**Current basis.** `analytics/operational/contracts.py` and [#1336](https://github.com/arunakulat/dutchbay-epc-model/pull/1336) delivered the D1 frozen evidence contract; [#1332](https://github.com/arunakulat/dutchbay-epc-model/issues/1332)–[#1335](https://github.com/arunakulat/dutchbay-epc-model/issues/1335) remain open. OpenOA's `PlantData` design distinguishes SCADA, revenue meter, tower, status, curtailment, asset and reanalysis data; its EYA gap analysis is a methodological comparator, not evidence of project acceptance ([OpenOA types](https://openoa.readthedocs.io/en/latest/api/types.html), [analysis API](https://openoa.readthedocs.io/en/latest/api/analysis.html)).

**Dolphins.** D2 normalization with time-zone, duplicate, missing-data and unit QA; D3 operational AEP with explicit electrical, availability, curtailment and wake loss attribution; D4 EYA-to-actual bridge and a default-off finance proposal; D5 climate-risk disclosure only from source-supported metrics. Do not overwrite the original EYA or create a retrospective “corrected canon” without a new governed decision.

**Acceptance.** Every data cut has immutable identity, coverage and exclusions; energy/loss attribution reconciles; negative controls fail on malformed time-series; the before/after EYA bridge separates measurement, weather, availability and method effects; any finance proposal has its own R3 oracle and authorization.

#### P1.4 — Build one contract-specific hybrid dispatch pilot

**Decision gate.** First choose a project and contractual revenue basis: CEB-controlled capacity-charge BESS, solar-to-night-peak energy tariff, or a separately evidenced merchant/tolling arrangement. The existing capacity-charge model is controlled by CEB dispatch and does not justify adding merchant arbitrage revenue. The [NREL SAM battery documentation](https://sam.nrel.gov/battery-storage/) distinguishes manual schedules from optimized dispatch and models degradation/replacements; it is a design comparator, not a DutchBay tariff source.

**Dolphins.** (a) Define an immutable chronological input contract: wind/solar generation, price or dispatch instruction, shared POC cap, outages, charge source, efficiency, initial/final SOC, minimum/maximum SOC, power and energy ratings, applicable tariff/LD terms. (b) Build a deterministic feasibility simulator with an hourly energy balance and no optimization claim. (c) Add a small independent linear or mixed-integer reference for one eligible tariff, with prevention of simultaneous charge/discharge and a transparent objective. (d) Link realized equivalent full cycles to existing SoH and augmentation treatment and aggregate revenue, charging cost and capex to annual or approved sub-annual cashflow periods. (e) Compare against do-nothing and no-BESS baselines, and stress tariff, RTE, degradation, outages and terminal SOC. A stochastic or look-ahead optimizer comes only after this deterministic contract has been validated.

**Acceptance.** Every MWh entering the ledger exits as delivered energy, stored-energy change or a named loss; no wind/solar/BESS or POC energy is double counted; SOC and power constraints bind in hostile cases; the independent solver/reference and finance oracle agree on small instances; dispatch/revenue rights and source dates are documented; default-off cases are unchanged. Do not present an optimized merchant value for a contract that grants no merchant dispatch right.

#### P1.5 — Cover project feasibility outside the Python finance calculation

**Current basis.** `DBAY-FRC-001` already names site rights/permits, environmental and social matters, procurement/cost basis, grid and construction interfaces as report sections with evidence and review grades. A mathematically sound debt model cannot resolve land title, permits, stakeholder impacts, EPC exclusions, insurance or utility acceptance. The [IFC Performance Standards](https://www.ifc.org/en/insights-reports/2012/ifc-performance-standards) and [wind EHS guidance](https://www.ifc.org/en/insights-reports/2015/publications-policy-ehs-wind-energy) are general primary comparators; project law and adopted lender conditions control the actual case.

**Dolphins.** Inventory the applicability and evidence state of every `DBAY-FRC-001` section for one bounded project case; link issuer-signed land, permits, grid connection, EPC/O&M/LTSA, insurance, tax/legal and E&S records to the report contract; reconcile priced and unpriced scope to capex/opex and contingencies; record professional and authority owners for each unresolved topic. Keep confidential evidence in its governed location and publish only authorized summaries/digests.

**Acceptance.** Report output identifies each section as run, limited, unsupported or not applicable with evidence and reviewer basis. Cost and construction interfaces reconcile to the finance input manifest. An absent ESIA, consent, legal opinion or utility study is visible and caps the claimed completeness; a successful model run does not fill it.

### P2 — improve lender usability and reduce change cost

#### P2.1 — Make the model and product versions legible

**Dolphin.** Add one versioning paragraph and a supported execution map to `README.md`: product release 15.6.1, current v14 contract generation, canonical single-scenario Hydra route, batch route, frozen resource adapters, advisory grid boundary, and where result schemas are versioned. Link existing detailed docs rather than repeating them. Inventory genuinely duplicate APIs and frozen-export routes with their consumers and removal conditions before a rename.

**Acceptance.** A new reader can pick the supported entrypoint and tell a release number from a contract identifier. Existing imports and historical run manifests remain interpretable. A naming-only document fix must not be described as a v15 model migration.

#### P2.2 — Measure and simplify governance friction

**Dolphins.** Optimize [#1342](https://github.com/arunakulat/dutchbay-epc-model/issues/1342) before the resolver's canonical-corpus runtime crosses 60 seconds; preserve its adversarial history/inventory checks and add a performance receipt. Then instrument four weeks of PR elapsed time (writing, review, CI, merge), rework reason, review findings, and delivered capability/evidence outcomes. Identify duplicated factual statements that can be replaced with a single canonical pointer or generated view. Resolve [#1270](https://github.com/arunakulat/dutchbay-epc-model/issues/1270) where the R10 hook claim differs from the active pre-commit set, and evaluate [#1183](https://github.com/arunakulat/dutchbay-epc-model/issues/1183) on whether audit-image CI should be required. Avoid changing gates on the basis of commit-type counts alone.

**Acceptance.** Resolver output/order/failure semantics are unchanged and runtime is measured below threshold in the canonical environment; the cycle-time report shows a baseline and at least one safe, quantified reduction in duplicate work. No source-provenance, exact-object review or independent oracle is silently removed.

#### P2.3 — Strengthen report and workbook reliance boundaries

**Dolphins.** Trace every lender report, HTML/PDF export, API payload and executive workbook to a common scenario/run/evidence identity and explicit units. Reconcile the format renderers to `DBAY-FRC-001`'s canonical report object and section dispositions. Distinguish annual computed, within-year allocated, synthetic grid, site-validated grid and professional/utility-accepted result classes in every consumer. If D7 is approved, prototype a formula workbook as an independent calculation oracle with its own formula lineage and recalculation step; existing values-only exports do not contain formulas to “retain.” Keep accessibility and citation tests targeted to the report's changed surface.

**Acceptance.** A consumer cannot accidentally display allocated quarterly DSCR as approved covenant DSCR or synthetic QSTS as site evidence; HTML, PDF, XLSX, JSON and API surfaces carry the same section/evidence disposition; a formula workbook, if commissioned, is independently calculated rather than a spreadsheet re-expression of the same Python numbers. [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) remains the release gate for Board/lender circulation.

#### P2.4 — Maintain known-client web service; prepare for tenancy with a decision record

**Dolphins.** Continue the current FastAPI/jobs/Fly.io path and make run identity, authorization, idempotency, cancellation, quotas, secret handling and reproducible exports observable for known clients. Use production telemetry to identify the first real scale bottleneck. Specify tenant-isolation and data-residency requirements before selecting PostgreSQL/TimescaleDB, a new frontend or Kubernetes. Treat [#788](https://github.com/arunakulat/dutchbay-epc-model/issues/788) and [#925](https://github.com/arunakulat/dutchbay-epc-model/issues/925) as product epics with demand gates, not instructions to rebuild the backend.

**Acceptance.** A bounded concurrency/load trial shows the existing stack's limiting resource and recovery behavior; any infrastructure PR has a measured need, a migration plan and an isolation test. No architecture choice is justified solely by a generic “institutional-grade” label.

### P3 — conditional expansion after source and product decisions

1. **Second jurisdiction pack (D3):** select a jurisdiction, owner, statute/effective-date corpus, tax/FX/currency assumptions and specialist reviewer. Implement a versioned pack and cross-jurisdiction contract test; do not generalize Sri Lankan rules by renaming fields. Avoid obsolete LIBOR and unidentified “EU WDAT” assumptions from the owner plan. The [Sprint 21 correction](SPRINT_21_BOOTSTRAP/SPRINT_21_COMPREHENSIVE_ANALYSIS.md) supplies the detailed defect list.
2. **Floating-rate debt, hedge and currency extension:** only after F5-02 transaction terms and market availability establish benchmark, tenor, payment currency and hedge rights. Model native-currency cash flows, forecast conversion, hedge premiums and stress with separate unit/currency conservation tests. Preserve F5-01/F5-02 separation.
3. **Hydro or another resource technology:** only after a real project/contract decision. A flow-duration curve alone is not a chronological hourly hydro dispatch profile; require seasonal inflow, environmental flow, head/efficiency and independent yield evidence.
4. **Formula workbook and interactive three-statement interface (D7/D2):** use a workbook as a second oracle if requested, then decide whether an interactive client earns its maintenance and security cost. The existing three-statement report and tie-out checks remain the starting point.
5. **Scale architecture:** benchmark measured workloads before introducing Polars, TimescaleDB, distributed workers or Kubernetes. A 25-year hourly trace is about 219,000 points per variable; it does not by itself prove a database or orchestration requirement. Retain deterministic run identities and financial equivalence as migration invariants.

## 6. Cross-workstream acceptance matrix

| Result being claimed | Minimum evidence before the claim may be made |
|---|---|
| “Software path works” | Deterministic fixture, negative controls, independent small-case oracle, current PR-head CI, limitations. |
| “Site resource estimate” | Site identity, calibrated measurements/coverage, long-term correlation, losses/uncertainty, independent resource assessment and source rights. |
| “Grid loss belongs in finance” | Authenticated real/site feeder package, full-horizon engineering-validated QSTS, contractual deemed-paid/self-curtailed distinction, before/after KPI oracle and explicit owner decision. |
| “Storage value belongs in finance” | Applicable dispatch/revenue rights, chronological energy and SOC ledger, validated degradation/augmentation/availability terms, independent optimization/finance check and downside sensitivity. |
| “Quarterly DSCR can support covenant use” | A3/A4 period and event timing complete, bridge/tax/debt mappings independently reviewed, exact F-5 exit disposition and transaction covenant convention. |
| “Board/lender pack may circulate” | Every [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) release gate and explicit independent `RELEASED` record. |

These are different evidentiary levels. Passing one row never implies a later row.

## 7. Capacity and sequencing rules

Keep one active finance behavior PR, one independent evidence-ingress PR, and one small tooling/documentation PR in the review pipeline at a time, adjusting only when qualified reviewers and source access are available. This is a scheduling proposal, not a new repository rule. Ask the coordinator to report monthly: accepted capability/evidence outcomes, unresolved blockers, PR lead time, review rework, and gates that caught a real defect. Prefer completing an existing issue's next reversible step over opening a parallel epic.

Dependencies that no software task can waive are: authenticated lender/legal terms for F5-02 and reserve/hedge assumptions; measured and site-identified resource inputs for a lender energy case; CEB/NSCC or qualified engineer feeder inputs plus usage authority for real QSTS; and an independent final #1110 release review. Work can proceed on deterministic software fixtures while these are pending, with results labelled accordingly.

## 8. Method, sources and limits

**Repository and live state.** This review read `AGENTS.md`, `CLAUDE.md`, the complete 74-row `go_with_the_flow_rules_v3_0_clean.csv` and its framework rows, all four `RECRUIT-01` modules, the resolver-selected 10 October handover and its 5 October startup record, the owner platform-plan/evaluation records, relevant finance/resource/grid/operations source, and live GitHub PR/issue/release state. The governed Python 3.12 environment passed `check_venv.sh`; the rules bootstrap loaded 74 active rules. `main` was clean and matched `origin/main`. No model run, QSTS, measured-resource assessment, full test suite, release qualification or independent professional review was performed for this planning document.

**External primary comparators, checked 11 October 2026.** [NREL SAM battery storage](https://sam.nrel.gov/battery-storage/) supports distinguishing scheduled/optimized dispatch and degradation/replacement modelling; [OpenOA PlantData](https://openoa.readthedocs.io/en/latest/api/types.html) and [analyses](https://openoa.readthedocs.io/en/latest/api/analysis.html) inform operational data and EYA-gap boundaries; [IEC 61400-12-1:2022](https://webstore.iec.ch/en/publication/68499) describes measured power-curve and uncertainty requirements; [IFC Performance Standards](https://www.ifc.org/en/insights-reports/2012/ifc-performance-standards) and [wind EHS guidance](https://www.ifc.org/en/insights-reports/2015/publications-policy-ehs-wind-energy) show that environmental and social diligence is a separate project-level workstream. None of these sources grants DutchBay a grade or substitutes for local law, transaction contracts, utility requirements or professional review.

**Limits.** The confidential raw met-mast series, lender/legal package, CEB/NSCC feeder/base case, OEM dynamic models, and the owner's Mac-only evidence were not available in this cloud checkout. The live PR queue may change after this cutoff. Historical records were used as pointers and checked against current code or GitHub state where a live claim mattered; their old status snapshots were not copied forward as current facts. The assessment's qualitative maturity labels and “governance dominates delivery” concern remain judgments until measured against a declared baseline.
