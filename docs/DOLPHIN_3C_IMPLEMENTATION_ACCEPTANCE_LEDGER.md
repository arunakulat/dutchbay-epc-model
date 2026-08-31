# Dolphin 3C implementation acceptance and retraining ledger

**Status:** binding addendum for D3C retraining and implementation review; no implementation  
**Historical design:** [`DOLPHIN_3C_RESULT_FACADE_CHARTER.md`](DOLPHIN_3C_RESULT_FACADE_CHARTER.md)  
**Historical disposition:**
[`DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md`](DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md)  
**Execution prerequisite:** accepted and protected-main-merged D3B-1  
**Authority:** engineering implementation boundary only; no grade, professional, lender, Board,
release or deployment authority

## 1. Why this ledger exists

The earlier D3C document reviewed the result-facade contract portion. It did not fully restate the
remaining package-assembly mission and omitted several load-bearing obligations from the original
Dolphin 3 brief. This ledger restores them before a D3C writer receives a SHA-bound lease. It does
not rewrite the hash-bound historical disposition and does not authorize implementation from an
unaccepted D3B working tree.

D3C's first implementation must consume exactly one of each computational input:

1. one exact D3A `ProjectCase`;
2. the matching accepted D3B-0 `EvaluationRequest`; and
3. one immutable accepted D3B-1 execution success or degraded-success outcome.

It must also receive a governed D3C assembly-authority receipt; a structurally valid caller-supplied
`ReportIdentity` is not authority. `EvaluationRequest.request_id` is not a D2 `run_id`, an engine
timestamp is not a `report_id`, and D3C may not mint, alias or infer either identity. Package
construction stops unless the authority receipt is accepted and every reciprocal D2 reference
binds to it.

It must emit one real `FeasibilityReportPackage` as a plumbing proof. It must not rerun the engine,
recompute a KPI, infer evidence, invent a jurisdiction or technology default, claim Golden Path 1,
or render or serve the package.

The first package remains:

```text
achieved_grade = ungraded
package_release.status = hold
```

Issue `#1110`, every evidence/review/release condition and every Board/lender circulation `HOLD`
remain unchanged.

### 1.1 D3C-0 assembly-authority prerequisite

No current D3A/D3B object authorizes all facts required to instantiate a genuine D2 package. Before
the package-assembly writer receives a lease, a separate reversible D3C-0 dolphin must define,
implement, independently review and merge one strict assembly-authority/receipt contract binding:

- exact `report_id`, `run_id`, issue, revision, creation timestamp and the authority source that
  allocated those identities;
- the exact ProjectCase, EvaluationRequest and D3B success content digests;
- the governed runtime/environment/dependency and dirty-worktree receipt needed by the D2 manifest;
- every exact D2 jurisdiction/technology `PackBinding` object or an explicit blocking disposition;
  D3A `support_status=declared` cannot be promoted into D2 pack facts;
- exact bytes, format, MIME type, producer/version, timestamp, source IDs, confidentiality and
  SHA-256 for each annual/debt/curve artifact; deferring D4 payload/section hashes does not waive
  D2 `ArtifactRecord.content_digest`;
- one held, non-reliance distribution control covering the scope's intended audiences/uses without
  release authorization; and
- the actor/source identities used for package orchestration, with no substitution for the four
  unperformed human responsibility roles.

The assembly authority is code-/ledger-owned and selected by stable ID; it is not accepted as an
arbitrary request object. D3C-0 may supply governed inputs, but it may not assemble the twenty
sections, map engine values, grade, release, render or serve a package. If any pack, artifact,
identity, runtime or distribution fact is unavailable, the D3C package remains blocked rather than
constructing mutually consistent but unauthoritative copies.

## 2. Exact package topology and complete register duty

Every produced package must contain exactly the twenty taxonomy IDs in
`config/feasibility_sections.yaml` order. Every section is populated or receives its exact honest
state; no section is dropped because an engine did not produce a value.

The five always-applicable stable IDs are:

1. `executive_investment_thesis`;
2. `project_description_and_structure`;
3. `risk_register_and_mitigations`;
4. `decision_checklist_conditions_precedent`; and
5. `appendices_provenance_audit_trail`.

The six engine-less stable IDs are:

1. `site_land_permits_legal_status`;
2. `construction_logistics_plan`;
3. `environmental_social_summary`;
4. `climate_resilience_assessment`;
5. `risk_register_and_mitigations`; and
6. `decision_checklist_conditions_precedent`.

Engine-less means an empty capability set unless a separately governed non-engine capability
record genuinely applies. It does not mean the section is omitted or `not_applicable`. Section
applicability and capability disposition remain different state axes.

The assembler must construct every D2 register required by `FeasibilityReportPackage`, not merely
the subset named in the contract-only charter. The following registers are load-bearing for the
first package and must be populated when facts exist or supplied as an exact, valid empty register
when the contract permits no fact:

- actor and responsibility;
- pack and capability;
- input, source and output;
- claim and evidence;
- assumption, judgement and derivation;
- limitation and error;
- review finding and review;
- decision;
- reconciliation and validation; and
- distribution.

An empty register is not evidence that a review, decision, distribution authorization or
professional act occurred. D3C must not create a decorative record solely to make a register
non-empty.

Exactly one reconciliation record must exist for each D1 family:

- `project_basis`;
- `energy`;
- `cost`;
- `revenue_tax_currency`;
- `debt`; and
- `non_financial_gaps`.

Each record must use the operands actually compared. `passed` or `failed` needs the reciprocal
section/output identities D2 requires. `not_applicable` is allowed only when that reconciliation
family genuinely has no operands; it cannot hide missing data or an analysis that should have run.

## 3. Human responsibility must remain visibly unperformed

The first package must carry four separate report-scoped `ResponsibilityAssignment` records for
`prepared`, `checked`, `reviewed` and `approved`. When no authorized human has performed the role,
each record must use `status = not_performed`, an exact report/run/section subject binding and a
truthful reason. It must carry no `actor_id`, `performed_at` or `decision_id`.

Software, an AI agent, a test runner, CI, a pull-request reviewer or an engineering merge cannot be
substituted for any of those human roles. D3C cannot infer a performed responsibility from the
presence of an actor record.

## 4. Engine-manifest to D2-manifest bridge

The engine `run_manifest` preserved by D3B-1 is a partial computation receipt, not the D2 package
`RunManifest`. D3C must apply this explicit bridge:

| D3B / engine fact | D2 package treatment |
|---|---|
| D3B `project_id`, `case_id`, ProjectCase digest and EvaluationRequest digest | Recompute and require exact object-content identity before mapping; bind case identity to the separately supplied exact D2 `ReportIdentity` |
| D3B `request_id` | Preserve as the evaluation-request identity; never relabel it as D2 `run_id` or `report_id` |
| Accepted D3C-0 assembly-authority receipt | Use its exact governed `ReportIdentity`, artifacts, packs, runtime and held distribution control; refuse a caller-minted substitute |
| D3B `evaluated_config_sha256` and engine `config_sha256` | They must be equal; use the evaluated digest as D2 `resolved_config_digest` |
| Engine `engine_version` | Copy exactly to D2 `engine_version` |
| Engine `git_sha` | Use as D2 `code_commit` only after exact Git-commit validation; never substitute the later package-assembly commit |
| Engine `seed` | Add to `deterministic_seeds` only when an exact integer is present |
| Engine `validation_mode` and manifest schema version | Preserve in validation/provenance records; they do not fill unrelated D2 fields |
| D3B `evidence_cutoff` and `valuation_date` | Copy exactly after reciprocal request/case validation |
| D3B source, resolved-config and evaluated-config digests | Preserve as three different identities; never relabel any as a D4 payload/section hash |
| Engine `generated_at` | Preserve as the engine-run timestamp; do not use it as the package creation time unless the two events are independently proven identical |
| D3B validation modules and projection receipts | Produce reciprocal validation/derivation records with no claim of evidence sufficiency |
| D2 pack/input/source/assumption/capability/validation/reconciliation ID tuples | Construct from the actual D2 registries; the engine manifest does not supply them |
| D2 environment and dependency versions | Supply only from a separately evidenced governed runtime receipt |
| D2 dirty-worktree disclosure | Supply from a separately evidenced run-state receipt; the engine manifest does not contain it |
| D2 report issue/revision | Supply from package document control, not the engine |
| D2 `payload_digest` | Leave `None` in D3C; canonical serialization and payload/section hashing remain D4 |

Any required D2 manifest field not supplied by those exact sources must be separately evidenced or
must stop package construction. D3C may not copy a convenient engine value into a semantically
different package field.

## 5. Static section mapping ledger

This table is the only permitted first-package section routing. An implementation must encode an
equivalent immutable table and test parity to this ledger. Runtime parsing of field names to infer a
section, unit, currency, ratio, nominal/real basis or precision is forbidden.

No scalar, series or artifact mapping may begin unless D3B-1 has already proven that
`scenario_result.config` hashes to the exact evaluated-config digest; nested and top-level
`annual_rows`, `debt_result` and `kpis` are exactly equal with identical scalar types, binary64
hex identity (including the sign of zero), and exact mapping-key types; and both duplicated
config-path fields are the canonical literal `<inline>` while both validation-mode fields are the
canonical literal `strict`. Equality must be occurrence-bounded and alias-safe; ordinary Python
`==` is not an admissible reconciliation oracle. D3C must recheck those immutable origin invariants
and refuse a caller-constructed substitute; it may not choose whichever duplicate is convenient.

| Section | Admissible first-package sources | Required treatment |
|---|---|---|
| 1 `executive_investment_thesis` | No automated conclusion source | Always emit the section record; do not turn KPIs into an investment recommendation or decision |
| 2 `project_description_and_structure` | `ProjectCase.identity`, `location`, `jurisdiction_bindings`, `technology_bindings`, `assets`, `topology`; matching D3B request identities | Carry project/scope/asset facts and limitations; absent sponsor/EPC/O&M human or contract facts remain explicit gaps |
| 3 `site_land_permits_legal_status` | ProjectCase site jurisdiction and separately governed legal/permit sources only | Engine-less; no permit/legal conclusion from location or jurisdiction code |
| 4 `resource_and_energy_yield` | A separately governed resource-assessment output plus reciprocal ProjectCase source provenance | Do not use capacity, capacity factor, annual revenue rows or an authored config block as proof that a resource assessment ran; absent assessment receives an exact non-success disposition |
| 5 `technology_selection_design_basis` | ProjectCase technology bindings/assets and separately governed design-basis outputs | No inference that a declared technology was selected or reviewed by a professional |
| 6 `grid_interconnection_curtailment` | ProjectCase topology/shared-infrastructure facts and separately governed grid outputs | Topology may describe interfaces; it is not a grid-capacity, agreement or curtailment assessment |
| 7 `construction_logistics_plan` | Separately governed construction/logistics sources only | Engine-less; no programme or constructability claim from finance life/COD fields |
| 8 `environmental_social_summary` | Separately governed E&S sources/capabilities only | Engine-less and ordinarily material; absence is not `not_applicable` |
| 9 `climate_resilience_assessment` | Separately governed climate/resilience sources/capabilities only | Engine-less; absence needs an exact gap/defer state and cannot be inferred inapplicable |
| 10 `capex_opex_contingency_procurement` | `ProjectCase.costs`; accepted authored `capex`/`opex` inputs bound through D3B; corresponding annual-row cost outputs only as a digest-bound table artifact | Preserve line IDs, periodicity, currency, price basis and allocations; do not recompute totals or invent contingency/procurement evidence |
| 11 `revenue_ppa_tariff_assumptions` | ProjectCase contract-jurisdiction sources/assumptions/missing inputs; D3B tariff/revenue authority routes; exact revenue columns only inside the annual-row artifact | Current D3B has no tariff/PPA numeric assertion receipt, so no scalar tariff/offtake term is carryable in v1; do not parse authored config names; infer no PPA execution or offtaker authority |
| 12 `financing_plan_debt_sizing` | `full_result.debt_result` as the primary debt output; corresponding `ScenarioResult` fields only as reconciliation operands; schedules in one digest-bound artifact | Carry an accepted scalar once under the static table below; never use misleading `_m` aliases, recompute debt or infer a lender offer, covenant approval, security, CP satisfaction or acceptance |
| 13 `tax_fx_inflation_accounting` | ProjectCase conversion/date/source facts; D3B dates, domains and degradation receipt; `full_result.fx_integration`; accepted FX outputs under the static table; tax/FX annual columns only inside the artifact | Preserve degradation/warnings and exact quote direction/date/basis; do not infer tax, inflation or accounting regimes from config names; heuristic FX VaR/CVaR is not a first canonical value; never apply Sri Lankan defaults to another jurisdiction |
| 14 `base_case_financial_outputs` | Statically declared and predicate-qualified `full_result.kpis`; `full_result.annual_rows` as one digest-bound artifact; `ScenarioResult` mirrors only as reconciliation operands | Carry, never recompute, each accepted KPI once; defaulted zeroes, fallback LLCR/PLCR, `None`, non-finite and unknown keys receive their exact refusal/absence state |
| 15 `sensitivity_downside_cases` | Only a separately accepted sensitivity result explicitly bound to the same case/run family | The D3B base-case result does not prove sensitivity ran; otherwise emit the exact missing/deferred/failed capability state and no values |
| 16 `monte_carlo_risk_distribution` | Only a separately accepted Monte Carlo result with governed seed/method binding | The D3B base-case result does not prove Monte Carlo ran; otherwise emit the exact state and no distribution |
| 17 `optimization_alternatives_analysis` | Only a separately accepted alternatives/optimization result | The D3B base-case result does not prove optimization ran; otherwise emit the exact state and no preferred alternative |
| 18 `risk_register_and_mitigations` | ProjectCase missing inputs/assumptions; D3B warnings/degradation; D2 limitations, errors and capability states; separately governed risk sources | Engine-less and always applicable; assemble disclosed risks/gaps without making a risk-acceptance or mitigation-closure decision |
| 19 `decision_checklist_conditions_precedent` | ProjectCase missing-input remedies; separately authorized decision/condition records only | Engine-less and always applicable; no decision, waiver, CP satisfaction or first-draw authority from CI or computation |
| 20 `appendices_provenance_audit_trail` | ProjectCase sources/assumptions; D3B authority and three config digests; numeric projection receipts; complete frozen engine manifest; D2 validation/reconciliation records | Always applicable and grade-critical; expose missing package provenance instead of equating the engine manifest with the D2 manifest |

Unknown upstream keys must be surfaced as `UnrecognizedUpstreamKey` or refused according to the
accepted facade contract. A present unknown key cannot be silently routed by name similarity.

## 6. Numeric unit and meaningful-precision gate

Every carried numeric requires a static field-to-unit record and a mandatory reviewed meaningful
precision. D2's optional `CanonicalValue.precision` is narrowed to mandatory for D3C numeric
inputs and outputs. The lexical value remains the full unrounded value allowed by the accepted D3C
conversion policy; the precision below is metadata about meaningful decimal places, not display
rounding or an evidence-accuracy claim. Display rounding belongs to later adapters.

Any field absent from the reviewed tables is `not_representable` or refused. The implementation may
not derive a unit, currency, quote direction or precision from `_usd`, `_pct`, `_m`, `ratio`, a
currency symbol, neighbouring values, a config key or a UI label. Repeated ScenarioResult fields
are reconciliation operands, not second output homes. Series, schedules and annual rows remain
digest-bound artifacts in the first slice.

### 6.1 Accepted full-result scalar table

| Exact upstream field | Section binding | Unit | Precision | Mandatory carry predicate |
|---|---|---:|---:|---|
| `full_result.kpis.project_irr` | 14 | `fraction/year` | 8 | Exact finite nonzero key and exact equality to `scenario_result.project_irr`; current exact zero is indistinguishable from the upstream default until a computation-status receipt exists |
| `full_result.kpis.equity_irr` | 14 | `fraction/year` | 8 | Finite; `equity_distribution.status == "computed"`; exact non-`None` reconciliation to `scenario_result.equity_performance.equity_irr` |
| `full_result.kpis.project_npv` | 14 | `USD` | 0 | Exact finite nonzero key and exact equality to `scenario_result.project_npv`; current exact zero remains default-ambiguous |
| `full_result.kpis.project_npv_prudential` | 14 | `USD` | 0 | Exact finite key, finite `prudential_rate_used` and exact equality to `scenario_result.wacc.prudential_npv` |
| `full_result.kpis.total_cfads_usd` | 14 | `USD` | 0 | Nonempty annual artifact and every originating row has finite `cfads_usd`; D3C must not recompute the total |
| `full_result.kpis.min_dscr` | 12, 14 | `ratio` | 4 | One canonical output referenced by both sections; nonempty finite DSCR series and exact reconciliation to `debt_result.min_dscr` |
| `full_result.kpis.avg_dscr` | 12, 14 | `ratio` | 4 | Nonempty finite DSCR series; D3C must not recompute the mean |
| `full_result.kpis.llcr` | 12, 14 | `ratio` | 4 | Live positive debt, explicit finite `debt_result.llcr`, exact equality; otherwise the KPI layer may have substituted DSCR mean |
| `full_result.kpis.plcr` | 12, 14 | `ratio` | 4 | Live positive debt, explicit finite `debt_result.plcr`, exact equality; otherwise the KPI layer may have substituted DSCR mean |
| `full_result.kpis.max_debt_usd` | 12, 14 | `USD` | 0 | Exact finite equality to `debt_result.debt_total` and `scenario_result.max_debt_usd`; store once |
| `full_result.debt_result.debt_total` | 12 | `USD` | 0 | Exact finite live-debt value; reconcile to the canonical max-debt output rather than duplicate it |
| `full_result.debt_result.principal_by_tranche.{lkr,usd,dfi}` | 12 | `USD` | 0 | Exact finite value; these are USD-equivalent principals labelled by debt denomination, not native-currency amounts |
| `full_result.debt_result.total_idc` | 12 | `USD` | 0 | Exact finite value |
| `full_result.debt_result.min_dscr` | 12, 14 | `ratio` | 4 | Nonempty finite DSCR series and exact KPI reconciliation; one canonical output home |
| `full_result.debt_result.llcr` | 12, 14 | `ratio` | 4 | Positive debt and explicit finite raw value; exact KPI reconciliation |
| `full_result.debt_result.plcr` | 12, 14 | `ratio` | 4 | Positive debt and explicit finite raw value; exact KPI reconciliation |
| `full_result.debt_result.avg_debt_rate` | 12 | `fraction/year` | 6 | Positive live debt and exact finite raw field |
| `full_result.debt_result.balloon_remaining` | 12 | `USD` | 0 | Exact finite raw field |
| `full_result.debt_result.balloon_pct` | 12 | `fraction` | 6 | Exact finite raw field and reciprocal balloon basis |
| `full_result.debt_result.construction_years` | 12 | `year` | 0 | Exact integer only |
| `full_result.debt_result.tenor_years` | 12 | `year` | 0 | Exact integer only |
| `full_result.debt_result.timeline_periods` | 12 | `count` | 0 | Exact integer only; never relabel as years |
| `full_result.debt_result.fx_min` | 13 | `LKR/USD` | 2 | All three FX statistics finite; every exact expected timeline row contains a finite `fx_rate`; exact same-direction LKR-per-USD ProjectCase conversion/date/source binding; D3B and `fx_integration` both non-degraded and successful |
| `full_result.debt_result.fx_max` | 13 | `LKR/USD` | 2 | Same closed LKR-per-USD predicate as `fx_min` |
| `full_result.debt_result.fx_avg` | 13 | `LKR/USD` | 2 | Same closed LKR-per-USD predicate as `fx_min` |

The LKR/USD rule is the first reviewed quote rule, not a global default. A different currency pair or
quote precision needs a new static reviewed entry. `fx_integration` booleans are nonnumeric facts;
warnings and degradation reasons become limitations/errors. `scenario_result.fx_curve.lkr_usd`
remains one curve artifact. `fx_match_ratio` and `hedging_coverage_pct` remain default-ambiguous and
are not first canonical values. `fx_risk_profile.var_95_usd_million` and
`cvar_95_usd_million` are fixed-shock/heuristic outputs and are refused in v1; any later admission
must use `OutputClass.SYNTHETIC`, `USD_million`, precision 3 and a persistent method warning.
"Reciprocal ProjectCase conversion" means the same directed quote, valuation date, price basis and
source binding; it never means mathematically inverting an opposite quote. If the exact expected
annual-row/timeline count is unavailable, any row lacks a finite `fx_rate`, or a KPI mirror differs,
the scalar remains artifact/reference-only.

### 6.2 Explicitly unavailable first-package scalars

No AEP/P50/P90/resource/uncertainty scalar is carryable without an accepted ResourceAssessment.
CAPEX/OPEX/revenue/tax annual scalars remain artifact-only. No tariff/PPA scalar has a D3B exact
field assertion receipt. WACC components and `discount_rate_used` remain default/`None` ambiguous.
Debt `_m` aliases do not establish millions and are refused. Sensitivity, Monte Carlo and
optimization values cannot come from the base-case result. Every non-finite value, unknown key and
field absent from the table fails closed.

The ProjectCase numeric input table in §6.3 is also a writer-lease prerequisite; ProjectCase's exact
Decimal representation and explicit unit avoid binary64 inflation but do not, by themselves,
authorize D3C to invent meaningful precision.

### 6.3 ProjectCase numeric input table

ProjectCase numerics are inputs, not engine outputs. A permitted scalar belongs in an
`InputRecord.resolved_value`; D3C must not create a second `OutputReference` merely because it
projected the input. Where the table says artifact-only, preserve the exact ProjectCase under a
digest-bound artifact/source locator and emit an explicit `not_representable` absence/limitation.
The ProjectCase remains valid; only the narrower D3C scalar projection is unavailable.

| Exact ProjectCase family | Static unit and basis treatment | Precision source | D3C v1 ruling |
|---|---|---|---|
| `location.latitude_degrees`, `location.longitude_degrees` | Exact `degree`; preserve coordinate role and range; never convert to radians or DMS | None: written Decimal scale is not coordinate accuracy | Artifact/reference-only |
| Generation `capacity.unit_power_capacity`, `capacity.total_power_capacity` | Preserve exact `MW`, `MWac`, `MWdc` or `MWp` plus electrical and capacity basis; never collapse or aggregate across bases | None; D3B binary64 compatibility is not a precision receipt | Artifact/reference-only |
| Generation `capacity.unit_count` | Exact `count`; do not derive from rating or total | `integral_semantics`, precision 0 | Carryable resolved input with exact source/assumption links |
| Storage `power_capacity.value` | Preserve exact `MW`/`MWac`/`MWdc` plus electrical and nameplate/usable/gross/net basis | None | Artifact/reference-only |
| Storage `energy_capacity.value` | Preserve exact `MWh`/`MWhac`/`MWhdc` plus the same bases | None | Artifact/reference-only |
| Storage `duration.value` | Exact `hour` plus the same bases; do not recompute from power/energy | None | Artifact/reference-only |
| Shared-infrastructure `capacity` | Preserve exact unit and infrastructure role; never treat `MW`, `MWac`, `MWdc`, `MWp` and `MVA` as equivalent | None; other roles also lack a closed dimensional allowlist | Artifact/reference-only |
| Cost-line `quantity` | Copy the explicit line-specific unit; do not normalize from description | None | Artifact/reference-only until a line-ID-specific precision receipt exists |
| Cost-line `unit_rate_native` | Exact `<native_currency>/<quantity.unit>`; periodicity remains a separate fact | None; amount minor-unit places do not declare rate precision | Artifact/reference-only |
| Cost `amount.native_amount` | Exact native currency; preserve periodicity, price basis and conversion edge | `native_minor_unit_places`, precision 0–6 | Carryable resolved input; never annualize or append `/year` |
| Cost `amount.reporting_amount` | Exact reporting currency; preserve conversion ID and price basis | `reporting_minor_unit_places`, precision 0–6 | Carryable resolved input; native and reporting propositions remain distinct and reconciled |
| `currency_conversions[*].rate` | Exact `<to_currency>/<from_currency>`; preserve direction, valuation date, price basis and source; never invert | `quote_precision`, precision 1–18 | Carryable resolved input; quote precision does not replace monetary minor units |
| Cost-allocation `share` | Exact `fraction`; preserve allocation, cost-line and asset IDs | None; exact sum-to-one is reconciliation, not precision | Artifact/reference-only |

The only current ProjectCase scalar classes admitted by this table are strict integral counts,
monetary amounts with explicit native/reporting minor-unit places, and directed conversion rates
with explicit quote precision. The closed precision-source set is therefore
`integral_semantics`, `native_minor_unit_places`, `reporting_minor_unit_places` and
`quote_precision`; every other ProjectCase numeric path is refused until an additive precision
receipt is governed.

A `MissingValue` never becomes a `CanonicalValue`. It retains its expected unit, missing-input ID,
reason, affected claims/sections, consequence and remedy. D3C does not solve a missing value from
another reconciled member. Negative controls must prove that `100`, `100.0` and `100.000` capacity
spellings remain equally uncarriable; Decimal-exponent changes do not affect acceptance; and the
mapper refuses AC/DC/MVA equivalence, MW/MWh interchange, quote reversal, periodicity conversion
and synthesized rate units.

## 7. Executable acceptance controls

Before D3C can be offered for merge, tests and independent oracles must prove:

- the assembler accepts a `D3BExecutionSuccess` object and has no evaluator, finance or private
  pipeline import;
- an execution spy observes no D3C gateway call and no finance rerun;
- one genuine `return_full_result=True` D3B result retains annual rows, debt result, metadata,
  warnings, `None`, legacy tuple sequences and finite numeric mapping keys;
- D3C receives that captured accepted outcome as input and never invokes the gateway while building
  its fixture or package;
- exact ProjectCase and EvaluationRequest content digests match the D3B success, while the supplied
  D2 report/run identity matches every reciprocal package reference and is never inferred from
  `request_id`;
- every produced package has exactly twenty sections in exact SSOT order;
- every required D2 register is present and all references are reciprocal;
- all six reconciliation families occur exactly once;
- all four absent human responsibility roles are visibly `not_performed`;
- every numeric has a static reviewed unit and mandatory meaningful precision;
- every duplicated engine surface is compared with exact scalar/key types and binary64 sign
  identity through an occurrence-bounded comparator, and both origins remain canonical `<inline>`;
- defaulted zero, `None`, non-finite, unknown-key, synthetic, failed, missing, degraded,
  unsupported, deferred and not-applicable controls each demonstrably fire;
- D3B engine-manifest fields never masquerade as complete D2 package provenance;
- achieved grade remains `ungraded`, package release remains `hold`, and no decision/review record
  is invented; and
- canonical finance outputs and `VERSION` remain unchanged.

The delivery evidence is also mandatory and cumulative:

- the inherited Dolphin 2 386-test import/taxonomy gate and its current superseding selection;
- the complete current `tests/contracts` gate and new focused D3C hostile suite;
- Draft 2020-12 validation and serialization schemas, canonical dump validation and exact
  serialization/round-trip controls;
- Ruff check, Ruff format, Black, isort, complete governed mypy and `git diff --check`;
- canonical-finance non-recomputation regressions and the D3C zero-gateway execution spy; and
- all required GitHub checks green against the exact immutable PR-head SHA after it is current with
  protected `main`, followed by exact post-merge protected-main verification.

## 8. Writer retraining and collision drill

The package-assembly writer receives no worktree until D3B-1 and the D3C-0 assembly-authority
prerequisite are independently accepted, merged and protected `main` is clean and synchronized.
Training must re-ingress D0, D1, D2, D3A, final D3B-0/D3B-1/D3C-0, both D3C documents, the
canonical GWTF ruleset and the unabridged CASPER/CESSPIT/CCCDIR meanings.

Before a lease, the writer must pass four read-only collision drills: interruption, unexpected
target-hash drift, failed patch context and coordinator takeover. The only passing response is to
stop, preserve the tree, return to read-only and request a fresh SHA-bound lease. The writer may not
reconcile another writer's work after lease revocation.

The lease then names one writer, exact main SHA, worktree, branch, phase and file allowlist. Domain
and assurance reviewers remain read-only and bind final dispositions to one immutable candidate
SHA. Green CI is necessary but cannot override a domain or assurance veto.

## 9. Explicit deferrals

D3C does not implement achieved-grade aggregation, grade ceilings, materiality/release policy,
D4 canonical serialization or payload/section hashes, HTML/API/PDF/DBPL/XLSX migration,
`ReportContext` or wizard replacement, Sri Lankan pack assurance, Golden Path completion, a second
jurisdiction/project, accounts, persistence, downloads, portfolios, licensing, language/runtime
rewrites, native kernels, F5-01, F5-02, P01, P02 or P03. It changes no finance mathematics, KPI
baseline or `VERSION`.
