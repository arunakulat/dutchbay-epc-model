# Global Feasibility Report Contract v1

| Control | Value |
|---|---|
| Document ID | `DBAY-FRC-001` |
| Contract version | `1.0.0` |
| Status | Normative target contract; implementation conformance incomplete |
| Issue date | 2026-08-28 |
| Product scope | Globally extensible renewable-energy feasibility platform |

## 1. Authority and reading rule

This contract defines what a DutchBay global feasibility-report package **means**. It governs
output completeness, applicability, evidence, assurance, delivery parity and release behaviour;
it does not change finance mathematics or assert that the current implementation conforms.

The key words **MUST**, **MUST NOT**, **SHOULD** and **MAY** are normative. Requirements marked
**CURRENT** describe verified implementation at this issue date. Requirements marked **FUTURE**
are conformance work, not present capability. Unless a requirement is explicitly marked **CURRENT**,
every normative requirement in this document is a target/FUTURE requirement and MUST NOT be read as
an implemented-capability claim. The primary-source basis and its limitations are recorded in
[`FEASIBILITY_REPORT_CONTRACT_SOURCES.md`](FEASIBILITY_REPORT_CONTRACT_SOURCES.md).

The ordered section identifiers, titles and presentation groups remain centralized in
[`config/feasibility_sections.yaml`](../config/feasibility_sections.yaml). This document does
not create a competing taxonomy. It defines the semantics that every section identifier and
every report package must eventually carry.

## 2. Purpose, scope and non-goals

### 2.1 Purpose

The platform is intended to accept essential structured project inputs, enrich them through
governed data and applicable technology and jurisdiction capabilities, and compose a traceable
feasibility assessment spanning technical, resource, power-system, geospatial, environmental,
social, regulatory, commercial, financial, risk and evidence matters.

### 2.2 Scope

This contract applies to HTML, DBPL PDF, other PDF, XLSX, JSON, API and controlled in-house or
CLI delivery. It governs the canonical report object before format-specific rendering.

### 2.3 Non-goals

This Dolphin does not:

- implement a global input schema, new calculation, jurisdiction pack or technology pack;
- certify any project, report, jurisdiction, model or source as lender-accepted or bankable;
- lift the current DutchBay audit or release `HOLD`;
- collapse F5-01 and F5-02 or replace their separate evidence and decision gates;
- promote synthetic, benchmark or advisory outputs to field, utility, transaction or lender
  evidence;
- require every source module to execute for every project; or
- authorize a Python or native-language rewrite.

## 3. Product and jurisdiction boundary

The architecture is **globally extensible**. That is a design property, not a claim that every
jurisdiction is implemented or assured. A report MUST identify each applicable jurisdiction
pack as `unsupported`, `supported` or `assured`, with its version, effective-date cutoff,
sources and review decision. An unknown or unsupported jurisdiction MUST NOT silently inherit
Sri Lankan tax, tariff, regulatory, permitting or accounting assumptions.

The three jurisdiction states mean:

- `unsupported`: no governed pack can make the material jurisdiction-specific determinations
  required at the requested grade. The report may preserve jurisdiction-neutral calculations,
  but affected sections MUST be marked `not_run_unsupported_jurisdiction` and the report grade
  MUST be capped accordingly.
- `supported`: a versioned pack, sources, schema, tests and known limitations exist. This means
  the platform can produce governed output within the stated limitations; it does not mean that
  the pack or a project has been independently accepted.
- `assured`: a supported pack has a current, scope-specific independent review record, no open
  review finding that blocks its claimed use, and an authorized decision identifying the grade
  and effective period for which it may be relied upon. Assurance expires or returns to `supported`
  when material law, regulation, tariff, tax, accounting, grid-code or pack logic changes.

A project spanning jurisdictions MUST identify each one, the subject matter it governs, and the
pack resolving it. Conflicts of law, lender policy or contract are reported, never resolved by an
implicit pack-precedence rule.

The Sri Lankan implementation is the first deeply developed reference pack. It is not a global
default, and this contract neither regrades nor assures it. The live audit release `HOLD`, P01,
P02, P03, F5-02 and resource/grid evidence boundaries remain unchanged.

### 3.1 Technology and jurisdiction pack contribution contract

Each pack MUST declare, in machine-readable form:

- pack identifier, semantic version, owner, status, effective date, expiry or review date;
- supported technologies, jurisdictions, project stages and target-grade ceilings;
- sections and capability identifiers contributed to or constrained;
- required and optional inputs, units, defaults and default provenance;
- outputs, validators, source references, evidence minima and cross-field rules;
- permitted degradation, prohibited substitutions and known limitations; and
- review records and compatibility with the core contract and other packs.

There MUST be one declared owner for each canonical output field. A pack MUST NOT silently
overwrite a value produced by the core or another pack. A resolution rule, both competing values
and the decision provenance MUST be recorded when conflict is possible. Inactive technology packs
MUST NOT run merely because their modules are importable.

### 3.2 Capability reachability

“Marrying” the codebase means that every **applicable product capability** is registered,
reachable through governed orchestration, testable, and visible in the report as executed or
explicitly dispositioned. It does not mean that every helper, adapter, synthetic lane, technology
or jurisdiction module executes for every project. Each capability record MUST identify its
owning contract, applicable sections, activation predicate, execution result and disposition.
Helpers that do not independently create report meaning MAY remain implementation details.

## 4. Orthogonal report truths

A report MUST keep the following truths separate:

1. run posture;
2. section applicability;
3. production outcome;
4. evidence sufficiency;
5. independent-review state;
6. assessment grade; and
7. release authority.

No one field is a proxy for another. In particular, `run.mode=lender` or
`report_grade=lender` records execution posture only; it is not a completeness, evidence,
independence, bankability, release or lender-acceptance certificate.

The contract also distinguishes:

- a **source**, which says where a datum or proposition came from;
- **evidence**, which is a source artifact and associated controls offered to support a claim;
- an **assumption**, which is a declared value or proposition adopted without sufficient direct
  evidence for the achieved grade;
- a **derivation**, which transforms recorded inputs by an identified method; and
- a **judgement**, which is an identified person's or governed agent's interpretation or decision.

A source citation alone is not evidence sufficiency. A correct calculation alone is not project
truth. A review alone does not grant release authority.

## 5. Canonical report package

**FUTURE.** CCCDIR conformance requires one centralized, versioned, immutable
`FeasibilityReportPackage` contract. Every delivery adapter MUST consume that same package and
MUST NOT rerun or reinterpret the project independently. The package will contain at least:

- report and project identity;
- contract, engine, code, configuration, jurisdiction-pack and technology-pack versions;
- target and achieved assessment grades;
- the complete ordered section manifest;
- source, evidence, limitation, review, decision and capability-disposition registers;
- reproducibility and artifact manifests; and
- release status and authority.

At minimum, the package MUST contain these typed objects:

| Object | Minimum meaning |
|---|---|
| `ReportIdentity` | Stable report ID, project/case ID, run ID, issue/revision, creation time and superseded-report link. |
| `ScopeDeclaration` | Project boundary, technologies, jurisdictions, stage, intended audience/use, target grade, valuation date, evidence cutoff, reporting currency/price basis, exclusions and materiality rule. |
| `SectionRecord[]` | Exactly one record for each stable section ID, in taxonomy order. |
| `CapabilityDisposition[]` | Every applicable registered capability and whether it executed, degraded, failed, was deferred or was not applicable. |
| `InputRegister` | Supplied, enriched and resolved inputs; units; raw values; transformations; validations and source links. |
| `SourceRegister` | Document/data identity, issuer, dates, locator, access rights, hash and extraction method. |
| `EvidenceRegister` | Claim-to-evidence links, authenticity/authority, applicability, sufficiency, limitations and review. |
| `AssumptionRegister` | Assumption, owner, basis, sensitivity/materiality, approval, review date and replacement action. |
| `LimitationRegister` | Limitation, affected claims/sections, consequence, grade ceiling, owner and remedy. |
| `ReviewRegister` | Reviewer independence, scope, method, findings, responses and signed decision reference. |
| `DecisionRegister` | Decision, authority, conditions, date, evidence basis and supersession. |
| `RunManifest` | Engine/code/config/pack identities, seeds, capability versions, environment and material input digests. |
| `ArtifactManifest` | Format, MIME type, producer, report/run binding, creation time, SHA-256 and disclosure exceptions. |
| `DistributionControl` | Intended audience/use, permitted reliance, distribution class, confidentiality, rights, expiry and redaction policy. |
| `PackageRelease` | Package-level hold/authorization, authority, scope, conditions, decision date and exact report/artifact binding. |

Canonical numbers MUST carry units and sufficient unrounded precision. Display rounding belongs to
an adapter policy and MUST NOT alter the canonical value.

## 6. Section state model

Every canonical section MUST appear in the machine-readable manifest, even when its narrative
is not rendered. Inapplicability, non-execution and failure are different outcomes and MUST NOT
be represented by an absent key or `None` alone.

The normative state axes are:

- `applicability`: `applicable`, `not_applicable`, `undetermined`;
- `production_status`: `complete`, `complete_with_limitations`, `not_required_by_scope`,
  `not_run_missing_input`, `not_run_missing_dependency`,
  `not_run_unsupported_jurisdiction`, `not_run_unsupported_technology`, `failed`,
  `degraded`, `intentionally_deferred`;
- `evidence_status`: `not_required`, `sufficient_for_achieved_grade`, `limited`, `missing`,
  `synthetic_only`, `external_evidence_hold`;
- `review_status`: `not_required`, `not_reviewed`, `self_checked`,
  `independent_review_pending`, `independent_review_completed_with_findings`,
  `independently_accepted`; and
- `release_status`: `not_applicable`, `hold`, `authorized`.

The concise human-facing section status MUST be derived from these axes by a centralized rule;
it MUST NOT discard the underlying states.

### 6.1 Minimum section record

Every `SectionRecord` MUST include:

```text
section_id, section_contract_version, applicability, applicability_reason,
production_status, evidence_status, review_status, release_status,
target_grade, achieved_grade, materiality, summary, output_references,
required_inputs, resolved_inputs, derived_inputs, capability_dispositions,
jurisdiction_pack_ids, technology_pack_ids, source_ids, evidence_ids,
assumption_ids, limitation_ids, error_ids, review_ids, decision_ids,
started_at, completed_at
```

Collections MAY be empty only where the state makes that logically valid. CESSPIT cross-field
validation MUST enforce at least these rules:

- `not_applicable` with `not_required_by_scope` requires an explicit project-scope rationale
  and identified approval basis;
  it cannot be inferred from missing data.
- `complete` requires a valid payload, executed required capabilities, traceable inputs and no
  known material limitation incompatible with the achieved grade.
- `complete_with_limitations` requires limitation records and an explicit grade consequence.
- each `not_run_*` state identifies the exact missing item, affected claims, consequence and
  remedy; a generic `None` or omitted block is invalid.
- `failed` records an actionable error and MUST NOT expose output retained from an earlier run as
  if it belonged to the current run.
- `degraded` identifies the failed or unavailable canonical path, the sanctioned substitute, the
  warning presented to users and the resulting grade ceiling.
- `intentionally_deferred` requires scope authority, reason, owner, target date or gate, and
  consequence. It is not a synonym for inconvenient or failed.
- `external_evidence_hold` and `independent_review_pending` cannot be cleared by the calculation
  or rendering process that produced the report.
- `authorized` requires an identified authority and decision record; successful CI or schema
  validation is not authority.

The human headline status MUST preserve the most consequential unresolved condition. The
centralized derivation rule MUST give `hold`, `external_evidence_hold`, independent-review
conditions, failure, unsupported scope and missing requirements precedence over a presentational
label such as “complete”. The machine form always retains every axis.

### 6.2 Applicability and materiality

Applicability is decided from the declared project boundary, technology, jurisdiction, stage and
intended decision. `undetermined` is blocking for a material section. A section may be
`not_applicable` only when the subject genuinely falls outside that boundary; lack of time,
evidence, support or computation is never inapplicability.

Materiality thresholds MUST be explicit, grade-specific where necessary, and recorded in the
scope declaration. Materiality may change the depth of treatment, not conceal a risk or legal
requirement. A report-level aggregation cannot average away a material failure.

## 7. Assessment grades

The normative report-assessment grades are `illustrative`, `screening`, `decision_grade` and
`lender_grade`. A package records both `target_grade` and `achieved_grade`. The achieved grade
is the highest grade for which every applicable material section satisfies the grade's
production, evidence and review requirements. It is never an average.

`ungraded` is the required sentinel when no grade is achieved; it is not a fifth grade. A target
grade expresses intent. It MUST NOT be copied into `achieved_grade`. At section level only,
`not_applicable` is an additional non-grade sentinel and is valid only with
`applicability=not_applicable` and `production_status=not_required_by_scope`; the report-level
achieved grade is never `not_applicable`.

| Grade | Permitted use and minimum contract behaviour | Prohibitions and ceiling conditions |
|---|---|---|
| `illustrative` | Demonstrates workflow or explores a hypothetical case. Synthetic, toy, placeholder or deliberately simplified inputs may be used when conspicuously labelled and traceable. | No external reliance, investment decision, lender claim or promotion of synthetic output to canonical project evidence. |
| `screening` | Supports early option comparison and information-gap identification. Material sections are present; public, benchmark and derived evidence may be used with source date, uncertainty and limitations. | Does not establish site suitability, permitability, grid acceptance, transaction economics or financeability. Missing material jurisdiction, resource or grid evidence caps the report here or below. |
| `decision_grade` | Supports a named internal governance decision. All material applicable sections are complete or acceptably limited; project-specific evidence, reconciliations and proportionate independent checks exist; conditions and decision authority are recorded. | It is not lender acceptance. An external-evidence hold, material unresolved model finding, unsupported jurisdiction, synthetic-only material claim or missing independent check prevents achievement. |
| `lender_grade` | Supports submission for transaction-specific external diligence. Authenticated transaction evidence, bankable resource/site work, required utility/grid studies, legally current jurisdiction advice, full model governance, independent specialist review and authorized release are bound to the report. | The platform MUST NOT self-award this grade. It requires the named external/independent review and release decisions applicable to the transaction. It does not guarantee financing or acceptance by any lender. |

Grade profiles MAY impose stricter technology-, jurisdiction-, transaction- or section-specific
requirements. They MUST NOT weaken the table. If sections achieve different grades, the package
grade is the minimum across applicable material sections after all report-level blockers. Invalid
`not_applicable` dispositions remain blockers rather than exclusions.

### 7.1 Report-level blockers

The achieved report grade MUST be `ungraded`, or capped below the requested grade, when any of the
following applies to a material claim:

- applicability remains `undetermined`;
- a required section failed, was deferred, is unsupported or lacks required input/dependency;
- evidence is missing, synthetic-only, or on an unresolved external-evidence hold;
- a required independent review is pending or has unresolved blocking findings;
- a jurisdiction or technology pack is unsupported for the requested grade;
- cross-section reconciliations or cross-delivery semantic parity fail;
- the reproducibility manifest cannot identify the material run basis; or
- release remains `hold` where the intended use requires authorization.

Section counts, coverage percentages and evidence scores MAY inform management. They MUST NOT
override these blockers or be labelled as bankability certificates.

## 8. Canonical section manifest

The twenty stable section identifiers in `config/feasibility_sections.yaml` form the v1
manifest. Every report carries a record for every identifier. Section content and applicability
rules are defined below without changing their config-owned identity or order.

The table states minimum report meaning, not an exhaustive engineering method. A pack may add
typed subsections or more demanding controls, but MUST NOT remove a section or weaken its minimum.

| Order and stable ID | Minimum required content | Applicability and grade-critical controls |
|---|---|---|
| 1. `executive_investment_thesis` | Report identity and scope; intended use; target and achieved grade; project stage; decision sought; canonical headline KPIs with units and basis; principal merits, risks, limitations, open conditions and release status. | Always applicable. It MUST disclose blockers and MUST NOT describe a held, ungraded or limited package as complete, bankable, approved or investment-ready. Each headline claim links to its producing section and evidence. |
| 2. `project_description_and_structure` | Site/location boundary; project assets and interfaces; technologies; capacity; development stage; sponsor/owner and delivery structure; EPC/O&M/offtake boundaries; schedule basis and material exclusions. | Always applicable. Unknown ownership, contracting or boundary facts are recorded as gaps. The stated boundary governs all later applicability decisions and must reconcile with inputs, maps and financial scope. |
| 3. `site_land_permits_legal_status` | Geospatial/project boundary; land/sea tenure and access; easements; permit, licence and consent register; legal and regulatory path; status, authority, dates, dependencies, appeals and gaps. | Applicable whenever a physical project, site right or approval is contemplated. Screening may identify pathways from current official sources. Decision/lender grades require project-specific status evidence and suitably qualified legal/regulatory review; the engine cannot self-certify legal compliance. |
| 4. `resource_and_energy_yield` | Resource sources and measurement campaign; data period, spatial/temporal resolution and quality controls; long-term correlation; methods; losses; availability; uncertainty; exceedance cases; gross-to-net reconciliation and energy-yield results. | Applicable to generation and resource-dependent storage/revenue cases. Technology standards and field-data requirements come from the active pack. Synthetic or reanalysis-only output remains labelled and cannot be promoted to bankable field evidence. |
| 5. `technology_selection_design_basis` | Candidate and selected technology; equipment and balance-of-plant basis; rating, quantity, layout/system architecture, design life, site suitability, codes/standards, interfaces, constraints and selection rationale. | Applicable to physical plant. Each active technology pack contributes its design basis; inactive packs are dispositioned. Vendor claims require versioned evidence and do not by themselves establish site suitability or warranty acceptance. |
| 6. `grid_interconnection_curtailment` | Point of connection; network/operator and grid-code basis; available data and model provenance; interconnection study scope; capacity/hosting constraints; load flow, fault, protection, power quality, voltage/reactive, stability and harmonic needs as applicable; curtailment; upgrades; approval, commissioning and certification status. | Applicable to grid-connected projects. A desktop or synthetic-feeder screen MUST be distinguished from an operator study on an authenticated network model. Decision/lender claims require the studies, models, approvals and independent evidence specified by the operator and jurisdiction. |
| 7. `construction_logistics_plan` | Delivery strategy and schedule; ports and laydown; route/heavy-haul constraints; cranes and erection; civil/electrical works; marine works where relevant; supply chain, labour, weather windows, interfaces, contingencies and commissioning path. | Applicable before physical delivery. Depth is stage-specific. Assumed route, port, vessel, crane or productivity data remain assumptions until surveyed/quoted/contracted; omissions flow into cost, schedule and risk sections. |
| 8. `environmental_social_summary` | E&S categorization and standards; area of influence and baseline; material impacts; alternatives and mitigation hierarchy; ESIA/ESMS/management plans; biodiversity; labour; community health/safety; land/resettlement; Indigenous Peoples where applicable; cultural heritage; stakeholder engagement, grievance and disclosure; commitments and monitoring. | Applicable to physical projects. Topic-level inapplicability requires evidence; the whole section is ordinarily material. Applicable law and adopted lender standards are both named. Desktop screening does not equal ESIA completion, stakeholder consent or compliance. |
| 9. `climate_resilience_assessment` | Physical and transition risk scope; scenarios, time horizons and data; hazard, exposure, vulnerability and consequence; design thresholds; adaptation options; residual risk; emissions/alternatives analysis where required; dependencies on E&S, resource and financial cases. | Applicable unless a documented scope rule establishes otherwise. Scenario results are not forecasts. Required external climate, human-rights or lender-framework review is a distinct evidence/review state. |
| 10. `capex_opex_contingency_procurement` | Estimate basis date, price level, currency and scope; work breakdown; quantities/rates; owner/development/EPC/grid/environmental/land/financing interfaces; OPEX and lifecycle replacements; escalation; contingency basis; procurement strategy; quotation/contract status and exclusions. | Applicable to all economic assessments. Totals reconcile to source detail and the financial model. Benchmark or placeholder cost can support only a disclosed lower grade; contingency is not used to conceal unpriced scope. |
| 11. `revenue_ppa_tariff_assumptions` | Offtake/PPA or merchant structure; tariff and currency; indexation/escalation; availability/deemed energy; curtailment and loss allocation; term; settlement; security/credit; merchant and certificate/carbon assumptions; source and effective date. | Applicable where economic outputs use revenue. Jurisdictional or contract terms MUST come from the named pack/evidence, never a hidden Sri Lankan fallback. Unsigned or assumed terms receive a stated evidence status and sensitivity. |
| 12. `financing_plan_debt_sizing` | Sources and uses; draw schedule; interest during construction; fees; reserves; tranches; tenor and repayment; gearing/sizing rule; coverage and covenant definitions; security/conditions; refinancing/balloon assumptions and equity funding. | Applicable when financing, equity or lender outputs are presented. Screening structures remain illustrative. Decision/lender grades require term-specific evidence, canonical metric definitions, reconciliations and review; calculated debt capacity is not a financing offer. |
| 13. `tax_fx_inflation_accounting` | Named jurisdictions and effective-date cutoff; income tax, depreciation/capital allowance, loss use, withholding, VAT/sales tax, customs/duties and incentives as applicable; FX sources and conversion basis; numeraire; inflation/escalation; accounting basis and material book/tax differences. | Applicable to financial results. Unknown jurisdiction or stale legal/tax basis blocks affected grade claims. Pack sources, assumptions and professional-review state are explicit. Currency and percentage units may not be silently mixed. |
| 14. `base_case_financial_outputs` | Annual/periodic revenue, cost, tax, cash-flow and funding statements; model waterfall; canonical NPV/IRR, coverage, leverage and return metrics; units, dates and definitions; construction/operations transition; tie-outs and reconciliations. | Applicable when financial feasibility is claimed. Outputs must use canonical evaluation contracts and finance functions, reconcile to assumptions and identify non-computable metrics. A green run does not establish economic truth or bankability. |
| 15. `sensitivity_downside_cases` | Variables and evidence basis; ranges and combinations; one-at-a-time, scenario, break-even/switching or stress analysis as appropriate; downside cases; covenant/decision thresholds and interpretation. | Applicable to decision uncertainty. Ranges are sourced or explicitly judgemental, not chosen to manufacture comfort. Sensitivities reuse the same definitions and report identity; inability to run is not `not_applicable`. |
| 16. `monte_carlo_risk_distribution` | Distribution choices, parameter basis, dependence/correlation, sampling method, trials, deterministic seed, convergence/stability checks, failed draws, percentiles and relevant tail/breach measures; limitations and comparison with deterministic cases. | Applicable only where stochastic analysis is in scope; otherwise a documented `not_applicable` decision is possible. Toy/default distributions are illustrative only. Non-reproducible or inadequately evidenced distributions cannot support decision/lender-grade probabilistic claims. |
| 17. `optimization_alternatives_analysis` | Alternatives and decision variables; objective(s); constraints; feasibility rules; method; convergence/optimality limitations; rejected/infeasible options; selected alternative and rationale; connection to E&S, technical, risk and financial outcomes. | Applicable where a real alternative or sizing/design decision exists. It may be `not_applicable` only when the scope authority documents that no meaningful decision space exists. Not running an available analysis is `intentionally_deferred`, not inapplicability. |
| 18. `risk_register_and_mitigations` | Risk taxonomy; cause-event-impact statement; affected objectives; likelihood/consequence basis; inherent and residual rating; controls; treatment; owner; action, due date and status; dependencies, triggers and monitoring; links to assumptions and conditions. | Always applicable. Risk scoring method and acceptance authority are explicit. Missing evidence, reviews and failed/deferred sections create risks or conditions; narrative optimism cannot lower them. The register is maintained across revisions. |
| 19. `decision_checklist_conditions_precedent` | Decision sought; criteria and tolerances; conditions precedent/subsequent; evidence required; owner, approver, due date and status; waiver/deviation authority; unresolved blockers; recommended next actions. | Always applicable. This is the controlled bridge from analysis to decision, not an auto-generated approval. External or independent gates remain held until the named authority records a decision. |
| 20. `appendices_provenance_audit_trail` | Full input, source, evidence, assumption, limitation, capability, error, review and decision registers; methodology and definitions; code/config/pack/run identities; validation and reconciliation receipts; artifact manifest and digests; supersession history and confidentiality/publication controls. | Always applicable and grade-critical. It must be sufficient to reproduce or explain the material result within access constraints. Sensitive material may be access-controlled or referenced rather than embedded, but absence and access conditions remain visible. |

### 8.1 Inputs, derivations and evidence by section

Each section contract MUST declare its conditionally required inputs, accepted units/types, source
and evidence minima for each grade, derived outputs, validations and required capabilities. At run
time the section record then binds that declaration to:

- every supplied or enriched input, preserving raw and resolved values, units, source and cutoff;
- every missing or invalid required input, with the exact claim/output affected;
- each derivation's method/contract version, input references, output units, precision and tests;
- each evidence item and the precise claim it supports; and
- each assumption or judgement used because sufficient evidence was unavailable.

Derived output MUST NOT cite itself as independent evidence. A value enriched from a third-party or
official service remains linked to that service's query/snapshot, licence, date and transformation.
Where a required input varies by jurisdiction, technology, stage or grade, the active pack declares
the predicate; application code MUST NOT conceal it in a template or conditional import.

### 8.2 Cross-section reconciliations

The package MUST record, at minimum, the outcome of these reconciliations:

- project boundary, capacity, technology quantity and schedule across sections 2, 5, 7 and 10;
- gross/net energy, losses, availability, curtailment and saleable energy across sections 4, 6,
  11 and 14;
- CAPEX, OPEX, escalation, contingency, replacements and decommissioning across sections 7, 10,
  13 and 14;
- revenue, tariff, currency, tax, FX and inflation across sections 11, 13, 14 and 15;
- debt terms, sizing, cash waterfall, covenant definitions and downside breaches across sections
  12, 14, 15 and 16; and
- E&S, climate, permitting, grid, construction and evidence gaps into sections 18 and 19.

A reconciliation may pass, fail or be not applicable with reason. An unresolved material failure
blocks the affected grade. Renderers MUST expose the failure; they MUST NOT select one conflicting
value for convenience.

## 9. Harness requirements

### 9.1 CASPER

Optional capabilities MUST expose clear call-time errors and predictable disposition records.
Sanctioned degradation MUST be explicit, bounded and grade-aware; it MUST NOT become silent
omission or stale-output reuse. A DBPL PDF is fail-loud under DBPL-01 and never degrades to a
non-DBPL PDF bearing the DBPL name.

A CASPER error record MUST include stable error code, capability/section, safe user message,
technical cause reference, retry/remedy, whether partial output is valid and the grade/release
consequence. Import safety does not authorize a renderer to erase the error. Degradation is
permitted only where its substitute and ceiling are declared in the applicable pack or core
contract. Canonical finance or evidence may never be replaced by a synthetic lane merely to
complete a report.

### 9.2 CESSPIT

Configuration and report contracts MUST be explicit and strictly validated before publication.
Unknown enums, contradictory states, absent required reasons and impermissible grade claims
MUST fail loud with actionable field-level errors.

Pre-flight checks MUST resolve the input schema, jurisdiction and technology packs, units,
required capabilities, intended audience/use, grade profile, evidence cutoffs, dependencies,
reproducibility controls and output prerequisites before material computation. Publication checks
MUST then validate section cardinality, cross-field constraints, reconciliation status, grade
aggregation, disclosures, release authority and artifact bindings. `strict=False`, unknown-field
discard, implicit coercion or renderer-side repair is non-conformant.

### 9.3 CCCDIR

Section identities, typed result contracts, status derivation, grade aggregation and artifact
projections MUST each have one source of truth. Format adapters may change presentation, never
meaning or values.

`config/feasibility_sections.yaml` remains the taxonomy SSOT until deliberately migrated. A typed
contract may enrich each ID with the requirements in this document, but MUST be generated from or
strictly parity-tested against that SSOT. Canonical calculations flow through the existing v14
evaluation gateway and contracts. Adapters import the canonical package; they do not reach around
it into finance, source-module internals or another delivery path.

### 9.4 Authorship and responsibility

The package MUST distinguish software, AI or other governed-agent contributions from human
responsibility. Agent identity, model/tool version where available, operation, inputs and review
state belong in provenance. Human `Prepared`, `Checked`, `Reviewed` and `Approved` identities are
separate roles and MUST NOT be inferred from an automated run or populated with an agent name.
Each human role record states scope, organization, date and decision reference. Missing required
human responsibility is visible and may block grade or release.

## 10. Delivery, provenance and reproducibility

HTML, PDF, XLSX, JSON and API outputs for one report identity MUST be semantically invariant.
Every output MUST bind to the same resolved configuration, run identity and report manifest.
The package MUST record SHA-256 digests for material inputs and emitted artifacts, while making
clear that a digest proves identity/integrity, not truth, authority or fitness for purpose.

### 10.1 Source and evidence metadata

Each material datum, document or dataset MUST retain, as applicable:

- stable `source_id`, title, issuer/author, document or dataset identifier and revision;
- publication, effective, observation/measurement and retrieval dates;
- direct URL, repository/evidence path and precise page, table, cell, clause, feature or record
  locator;
- raw value/text reference, interpreted value, units, precision and transformation chain;
- jurisdiction, technology, project boundary and period to which it applies;
- source class (`authenticated_project`, `official_primary`, `contracted`, `vendor`, `licensed`,
  `benchmark`, `derived`, `assumption`, `synthetic` or `missing`);
- authenticity/authority, confidentiality, licence/publication and access restrictions;
- extraction method, responsible agent, quality checks and SHA-256 digest where bytes exist; and
- supersession, expiry, limitation, evidence status and reviewer decision.

The raw source and interpreted datum remain distinguishable. W3C provenance concepts—entity,
activity, responsible agent and derivation—are sufficient for v1; a full PROV serialization is not
required. A URL without edition/effective date or a hash without source authority is not complete
provenance. Secrets, personal data and licensed material MUST NOT be copied into public artifacts;
the canonical package records controlled references and disclosure limitations instead.

### 10.2 Evidence rules

Evidence sufficiency is claim-, section- and grade-specific. A source may support one proposition
but not another. The evidence register MUST state the exact claim, evidence locator, authenticity,
relevance, jurisdiction/period, independence, limitations, review and expiry. Conflicting evidence
is preserved and dispositioned; it is not silently replaced by the preferred item.

Synthetic, toy, placeholder or advisory output MUST remain labelled through every derivation and
artifact. It MUST NOT become canonical field, grid-operator, contract, legal, tax or lender evidence
through aggregation, rendering, export or human-facing prose. A numerical evidence score MAY be
reported as a diagnostic but MUST NOT elevate a claim, section or package grade and MUST NOT be
called “bankable” without the independent transaction-specific requirements of this contract.

### 10.3 Reproducibility manifest

One `RunManifest` MUST bind the package to:

- report, project/case and run IDs;
- contract/schema, engine and code versions, commit identity and dirty-state disclosure;
- resolved configuration and every active pack/version;
- material input, source snapshot and resolved-assumption digests;
- capability graph and implementation versions;
- deterministic seeds and stochastic method/settings;
- required runtime/dependency versions and relevant external-service/data snapshot identifiers;
- validation, reconciliation and degradation results; and
- creation time, valuation date, evidence cutoff and report issue/revision.

Timestamps MUST be RFC 3339 UTC. Report payload and each section payload SHOULD have canonical
serialization digests to support localization of change; the serialization algorithm and schema
version MUST be named. Volatile timestamps and artifact locations are not inserted into a canonical
payload before its identity digest unless the identity algorithm explicitly defines them.

Reproduction means that the same governed inputs and implementation can explain and, where inputs
remain available, recompute the material results within declared tolerances. It does not promise
that mutable external services or licensed data remain available forever.

### 10.4 Cross-delivery invariance

The canonical JSON representation is the lossless semantic reference. HTML, DBPL PDF, other PDF,
XLSX and API views MAY paginate, abbreviate or add navigation, but for every exposed fact they MUST
preserve value, units, sign, date/period, precision policy, status, evidence link, limitation and
report/run identity. An adapter MUST NOT independently evaluate the project.

An XLSX MAY include transparent presentation or reconciliation formulas, but it MUST NOT become a
second canonical financial model or calculate a competing headline value. Any cell intentionally
omitted for confidentiality or format limits carries an explicit reason. API pagination and field
selection may reduce what is returned in one response, not change the underlying package.

Every artifact record MUST include format, MIME type, producer/adapter version, report/run binding,
creation time, content digest, completeness/disclosure profile, confidentiality marking and
supersession. Parity tests compare semantic values and dispositions, not byte equality.

### 10.5 PDF and DBPL

A PDF described as DBPL MUST be produced only through
`app.reports.dbpl.print_core.render_dbpl_pdf` with the complete `[report]` dependency and font
stack. Missing, mis-pinned or unimportable DBPL dependencies fail loud; the platform MUST NOT fall
back to a generic PDF carrying DBPL identity. A best-effort PDF from `app.reports.renderer` is
permitted only when labelled non-DBPL, with its renderer, limitations and font substitutions
recorded. The un-suppressible DBPL caveat band, document control, page furniture and font
provenance remain part of the output contract.

### 10.6 Audience, reliance, confidentiality and release

The package, not merely individual sections, MUST state intended audience, permitted use/reliance,
distribution class, confidentiality, publication rights, reliance exclusions and expiry/review
date. These controls apply to every artifact and API response. A public summary is a separately
manifested redacted projection of the same report identity, not an ungoverned copy.

Package release authority is distinct from section-local production/evidence/review states. A
section may be technically complete while the package remains `hold`; no section may authorize the
package. Release requires a named human or institutional authority, scope, decision, date,
conditions and artifact/report identity. Section-level `release_status` records a local block or
authorization need; `PackageRelease` is the final distribution decision and cannot be inferred by
aggregating local values.

## 11. Current implementation and conformance gap

The mapping below is a verified 2026-08-28 truth statement. `Implemented` means the stated narrow
mechanism exists, not that this contract is satisfied end to end.

| Contract area | Current mechanism | State against v1 | Required conformance work |
|---|---|---|---|
| Stable section taxonomy | `config/feasibility_sections.yaml` owns 20 ordered IDs in seven presentation groups. | Implemented foundation | Preserve as SSOT; add/enforce the richer typed section semantics without a competing taxonomy. |
| Authored coverage | `analytics/feasibility_sections.py` resolves `complete`, `draft` and `not_applicable`, soft by default. | Partial | Separate applicability, production, evidence, review and release axes; prohibit silent unknown/`None`; strict publication validation. |
| Execution posture | `analytics/run_modes.py` exposes `screening`, `developer`, `lender` and `ic` permission profiles. | Implemented, semantically narrower | Keep as run posture. Rename or document legacy `report_grade`; never map it directly to achieved assessment grade. |
| Canonical report context | HTML/PDF/API-oriented surfaces share `app.reports.report_model.ReportContext`. | Partial | Introduce/version the complete package and registries; represent every section and outcome; retain ReportContext as adapter or migrate it. |
| Optional components | Report orchestration/rendering permits absent optional blocks represented by `None` or omission. | Non-conformant | Emit explicit capability and section dispositions with cause, consequence, grade ceiling and remedy. |
| HTML/PDF semantic path | Current HTML and generic PDF derive from report context/rendering machinery. | Partial | Bind both to one immutable package and parity-test values, states, disclosures and identity. |
| XLSX path | `/v1/cases/report.xlsx` reruns the pipeline and emits through `analytics.executive_workbook.emit_executive_workbook_from_pipeline`. | Non-conformant | Stop independent evaluation; project the same package/run identity and test semantic parity. |
| DBPL PDF | DBPL print core, dependencies and fail-loud contract exist separately from generic rendering. | Implemented foundation | Route only explicitly DBPL artifacts through the print core and bind artifact/provenance manifest. Never relabel generic output. |
| Friendly web inputs | `app.models.WindFarmInputs` maps user fields onto a selected committed base variant. | Unsafe global boundary | Add jurisdiction/technology-aware global input contract; reject unknown jurisdiction-specific requirements rather than inherit Sri Lankan case assumptions. |
| Canonical finance/evaluation | v14 contracts and `evaluate_with_overrides()` provide central evaluation boundaries. | Implemented foundation | Package their results without duplicate mathematics and add report-level reconciliation/traceability. |
| Evidence register | Current evidence machinery records selected financial/economic assumptions and source tiers; weighted summaries exist. | Partial | Extend claim/section coverage, authentication, precise locators, external holds and independent decisions. Prevent score labels from implying grade or bankability. |
| Run manifest | Current manifest records config SHA-256, engine version, git SHA, generated time, seed, validation mode and schema version. | Partial | Add report identity, active pack/source/input hashes, capability graph, environment, cutoffs, validations, section/payload and artifact bindings. |
| Capability coverage | A module coverage audit can distinguish fired, available-not-fired and not-applicable modules for a run. | Diagnostic foundation | Replace module count as product claim with governed capability registry, activation predicates and report-visible dispositions. |
| Jurisdiction/technology packs | Sri Lankan wind/project configuration and related modules are deeply implemented; global packs are not uniformly declared/assured. | Partial | Formalize pack contract, conflict resolution, lifecycle, negative unknown-jurisdiction tests and assurance records. |
| Review/release governance | Audit artifacts distinguish structural checks and external review/release gates. Current release remains `HOLD`. | Governed but incomplete | Bind review and release decisions to report/package identity; preserve P01/P02/P03, F5-02 and resource/grid evidence gates. |

The current platform therefore does **not** conform to `DBAY-FRC-001 v1.0.0`, and this document does
not retroactively grade any existing report. In particular, structural validation, passing CI,
completion coverage, an evidence percentage or `run.mode=lender` MUST NOT lift the live release
`HOLD` or satisfy missing independent evidence and decisions.

## 12. Acceptance and versioning

### 12.1 Acceptance criteria

Conformance is achieved only when automated tests and controlled review demonstrate all of the
following against the production path:

1. **Taxonomy parity:** the package contains exactly the 20 SSOT section IDs in order; duplicate,
   unknown, missing or reordered IDs fail publication.
2. **Strict state schema:** every axis uses a known enum; all conditional reasons/records exist;
   contradictory states and silent unknown fields fail with precise paths.
3. **Applicability controls:** lack of input, evidence, dependency, execution or support cannot be
   encoded as `not_applicable`; every valid N/A carries a project-specific basis and approval.
4. **No invisible absence:** each optional capability and material expected output is executed or
   dispositioned. `None`, empty template branches and stale cached output cannot masquerade as
   completeness.
5. **Grade aggregation:** property tests prove achieved grade is the minimum satisfied grade across
   applicable material sections plus report blockers, never an average, target copy or run-mode map.
6. **Unknown-jurisdiction negative control:** a fictional/unsupported jurisdiction fails closed for
   material local assumptions and never receives Sri Lankan tax, tariff, permit or accounting values.
7. **Synthetic-evidence negative control:** synthetic resource/grid/data output cannot satisfy
   decision/lender evidence or lose its warning through derivation or export.
8. **Independent-authority negative control:** the producing process, CI, model owner or evidence
   score cannot self-clear an external evidence hold, required independent review or release.
9. **Error/degradation controls:** unavailable dependencies, failures and sanctioned substitutes
   produce their exact dispositions, warnings and grade ceilings; old results are not reused.
10. **Reconciliations:** deliberate conflicts in capacity, energy, cost, currency, tax, debt or
    schedule fail the relevant reconciliation and cap the report as specified.
11. **Cross-delivery parity:** one fixture package produces HTML, DBPL PDF where requested, non-DBPL
    PDF, XLSX, JSON and API artifacts with the same canonical values, units, statuses, evidence,
    limitations and report/run identity. No adapter invokes evaluation.
12. **Workbook unity:** an execution spy or equivalent proves XLSX consumes the existing package and
    does not independently rerun the finance pipeline.
13. **DBPL fail-loud:** incomplete DBPL dependencies or fonts produce the controlled DBPL error and
    never a silently substituted DBPL-labelled artifact.
14. **Reproducibility:** a fixed fixture, seed, clock and serialization policy reproduce material
    payload digests; a one-field material input change changes the appropriate source, section and
    package identities.
15. **Disclosure and privacy:** intended use, audience, confidentiality, reliance, limitations,
    agent/human roles and release state appear on every required surface; restricted source content
    and secrets do not leak.
16. **Rendered review:** representative DBPL PDFs and XLSX files receive semantic and layout checks;
    truncated caveats, hidden statuses, broken locators or unreadable control furniture fail.
17. **Current HOLD regression:** adoption or implementation of this contract cannot change P01/P02/
    P03/F5-02/resource-evidence state or package release without the separately required hash-bound
    authority.

Focused unit/contract tests are necessary but not sufficient. Finance-, grid-, E&S-, legal- and
evidence-material grade claims retain the independent-oracle and specialist-review requirements of
their domains.

### 12.2 Contract and pack versioning

This document and the machine package use semantic versioning:

- `PATCH`: clarifications and corrections that do not change machine meaning or required behaviour;
- `MINOR`: additive backward-compatible fields, statuses or requirements for which v1 readers have
  an explicit safe unknown-handling rule; and
- `MAJOR`: removal, rename, type or semantic change to a stable field/status/section ID, grade rule,
  applicability rule or release meaning.

Because strict readers reject unknown fields, even an additive field requires a declared reader
compatibility range and fixtures. Stable section IDs are never recycled. A rename uses a new ID,
deprecation period, migration map and dual-read policy; historical packages remain immutable and
retain the contract, code and pack versions under which they were issued.

Jurisdiction and technology packs are versioned independently and declare compatible contract and
engine ranges. Material source, legal, tariff, tax, grid-code or methodology changes require pack
review, effective-date control and a statement of whether existing reports require reissue. A new
engine MUST NOT silently reinterpret an old package.

### 12.3 Sequenced implementation Dolphins

Implementation SHOULD proceed as small, independently reversible Dolphins:

1. **Machine contract and taxonomy parity:** define typed package/state/registry schemas by extending
   the existing SSOT; add strict cross-field and negative-control fixtures. No finance change.
2. **Orchestration and disposition:** build one package from the existing evaluation gateway; map all
   20 sections and applicable capability outcomes, including every current optional `None` path.
3. **Grade and release policy:** implement centralized applicability, materiality, grade aggregation,
   external hold, review and package-release contracts without changing the live HOLD.
4. **Provenance and manifests:** bind inputs, sources, evidence, packs, sections, run and artifacts;
   add canonical serialization and privacy controls.
5. **Surface convergence:** make HTML/API consume the package, then migrate XLSX away from independent
   rerun; add semantic parity tests.
6. **DBPL projection:** project the same package through the fail-loud DBPL print core and complete
   rendered-disclosure checks.
7. **Pack formalization:** extract the Sri Lankan reference pack behind explicit interfaces, then add
   new jurisdictions/technologies only with sources, tests, limitations and review state.

No Dolphin should combine this contract migration with a language rewrite. Native kernels or later
packaging may be evaluated from measured performance and portability needs after semantic contracts
and parity tests make such a change auditable.

## 13. Worked example

This is a deliberately fictional contract fixture, not a project assessment. Values and identities
are placeholders solely to show state behaviour; no numerical feasibility claim is made.

```yaml
# Abridged state example; a real package must include every field/register required above.
report_id: FRC-EXAMPLE-NONPROJECT
target_grade: decision_grade
achieved_grade: screening
package_release:
  status: hold
  reason: EXT-EVIDENCE-001 remains open
sections:
  - section_id: technology_selection_design_basis
    applicability: applicable
    applicability_reason: "The fictional scope includes a physical generating plant."
    production_status: complete
    evidence_status: sufficient_for_achieved_grade
    review_status: self_checked
    release_status: hold
    achieved_grade: screening
    capability_dispositions:
      - capability_id: EXAMPLE-DESIGN-BASIS
        outcome: executed
    limitation_ids: []

  - section_id: optimization_alternatives_analysis
    applicability: not_applicable
    applicability_reason: >-
      The fictional scope authority records that this illustrative fixture contains no
      alternative or sizing decision; this is not inferred from missing inputs.
    production_status: not_required_by_scope
    evidence_status: not_required
    review_status: self_checked
    release_status: not_applicable
    achieved_grade: not_applicable
    decision_ids: [EXAMPLE-SCOPE-DECISION]

  - section_id: grid_interconnection_curtailment
    applicability: applicable
    applicability_reason: "The fictional scope assumes a grid-connected plant."
    production_status: complete_with_limitations
    evidence_status: external_evidence_hold
    review_status: independent_review_pending
    release_status: hold
    achieved_grade: screening
    limitation_ids: [EXAMPLE-NO-OPERATOR-STUDY]
    evidence_ids: [EXAMPLE-OPERATOR-STUDY-REQUEST]
```

The fixture's scope decision validates the dedicated N/A outcome; it is not a disguised missing-input
or deferred state. The grid evidence hold caps the package below its target and keeps release held.
A renderer that drops either section is non-conformant.

## 14. Interpretation and decision rules

When this document conflicts with an adapter template, prose convention or legacy field name, this
contract governs report meaning while the feasibility taxonomy continues to govern section identity.
Existing financial and technical contracts continue to govern calculation meaning. A conflict with
law, contract, lender requirement, current governance or a stricter adopted standard is escalated and
recorded; the platform does not silently choose the more convenient rule.

Questions about whether a report is “complete” MUST therefore be answered with at least: complete
for which scope and grade, with what evidence, under whose independent review, and released by whom.
Anything less collapses distinct truths and is outside this contract.
