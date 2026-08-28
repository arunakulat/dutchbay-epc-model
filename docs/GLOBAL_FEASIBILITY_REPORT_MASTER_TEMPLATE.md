# Global Feasibility Report Master Template v1

| Control field | Controlled value |
|---|---|
| Document ID | `DBAY-GFR-MT-001` |
| Template version | `1.0.0` |
| Status / reason for issue | Authoring template for controlled review; contains no project facts or human approvals |
| Issue date | 2026-08-28 |
| Governing report contract | [`DBAY-FRC-001 v1.0.0`](FEASIBILITY_REPORT_CONTRACT.md) |
| Section identity source | [`config/feasibility_sections.yaml`](../config/feasibility_sections.yaml) |
| Product scope | Globally extensible renewable-energy feasibility platform |
| Current implementation | Partial; this template does not assert platform conformance |
| Current DutchBay release state | `HOLD`; unchanged by this template |

> **Controlled-template notice.** This is a writing architecture, not a populated feasibility
> study, machine schema, calculation method, legal opinion, investment recommendation, lender
> submission or release decision. Editorial placeholders are deliberately unfilled. Example
> sentences are fictional and demonstrate disclosure form only. A successful render, calculation,
> test or review does not convert this template into project evidence or human authorization.

## A. Authority, audience and use

This master template translates the exact ordered twenty-section skeleton governed by
`config/feasibility_sections.yaml` into a disciplined human report. The YAML remains the sole
source of section identity and order. The headings below repeat those stable IDs only as a
parity-tested projection. They must not be maintained as a second taxonomy.

The template is written for five related audiences:

1. the analyst or multidisciplinary author assembling a project report;
2. the future web, YAML or API-driven renderer that will project governed content without changing
   its meaning;
3. an investment committee or Board seeking a concise decision record;
4. a DFI, lender, technical adviser, legal adviser, E&S adviser or other specialist performing
   transaction-specific diligence; and
5. an external auditor seeking to reconstruct the source, transformation, review and release path.

These audiences do not receive identical rights of reliance. Every issued report must state its
intended audience, permitted use, distribution class, confidentiality, publication rights, expiry
or review date and reliance exclusions. A public summary is a controlled redaction of an identified
report, not a freestanding substitute.

Unless a statement is explicitly labelled **CURRENT**, instructions in this template describe the
target/FUTURE report architecture. They do not claim that the current platform composes every
section, preserves every disposition or emits every artifact from one canonical package.

## B. How to read and fill this template

Three visual labels separate instruction from content:

- **TEMPLATE INSTRUCTION** tells the author what the finished report must do. It is removed from a
  clean issued report only after the required content or an explicit disposition replaces it.
- **FILLABLE PLACEHOLDER** uses double square brackets, for example
  `[[Insert the evidence cutoff date and basis.]]`. These marks are editorial aids, not a proposed
  machine syntax. No placeholder may survive unnoticed in an issued report.
- **EXAMPLE - FICTIONAL WORDING ONLY** demonstrates candid prose. It never states a DutchBay or
  other real project fact and must not be copied without replacing its factual basis and sources.

An author must never delete a required subsection merely because information is unavailable. Use
the contract's separate applicability, production, evidence, review, achieved-grade and release
states. An absent narrative must be replaced by the correct disposition, its cause, consequence,
owner and remedy.

## C. Controlled opening matter

### C.1 Cover and identity panel

The cover must identify the report without making a grade or release claim by design alone.

| Required field | Fillable placeholder |
|---|---|
| Project / case | `[[Insert controlled project and case identity.]]` |
| Report title | `[[Insert precise project and assessment title.]]` |
| Report ID and revision | `[[Insert stable document ID, revision and superseded-report reference.]]` |
| Issue date and RFC 3339 UTC generation time | `[[Insert issue date and controlled generation time.]]` |
| Project location and boundary | `[[Insert jurisdictions, coordinates/boundary reference and site description.]]` |
| Active technologies | `[[Insert only technologies in the governed project scope.]]` |
| Project stage | `[[Insert concept, pre-feasibility, feasibility, procurement, financing or other governed stage.]]` |
| Intended audience and decision | `[[Insert named audience and the decision this report informs.]]` |
| Target / achieved assessment grade | `[[Insert separate values and the aggregation decision reference.]]` |
| Run posture | `[[Insert run.mode separately; never present it as achieved grade.]]` |
| Package release | `[[Insert HOLD or authorized, authority, conditions and exact artifact binding.]]` |
| Distribution / reliance | `[[Insert confidentiality, permitted distribution, reliance and expiry.]]` |

### C.2 Headline caveat

Place a prominent, unambiguous caveat before the executive thesis. It must identify the most
consequential scope, evidence, review and release boundaries.

> **EXAMPLE - FICTIONAL WORDING ONLY:** This report is a screening assessment prepared from the
> sources identified in the evidence register. It is not a utility interconnection approval, an
> ESIA, a legal or tax opinion, a financing offer, or lender acceptance. The package remains on
> HOLD pending the external evidence and review decisions listed in Section 19.

### C.3 Document control and revision history

Every issue must carry a revision record. Automated or AI-assisted authorship is recorded in
provenance, never placed in a human responsibility cell. The human roles below remain blank until
the named person has performed and accepted the stated scope.

| Revision | Date | Status / reason for issue | Prepared | Checked | Reviewed | Approved |
|---|---|---|---|---|---|---|
| `[[Rev]]` | `[[Date]]` | `[[Draft for review / responding to comments / authorized issue]]` | `[[Human name or NOT PERFORMED]]` | `[[Human name or NOT PERFORMED]]` | `[[Human name or NOT PERFORMED]]` | `[[Human name or NOT AUTHORIZED]]` |

The register must also identify software/AI/governed-agent contribution, tool or model version
where available, operation performed, source inputs and human review state. It must not imply that
an automated author prepared, checked, independently reviewed or approved the report.

### C.4 Scope, basis and cutoffs

State, before any result:

- physical and contractual project boundary;
- technologies and jurisdictions in scope;
- project stage and intended decision;
- valuation date, evidence cutoff, data retrieval dates and price basis;
- reporting and functional currencies, FX convention and inflation basis;
- target assessment grade, materiality rule and known grade ceilings;
- applicable jurisdiction and technology packs with version/status;
- exclusions and the authority accepting them; and
- dependencies on information outside the report.

Unknown jurisdictions must not inherit Sri Lankan assumptions. Sri Lanka may be named only when a
project actually invokes the Sri Lankan reference pack. Even then, the report must state the pack
version, effective cutoff, supported/assured status and unresolved review conditions.

### C.5 Distribution, confidentiality and reliance

Use positive statements of permitted use, followed by exclusions. Avoid a generic disclaimer that
attempts to conceal what the report was actually prepared to do.

> **EXAMPLE - FICTIONAL WORDING ONLY:** This controlled draft is supplied to the named project team
> for information-gap closure. It may not be circulated as an investment recommendation or relied
> upon for procurement, financing, land acquisition, permitting, grid connection or construction.
> Restricted source artifacts remain in the evidence repository and are referenced, not reproduced.

### C.6 Executive reading map

The opening matter should direct readers to:

- Section 1 for the decision thesis and blockers;
- Sections 2-9 for project, site, resource, technology, grid, logistics, E&S and climate basis;
- Sections 10-17 for commercial, financial, risk-distribution and alternatives analysis;
- Sections 18-19 for risks, mitigations, conditions and decision authority; and
- Section 20 for provenance, registers, reproducibility and artifact identity.

## D. Report-wide drafting rules

### D.1 Facts, evidence, assumptions, derivations and judgements

Use the five terms precisely. A fact is a proposition supported for the stated scope and cutoff;
evidence is the controlled artifact offered in support; an assumption fills a declared evidence
gap; a derivation transforms identified inputs by an identified method; and a judgement records a
reasoned interpretation or decision. Do not call a source citation sufficient evidence without
addressing authenticity, relevance, time, jurisdiction, precision and independence.

Every material number should answer: what is it, in what unit and currency, at what date/price
basis, produced by which method, from which inputs, supported by which evidence, reviewed by whom,
and subject to which limitation? Preserve raw values and precision in the governed register even
when the report displays a rounded value.

### D.2 Status and grade language

Do not use “complete”, “approved”, “bankable”, “lender-grade”, “decision-grade”, “compliant” or
“investment-ready” as loose adjectives. Use the exact contract state and explain the basis.
`run.mode=lender` is execution posture only. Evidence coverage and model validation are diagnostic;
neither grants achieved grade or release.

Prescribed status forms are:

- **Complete:** “The section output is complete for [[scope and achieved grade]], based on
  [[evidence IDs/cutoff]], and subject to [[limitations or ‘none recorded’]].”
- **Complete with limitations:** “The analysis was completed using [[basis]], but [[limitation]]
  prevents reliance beyond [[grade/use ceiling]]. [[Owner]] must [[remedy]] before [[gate/date]].”
- **Not applicable:** “The subject is not required by the approved project scope because [[specific
  rationale]]. This is not a missing-input or deferred-analysis disposition. Basis: [[decision]].”
- **Missing input:** “The analysis was not run because [[input]] is missing or invalid. Consequently,
  [[claims/outputs]] are unavailable and the report is capped at [[grade]]. Remedy: [[action/owner]].”
- **Missing dependency:** “The governed capability could not run because [[dependency]] was
  unavailable. No stale or substitute output has been represented as canonical.”
- **Unsupported jurisdiction/technology:** “The platform has no governed [[jurisdiction/technology]]
  pack for this proposition at [[target grade]]. No Sri Lankan or other pack assumptions were used
  as a fallback.”
- **Failed:** “The governed analysis failed with [[controlled error reference]]. Partial output is
  [[valid/not valid]] for [[bounded use]]. Earlier-run results were not reused.”
- **Degraded:** “The canonical capability was unavailable and the declared substitute [[substitute]]
  was used. The substitute is suitable only for [[bounded purpose]] and caps the section at
  [[grade]].”
- **Intentionally deferred:** “[[Authority]] deferred [[analysis]] because [[reason]]. [[Owner]] must
  complete it by [[date/gate]]; until then [[decision/grade/release consequence]].”
- **External evidence HOLD:** “The calculation cannot clear this hold. [[External artifact/decision]]
  is required from [[authority]], bound to [[report/run/evidence identity]].”
- **Independent review pending:** “Independent review of [[scope]] has not been completed. Internal
  checking and successful CI do not satisfy this requirement.”

### D.3 Jurisdiction and technology applicability

Name every active pack and every material cross-border issue. A technology pack contributes only
when its technology is in the declared scope. Shared issues such as grid, land, E&S, climate,
logistics and financing must reconcile technology-specific contributions rather than presenting
parallel, incompatible cases.

Jurisdiction statements should distinguish:

- official law, regulation, tariff, grid code or published procedure;
- project-specific permit, agreement, ruling or advice;
- professional interpretation awaiting or carrying independent review; and
- an assumption adopted for screening only.

### D.4 Exhibits, tables and maps

Every exhibit must have a title, finding, units, legend, basis/cutoff, source and limitation. A map
must state coordinate reference system, extent, scale, north direction, data dates, resolution,
exclusions, positional limitations and whether a boundary is surveyed, contractual, indicative or
derived. Tables distinguish zero, not available and not applicable. Do not hide uncertainty inside
decimal precision, colour, or an unlabeled base map.

### D.5 Cross-delivery and accessibility

The same report identity must preserve values, units, status, evidence and limitations in HTML,
DBPL PDF, other PDF, XLSX, JSON and API projections. CURRENT implementation is not yet unified, and
the XLSX route independently reruns the pipeline. Authors must therefore reconcile artifacts and
state any current divergence rather than presuming parity.

A DBPL PDF must use the DBPL print core and carry document control, classification banner, running
identity/footer, caveat bands, font provenance and PDF/UA-1 tagging. Accessibility also requires
meaningful headings, table headers, repeated row labels, textual findings for figures, sufficient
contrast, non-colour status cues and readable link text. PDF/UA tagging alone is not proof of an
accessible report.

### D.6 Editorial and terminology standard

Write for a technically literate decision-maker. Lead with the finding, then show its basis,
consequence and required action. Prefer a precise short sentence to ceremonial language. Define
abbreviations at first use and maintain a register. Use consistent project, asset, currency,
technology and counterparty names. Preserve distinctions such as MW versus MWh, gross versus net
energy, percentage versus percentage point, nominal versus real, project versus equity return,
P50 versus expected value, curtailment versus availability loss, and source date versus effective
date.

Avoid promotional claims, false precision, anthropomorphism and passive constructions that hide
responsibility. Do not say “it is believed” where the report can say who judged what, on which
basis, and with what review state.

### D.7 Responsibility pattern

Each section names four responsibility scopes:

- **Author:** assembles the narrative from governed inputs and records every gap;
- **Checker:** reconciles values, units, sources and internal logic against the producing records;
- **Independent/specialist reviewer:** provides effective challenge within a stated professional
  scope where the target grade requires it; and
- **Approver/release authority:** accepts the decision or distribution within delegated authority.

These roles may be “not performed” or “not required” only with an explicit basis. They are never
auto-populated from software or AI provenance.

## 1. `executive_investment_thesis` - Executive investment thesis

### Purpose and decision question

Give the reader a controlled answer to: **What decision is sought, what does the evidence support,
what could defeat the case, and what must happen next?** This section is a synthesis of the report,
not a substitute for it. It must distinguish commercial promise from demonstrated feasibility and
must carry the package's actual achieved grade and release state.

### Required narrative

Begin with the project proposition in one paragraph: asset, location, technology, capacity, stage,
sponsor/delivery structure, intended use and valuation/evidence cutoffs. State the requested
decision and why it arises now. Then set out:

1. the technical and resource basis that is sufficiently supported;
2. the commercial and financial outcome, including the canonical return, coverage, cost and energy
   measures applicable to the decision;
3. principal E&S, climate, land, permit, grid and execution consequences;
4. the strongest downside or counter-case, not merely the preferred case;
5. the target and achieved grades, evidence/review constraints and package `HOLD` or authorization;
6. conditions that must be met before the next decision gate; and
7. a recommendation framed within the author's authority.

Do not lead with an IRR divorced from its energy, tariff, tax, FX, debt and evidence basis. If the
economic or execution case is adverse, say so in the opening page. If no recommendation is
authorized, state what the analysis shows and leave the decision to the named authority.

### Required inputs and analytical outputs

| Inputs to synthesize | Required outputs |
|---|---|
| Controlled report/scope identity, intended audience and decision | One-sentence project proposition and exact decision sought |
| Achieved-grade aggregation and every material section disposition | Target/achieved grade, run posture and release shown separately |
| Canonical technical, energy, cost, revenue, finance and risk outputs | Headline KPI table with units, dates, scenario and source section |
| Evidence, limitation, review, risk and condition registers | Ranked merits, blockers, limitations, conditions and owners |
| Approved materiality and decision criteria | Recommendation or decision options within stated authority |

### Minimum exhibits

- a one-page decision dashboard showing metric, value, basis, threshold where authorized, status
  and source section;
- a “case for / case against / unresolved” table;
- a top-risk and top-condition table with owner, evidence required and next gate; and
- a grade/release panel that cannot be mistaken for the run posture.

### Evidence, review and applicability

This section is always applicable. Every factual statement and headline value must link to the
producing section and evidence; it must not create new assumptions or calculations. The author
checks that no favorable result is presented above the grade of its weakest material dependency.
Independent review of a specialist section does not become executive-level release authority.

At `illustrative` or `screening` grade, emphasize option logic, uncertainty and missing evidence.
At `decision_grade`, identify the named internal decision and all conditions. At `lender_grade`,
the summary may describe readiness for transaction-specific diligence only when the independent
reviews and release authorization required by the contract are bound to the package. It must still
avoid predicting lender acceptance.

### Jurisdiction and technology applicability

Name every active jurisdiction and technology pack that materially contributes to the thesis, with
its version, effective date and supported ceiling. Cross-border, shared-asset and hybrid-project
effects must be visible rather than compressed into a single-country or single-technology case.
Unknown or unsupported jurisdictions receive an explicit disposition and must not inherit Sri
Lankan assumptions. Inactive technologies and advisory or synthetic lanes must not appear as if
they were executed, canonical or independently evidenced.

### Cross-section reconciliation

Reconcile the executive capacity, energy, cost, schedule, tariff, tax/FX, debt, returns, downside,
risk and conditions against Sections 2, 4, 6, 7 and 10-19. A conflict is a blocker, not an editorial
choice. The thesis must carry every material external-evidence hold and unresolved independent
finding appearing elsewhere.

### Fillable drafting block

- **Finding:** `[[State the evidence-supported investment or development conclusion in one sentence.]]`
- **Decision sought:** `[[Name the authority, decision, date/gate and alternatives available.]]`
- **Basis:** `[[Cite producing sections, canonical scenarios, cutoffs and evidence IDs.]]`
- **Counter-case:** `[[State the strongest evidence-supported reason not to proceed.]]`
- **Grade/release:** `[[State target, achieved, run posture, review and package release separately.]]`
- **Conditions:** `[[List only the material actions that change the decision or grade.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The screening case supports continued development to close
> the identified resource, grid and land evidence gaps; it does not yet support procurement or
> financing commitment. The downside case breaches the stated internal threshold under the
> assumptions shown in Sections 11 and 15. Release remains on HOLD pending the external decisions
> in Section 19.

### Responsibility

The lead report author prepares the synthesis. Technical, resource, grid, E&S, legal/tax and
financial checkers confirm only the claims within their scope. The model checker reconciles
headline values to canonical outputs. The independent reviewer challenges material judgements and
omissions. Only the named decision/release authority may approve circulation or action.

## 2. `project_description_and_structure` - Project description and sponsor/EPC/O&M structure

### Purpose and decision question

Define exactly **what project is being assessed, where its boundaries lie, who controls its
interfaces, and whether the commercial/organizational structure is coherent enough for the
intended decision**. All later applicability and reconciliation decisions depend on this section.

### Required narrative

Describe the site and area of influence, generating/storage assets, point of interconnection,
shared facilities, access/logistics assets, construction and operations boundary, capacity and
technology composition. Separate existing, proposed, optional, third-party and excluded assets.
State the development stage and critical schedule dates with their basis.

Explain sponsor, shareholder, project-company, developer, EPC, equipment-supply, O&M, offtake,
land, grid and financing roles. Do not treat an expected party as contracted. Identify interface
ownership, approval rights, guarantees, performance/security obligations and unresolved gaps.
Where the structure is undecided, compare the credible alternatives and show the decision gate.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Controlled coordinates/boundary, cadastral or marine limits, layout and single-line diagram | Project boundary statement and asset/interface schedule |
| Technology, capacity, quantity, operating mode and phasing inputs | Reconciled capacity/technology/phase table |
| Corporate records, ownership chart and authorized sponsor information | Sponsor/project-company structure with evidence status |
| Draft/executed EPC, supply, O&M, offtake, grid, land and financing documents | Contract and responsibility matrix: executed, draft, assumed, missing |
| Development programme and approval path | Stage statement, milestone basis and critical dependencies |

### Minimum exhibits

- regional context and controlled project-boundary maps;
- an asset and interface diagram, including point of connection and third-party facilities;
- corporate/contract structure diagram with evidence status on every relationship;
- capacity and technology schedule by phase; and
- milestone schedule distinguishing target, committed and externally controlled dates.

Maps must identify the CRS, scale, data date, boundary status and source. Diagrams must not imply
contractual relationships unsupported by an executed or clearly labelled draft instrument.

### Evidence, review and applicability

This section is always applicable. Corporate, land, grid and contractual assertions require the
relevant controlled source, date and status. Sponsor-provided descriptions may be used but remain
sponsor evidence until corroborated where the achieved grade demands independence. A logo,
website, term sheet or tender expectation is not proof of execution or authority.

At lower grades, indicative boundaries and structures may be used with conspicuous limitations.
Decision-grade work requires project-specific and internally reconciled boundaries, roles and
documents. Lender-grade presentation requires the transaction-specific agreements, due-diligence
status and specialist review appropriate to the claim; this template cannot confer them.

### Jurisdiction and technology applicability

Name all jurisdictions governing the site, corporate vehicle, contracts, grid, taxes, financing
and cross-border supply. Explain conflicts and interfaces; do not apply a silent precedence.
Technology-specific assets are included only when active. A hybrid project must show shared versus
dedicated assets and how control, losses, costs and revenues are allocated.

### Cross-section reconciliation

Reconcile boundary, capacity, quantities, phasing, counterparties and dates to Sections 3, 5-7,
10-14 and 19. The same physical scope must feed the energy model, CAPEX/OPEX, permits, contracts,
debt and risk register. Record any excluded asset whose cost, permit, impact or grid function is
still borne by the project.

### Fillable drafting block

- **Project definition:** `[[Describe included assets, phases, capacity, location and boundary.]]`
- **Structure:** `[[Identify sponsor, project company and material counterparties with document status.]]`
- **Interfaces:** `[[Assign technical, contractual and approval ownership.]]`
- **Unresolved matters:** `[[State gaps, consequence, owner and gate.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The boundary shown is an indicative development boundary,
> not a surveyed or legally registered parcel. The cost model includes the internal collection
> system but excludes the third-party transmission upgrade identified in Section 6; the exclusion
> is therefore carried as a cost and schedule limitation rather than treated as resolved.

### Responsibility

The project/development lead authors the factual scope. Engineering checks asset and interface
definitions; legal/corporate counsel checks entities and document status; the financial checker
confirms model-boundary consistency; geospatial review confirms map provenance. Human approval of
the project definition is separately recorded.

## 3. `site_land_permits_legal_status` - Site, land, permits and legal status

### Purpose and decision question

Establish **whether the project has, or can credibly obtain, the site rights and governmental,
regulatory and contractual permissions required for its present stage and next decision**. The
section reports legal status; it does not manufacture a legal opinion from model logic.

### Required narrative

Describe land or seabed ownership/tenure, lease/concession, access, easements, wayleaves, setback
and encumbrance position. State whether boundaries are surveyed, registered, contractual,
indicative or disputed. Identify affected parcels and the relationship between the project
boundary, area of influence, transmission route, access routes and temporary construction land.

Set out the permit and licence pathway by authority, instrument, legal basis, submission status,
conditions, validity/expiry, dependencies, appeal or challenge exposure, public consultation and
renewal/transfer requirements. Distinguish statutory requirement, regulator practice, professional
interpretation and screening assumption. Identify foreign investment, corporate, competition,
procurement, sanctions, local-content, import/export and security issues where material.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Title/registry records, surveys, cadastral or marine data, leases/concessions and access instruments | Land/site-right schedule with parcel, right, term, status, encumbrance and gap |
| Official laws, regulations, authority guidance and effective dates | Jurisdiction-specific permit/legal pathway and source cutoff |
| Applications, permits, licences, conditions, correspondence and decisions | Permit register with exact status and critical conditions |
| Project design, schedule, E&S scope, grid route and logistics plan | Dependency map linking design changes and approvals |
| Legal and specialist advice with scope/reliance | Legal issues, review findings, unresolved interpretations and grade ceiling |

### Minimum exhibits

- land/site-right map and parcel schedule;
- permit/licence register with authority, legal basis, status, dates and dependency;
- approval pathway or critical-dependency diagram;
- legal-issues matrix separating fact, interpretation, assumption and advice; and
- conditions/undertakings table linked to Sections 18 and 19.

### Evidence, review and applicability

This section is applicable whenever a physical site, access right, government approval or legal
structure is contemplated. Lack of records is a missing-evidence condition, not N/A. Screening may
identify an official pathway, but cannot claim project compliance or permitability. Decision and
lender grades require current project-specific evidence and suitably qualified legal/regulatory
review within the stated jurisdiction and reliance scope.

Do not summarize a document more strongly than its operative language. Record version, execution,
signatory authority, conditions, annexes, amendments and expiry. Confidential evidence may be
referenced through controlled IDs rather than reproduced.

### Jurisdiction and technology applicability

Each governing jurisdiction is explicit. An unsupported jurisdiction receives the prescribed
fail-closed language and grade cap; Sri Lankan law or procedure is never a global default.
Technology-specific consents, such as aviation, maritime, water, hazardous material, generation,
storage or decommissioning approvals, are activated only when relevant and sourced.

### Cross-section reconciliation

Reconcile land and permit boundaries with Sections 2, 5-9 and 19; expiry and approval dates with
Section 7; fees, duties and obligations with Sections 10 and 13; conditions and disputes with
Sections 18-19. A design assumption that changes required land or permitting must be visible in
both sections.

### Fillable drafting block

- **Site-right conclusion:** `[[State exactly which rights exist, their term/status and what is missing.]]`
- **Permit conclusion:** `[[State permits obtained, pending, not applied, expired or disputed.]]`
- **Legal basis/review:** `[[Cite official source cutoff and advice/review scope.]]`
- **Decision consequence:** `[[State the next gate and what cannot proceed before it.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The official procedure supports a screening view of the
> expected approval sequence, but no project-specific permit decision has been evidenced. The
> section is therefore complete with limitations for screening only; it is not a legal opinion or
> confirmation that the project can lawfully commence construction.

### Responsibility

The development/land lead compiles the register. A qualified land specialist checks boundary and
tenure evidence. Jurisdiction-qualified counsel reviews legal interpretation and reliance. E&S,
grid and construction leads check approval dependencies. Only the authorized project body accepts
legal risk or a permit-condition decision.

## 4. `resource_and_energy_yield` - Resource assessment and energy-yield assessment

### Purpose and decision question

Determine **what energy the project can credibly deliver, with what uncertainty, on which resource,
measurement, design and loss basis**. This section must allow a technical adviser to reconstruct
the gross-to-net chain and identify where evidence ends and assumption begins.

### Required narrative

Describe the applicable resource: wind climate, solar irradiance, hydrology, marine resource,
fuel/heat source or other technology-specific driver. State measurement instruments, locations,
heights/depths, periods, availability, calibration, quality control, data exclusions and gaps.
Identify reanalysis/satellite/reference datasets, spatial/temporal resolution, retrieval date,
licence and representativeness.

Explain long-term correction or correlation, spatial extrapolation, vertical adjustment, wake or
array effects, power/conversion curves, availability, electrical and environmental losses,
curtailment treatment, degradation and uncertainty. Present gross, intermediate and net energy
without double-counting. Define exceedance cases, period and statistical method. A P50 is not
automatically an expected value, and a P90 is not “90 per cent of P50”.

For storage, distinguish generation/resource assessment from charging source, dispatch, round-trip
loss, availability, degradation and augmentation. For hybrids, present technology contributions,
shared-constraint allocation and portfolio net energy.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Measurement campaign, calibration/maintenance and quality records | Resource data inventory, quality/coverage metrics and gap disposition |
| Official/licensed reference datasets and query/snapshot provenance | Long-term/reference basis and representativeness assessment |
| Layout/design, equipment curves and operating strategy | Gross production by technology and period |
| Loss, availability, degradation and curtailment assumptions/evidence | Auditable gross-to-net loss bridge without duplication |
| Uncertainty components, correlations and statistical method | P-level or other uncertainty cases with definitions and confidence limits |
| Reconciliation rules to grid, revenue and finance | Saleable-energy series and canonical finance input reference |

### Minimum exhibits

- resource and measurement-location map with terrain/context and data status;
- measurement timeline and completeness/quality table;
- long-term/reference comparison and trend exhibit where supported;
- gross-to-net energy waterfall with every loss and uncertainty item;
- monthly/annual production profile and technology split;
- exceedance/uncertainty table with method, period and units; and
- layout/wake or spatial-yield exhibit where applicable.

### Evidence, review and applicability

This section is applicable to generation and to resource-dependent storage/revenue cases.
Technology-pack requirements determine the appropriate standard, data class and method. Reanalysis,
satellite, synthetic, vendor or generic benchmark data may support illustration/screening when
labelled; it cannot be promoted to a bankable field campaign by calibration, averaging or prose.

Decision-grade conclusions require project-specific data and proportionate independent technical
review. Lender-grade presentation requires the transaction's accepted field/resource work,
methods, uncertainty analysis and independent adviser decision. The engine and report author
cannot self-certify those conditions.

### Jurisdiction and technology applicability

Use only active technology lenses. Wind reporting should identify long-term meteorology, turbine
and balance-of-plant inputs, extremes and traceability appropriate to the adopted standard. Solar
reporting should name the monitoring/data basis and adopted IEC edition/class where claimed.
Other technologies require their own governed pack rather than analogy. Local terrain, climate,
grid dispatch and environmental constraints enter only through sourced project-specific rules.

### Cross-section reconciliation

Reconcile capacity, layout and equipment with Sections 2 and 5; curtailment and export limits with
Section 6; availability/commissioning with Section 7; environmental shutdowns with Section 8;
degradation/replacements with Section 10; saleable energy and deemed energy with Section 11; and
all finance inputs with Sections 14-16. The report must identify which energy series is canonical.

### Fillable drafting block

- **Resource basis:** `[[Identify campaign/reference data, periods, quality and cutoff.]]`
- **Method:** `[[Describe correction, spatial/vertical treatment, conversion and loss chain.]]`
- **Energy result:** `[[Insert controlled gross/net and exceedance outputs with units and period.]]`
- **Uncertainty/limitation:** `[[State dominant uncertainties, missing evidence and grade ceiling.]]`
- **Finance bridge:** `[[Identify the exact saleable-energy series supplied to Section 14.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The modeled series is suitable for comparative screening,
> but no project measurement campaign or independently reviewed uncertainty model has been
> supplied. The reported energy cases must therefore not be described as bankable P50/P90 evidence,
> and the financing case remains capped accordingly.

### Responsibility

The resource specialist authors the assessment; data engineering checks lineage and quality
controls; the technology/design lead checks equipment and layout inputs; grid and finance checkers
confirm curtailment and saleable-energy transfer. Independent resource review is recorded separately
from internal model checking and is mandatory where the target grade requires it.

## 5. `technology_selection_design_basis` - Technology selection and design basis

### Purpose and decision question

Explain **why the selected technology and configuration are suitable for the declared site, duty,
interfaces and project life, and what remains to be proven before commitment**.

### Required narrative

Describe the selected and credible alternative technologies, equipment quantities/ratings,
configuration, layout, balance of plant, control philosophy, design life, environmental envelope,
codes/standards, availability philosophy, redundancy, spares and decommissioning basis. Separate
concept, reference, bid, selected and contracted designs.

Set out selection criteria and trade-offs: energy, site suitability, constructability, grid
performance, environmental/social impact, supply-chain maturity, warranty, degradation, service,
local capability, cost, schedule and financeability. State where vendor evidence, certification,
type testing, site-specific load/stress assessment, geotechnical work or design review is pending.

For hybrids and storage, describe shared point-of-connection controls, energy-management logic,
charge source, usable versus nameplate capacity, duration, degradation/augmentation, fire safety,
auxiliary loads and allocation of shared constraints.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Site/resource/environmental design conditions and survey status | Controlled design-basis memorandum and unresolved design inputs |
| Candidate equipment specifications, curves, certifications, warranties and service terms | Technology compliance/deviation matrix with evidence status |
| Layout, electrical/civil/control architecture and interfaces | Selected configuration, quantities and system architecture |
| Energy, grid, E&S, logistics, cost and schedule studies | Multi-criteria selection rationale and trade-off record |
| Codes, standards and jurisdiction requirements | Applicable-standard register and project-specific verification plan |

### Minimum exhibits

- design-basis table with parameter, unit, value/status, source and verification owner;
- site/layout and system/single-line diagrams;
- candidate technology comparison and selection matrix;
- equipment and balance-of-plant schedule;
- interface and responsibility matrix; and
- compliance, certification, warranty and open-verification register.

### Evidence, review and applicability

This section applies to every physical plant. Vendor literature is a source, not independent proof
of site suitability, warranty acceptance, deliverability or performance. Record document version,
model/configuration, operating envelope and deviations. A generic type certificate does not close
a site-specific design question unless its scope demonstrably covers it.

At screening grade, a reference design may be adequate if explicitly indicative. Decision-grade
requires a coherent project-specific basis and reviewed trade-offs. Lender-grade claims require
the transaction-specific design, certification, warranties, specialist studies and independent
technical review appropriate to the equipment and jurisdiction.

### Jurisdiction and technology applicability

Each active technology pack contributes its own design and evidence requirements. Inactive packs
are explicitly not required by scope. An unsupported technology produces a fail-closed disposition;
another technology's rules are not reused by analogy. Jurisdiction requirements for codes, safety,
local certification, grid behavior and decommissioning must be named and date-controlled.

### Cross-section reconciliation

Reconcile quantity, capacity, layout and project life to Sections 2 and 4; grid functions to
Section 6; logistics and construction methods to Section 7; E&S/climate design constraints to
Sections 8-9; equipment cost, spares, replacement and augmentation to Section 10; operating terms
to Section 11; and alternatives/risks to Sections 17-19.

### Fillable drafting block

- **Selected basis:** `[[Identify technology, model/configuration, quantity, rating and design stage.]]`
- **Why selected:** `[[State criteria, alternatives and decisive trade-offs.]]`
- **Suitability evidence:** `[[Cite certifications, studies, limits and pending verification.]]`
- **Open design matters:** `[[State issue, consequence, owner and closure gate.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The reference configuration is adequate for energy and cost
> screening, but the site-specific suitability assessment and binding warranty envelope are
> pending. The selection is therefore provisional and must not be represented as an OEM-approved
> or construction-ready design.

### Responsibility

The lead engineer authors the design basis. Resource, grid, civil/geotechnical, E&S, logistics,
cost and operations specialists check their interfaces. Procurement/legal review vendor and
contract evidence. Independent technical review and authorized design acceptance are recorded as
separate acts; automated optimization is not design approval.

## 6. `grid_interconnection_curtailment` - Grid/interconnection and curtailment assessment

### Purpose and decision question

Establish **whether, how and on what evidence the project can connect and operate without
misstating network capacity, stability, compliance, upgrade or curtailment risk**. A platform
screen and an operator-approved interconnection study are distinct states throughout.

### Required narrative

Identify the network, operator, regulator, point of connection, voltage, export/import capacity,
connection route, ownership boundary and applicable grid code/procedures. State the source,
version, date and authenticity of the network model and plant/OEM model. Explain the formal
interconnection process and current project status: preliminary assessment, application, full
studies, offer/agreement, detailed design, testing, commissioning, certification and operation.

Describe studies required or performed: power flow, short circuit, protection, voltage/reactive,
power quality, harmonics, flicker, dynamic/RMS, EMT, frequency response, fault ride-through,
control interactions, hosting capacity, contingency and stability, as applicable. Report scope,
tool/version, cases, assumptions, acceptance criteria, findings, failed/non-convergent cases and
review/approval status. State upgrades, cost/schedule ownership and dependencies.

Explain curtailment sources separately: network constraint, operator instruction, plant/export
limit, shared point-of-connection allocation, negative price/offtake rule, self-curtailment and
availability. A zero assumption is not evidence of zero curtailment. Identify the series transferred
to resource, revenue and finance.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Grid code, connection procedure, operator data and approval requirements | Interconnection-stage and requirement matrix |
| Authenticated network/base-case model or explicitly synthetic/advisory substitute | Model provenance, suitability and evidence disposition |
| Plant layout, ratings, controls, protection and validated OEM models | Study model and interface register |
| Study cases, criteria, contingencies and operating scenarios | Results by study, case, margin, breach and remedy |
| Connection offer/agreement, operator correspondence and upgrade scope | Capacity, upgrade, responsibility, cost and schedule status |
| Curtailment evidence/assumptions and dispatch rules | Curtailment allocation and saleable-energy interface |

### Minimum exhibits

- geographic connection route and point-of-connection map;
- electrical single-line and ownership/metering boundary;
- study/approval matrix with operator-required, performed, reviewed and accepted states;
- results and margin table, including failed or not-run cases;
- upgrade scope, owner, cost and schedule interface table; and
- curtailment bridge from unconstrained generation to export/saleable energy.

### Evidence, review and applicability

This section applies to every grid-connected project. An off-grid or isolated system requires its
own power-system adequacy and stability treatment rather than blanket N/A. A desktop calculation,
public network diagram, synthetic feeder or generic grid-strength screen is advisory. It must carry
its warning into every exhibit and cannot be relabelled as operator evidence through a high
`run.mode`, complete report, or finance linkage.

Decision/lender-grade claims require the studies, authenticated models, operator decisions,
commissioning evidence and independent review appropriate to the project stage and jurisdiction.
The report cannot self-approve connection or compliance.

### Jurisdiction and technology applicability

The operator and host grid code determine study scope and acceptance. Technology-specific controls
cover inverter- or converter-based resources, synchronous machines, storage, hybrid plant, weak
grids and shared connections as applicable. Unsupported operator/jurisdiction requirements fail
closed. No Sri Lankan network or CEB/NSO assumption applies outside the named Sri Lankan pack.

### Cross-section reconciliation

Reconcile capacity and plant controls with Sections 2 and 5; losses/curtailment with Section 4;
route/works with Sections 3, 7 and 8; resilience with Section 9; upgrade cost and schedule with
Section 10; deemed-energy and dispatch terms with Section 11; and saleable energy, debt downside,
risk and conditions with Sections 14-19.

### Fillable drafting block

- **Connection status:** `[[State exact formal stage, operator evidence and next approval.]]`
- **Study basis:** `[[Name network/plant models, tools, cases, criteria and provenance.]]`
- **Findings:** `[[Report supported capacity, margins, breaches and required upgrades.]]`
- **Curtailment:** `[[Separate evidence, assumptions and canonical finance transfer.]]`
- **Hold/limitation:** `[[State operator evidence or review still required.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The screen identifies no violation within its synthetic
> test cases, but it is not based on an authenticated operator network model and has not been
> reviewed by the grid operator. It is suitable for design triage only. Full interconnection,
> dynamic and commissioning studies remain an external-evidence HOLD.

### Responsibility

The power-systems lead authors the technical assessment. Protection, controls/OEM and grid-code
specialists check their models and criteria. Resource and finance checkers reconcile curtailment
and export. The independent grid reviewer and operator retain their own authority; internal review
or CI cannot stand in for either.

## 7. `construction_logistics_plan` - Construction and logistics plan

### Purpose and decision question

Determine **whether the project can be delivered safely and credibly through the available ports,
routes, sites, supply chains, resources and weather windows within the stated cost and schedule**.

### Required narrative

Set out delivery strategy, contracting/package interfaces, design/procurement/construction sequence,
site establishment, civil/electrical/marine works, installation, testing, energization and
commissioning. Identify critical-path activities, externally controlled milestones, interfaces
with permits, grid and E&S commitments, and schedule contingency.

Describe origin-to-site logistics: manufacturing source, export/import procedures, ports, vessels,
handling, storage/laydown, road/bridge/turning constraints, heavy-haul route, crane/erection strategy,
temporary works and reinstatement. State which route/port/geotechnical/topographic/bathymetric
surveys or vendor method statements exist. Treat unsurveyed dimensions, productivity and weather
windows as assumptions.

Address workforce and accommodation, local capability, HSE, quality assurance, security, supply
chain concentration, long-lead items, spares, customs, interface management and contingency plans.
For offshore/marine works, include metocean limits and vessel/port availability. For storage,
include dangerous-goods transport, thermal/fire controls and commissioning constraints.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Design, quantities, weights/dimensions and installation requirements | Work breakdown and delivery method by package |
| Port/route/site surveys, geospatial constraints and authority limits | Logistics route and constraint register |
| Contractor/vendor programmes, productivity and resource assumptions | Integrated schedule with critical path and confidence basis |
| Weather/metocean, geotechnical and access data | Work windows and delay/contingency analysis |
| Permit, E&S, customs, workforce and security obligations | Compliance and interface schedule |
| Quotes/contracts, lead times and supply-chain evidence | Procurement/logistics cost and risk inputs |

### Minimum exhibits

- construction work breakdown and responsibility matrix;
- integrated milestone schedule with critical path and float basis;
- port-to-site route map, constraint photographs/survey references and alternative routes;
- heavy-component and lifting schedule;
- logistics assumptions/verification register; and
- supply-chain, weather-window and commissioning risk table.

### Evidence, review and applicability

This section applies before physical delivery; depth varies with stage. Desktop mapping and vendor
experience can support screening but not prove route feasibility, bearing capacity, crane pad,
vessel availability or programme productivity. Decision-grade claims require project-specific
surveys, coherent contractor/vendor input and constructability review. Lender-grade presentation
requires transaction-specific plans, contracts/evidence and independent technical review.

### Jurisdiction and technology applicability

Host-country transport, customs, labour, HSE, marine/aviation, road authority and local-content
requirements must come from the active jurisdiction pack and project evidence. Each technology
contributes its actual component dimensions, handling, installation and commissioning needs. Shared
routes and facilities must resolve competing demands rather than assume simultaneous availability.

### Cross-section reconciliation

Reconcile asset quantities and design with Sections 2 and 5; land/access and permits with Section 3;
grid outage/energization with Section 6; biodiversity/community/land commitments with Section 8;
climate/weather hazards with Section 9; cost/contingency and procurement with Section 10; and
schedule-driven financing, risks and conditions with Sections 12, 18 and 19.

### Fillable drafting block

- **Delivery strategy:** `[[State packages, sequence, contract interfaces and construction boundary.]]`
- **Logistics basis:** `[[Identify port, route, surveys, component envelope and constraints.]]`
- **Schedule:** `[[Insert controlled milestones, critical path and contingency basis.]]`
- **Open verification:** `[[State unsurveyed/uncontracted matters, consequence, owner and gate.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The route assessment uses desktop geometry and has not been
> validated by structural bridge checks or a trial movement. Transport feasibility and the related
> cost/schedule are therefore limited to screening. Procurement commitment is conditional on the
> route survey, authority agreement and contractor method statement listed in Section 19.

### Responsibility

The construction/logistics lead authors the plan. Civil, electrical, marine, HSE, geospatial,
procurement and commissioning specialists check their interfaces. E&S and legal reviewers confirm
commitments/permissions. The independent technical reviewer challenges schedule and constructability;
the project authority accepts delivery strategy and residual risk.

## 8. `environmental_social_summary` - Environmental and social assessment summary

### Purpose and decision question

Explain **the project's material environmental and social risks, impacts, affected people and
ecosystems, applicable standards, mitigation commitments and unresolved conditions, and whether
the present evidence supports the intended decision**.

### Required narrative

State the legal and adopted lender/financier standards, assessment category and basis, project area
of influence, alternatives considered and assessment status. Describe baseline data, survey seasons,
methods, consultation and gaps. Distinguish desktop screening, scoping, specialist study, ESIA,
ESMS/ESMP, permit decision, monitoring evidence and independent review.

Address material topics as applicable: biodiversity and ecosystem services; critical habitat;
birds/bats and other species; water, air, noise, shadow/flicker and waste; marine/coastal impacts;
pollution prevention and resource efficiency; labour and working conditions; occupational and
community health/safety; security; land acquisition and involuntary resettlement; livelihood and
economic displacement; Indigenous Peoples; cultural heritage; vulnerable groups; gender and human
rights; cumulative/induced impacts; supply chain; stakeholder engagement, disclosure and grievance;
and construction, operations and decommissioning commitments.

For each material impact, state receptor, source/pathway, project phase, significance method,
inherent effect, mitigation hierarchy, residual effect, monitoring/trigger, owner and evidence.
Do not declare “no impact” because a survey or consultation has not occurred. Do not describe
stakeholder engagement as consent unless the applicable legal/framework requirement and evidence
support that term.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Project boundary/design, alternatives, schedule and area of influence | E&S scope, category and standards matrix |
| Official legal/permit requirements and adopted lender standards | Applicable-requirement and compliance-status register |
| Baseline studies, spatial data, survey effort/seasonality and quality | Baseline adequacy/gap assessment and sensitivity maps |
| Stakeholder, grievance, land/livelihood and consultation records | Engagement record, issues, commitments and unresolved concerns |
| Impact assessments, cumulative analysis and specialist studies | Impact/significance and mitigation hierarchy table |
| ESMS/ESMP, action plans, monitoring and independent review | Commitment/action plan with owner, timing, evidence and status |

### Minimum exhibits

- project area-of-influence and E&S sensitivity map with source/scale/limitations;
- standards and legal-requirements matrix;
- baseline survey inventory by receptor, season, coverage and gap;
- impact/mitigation/residual-significance table;
- stakeholder and grievance summary that protects personal/confidential information;
- commitments/action-plan register; and
- E&S risks and conditions cross-referenced to Sections 18 and 19.

### Evidence, review and applicability

This section is ordinarily material for a physical project. Individual topics may be not applicable
only on a reasoned, evidenced basis. A whole-section N/A disposition requires exceptional and
approved scope logic. Official law and adopted lender standards are both named; one does not
silently displace the other.

At screening grade, identify sensitivities, plausible impacts and study gaps without claiming ESIA
completion or compliance. Decision-grade requires adequate project-specific baseline/assessment,
actionable mitigation and proportionate independent checking. Lender-grade presentation requires
the applicable transaction process, independent E&S review, action-plan/covenant treatment and
release authority; the platform cannot self-certify IFC PS or EP4 compliance.

### Jurisdiction and technology applicability

Host law, permit conditions, country designation and adopted financier standards must be explicit
and current. Technology lenses activate their relevant EHS issues; physical setting and community
context determine applicability. Sri Lankan EIA or other country-specific material is used only
through the named pack and project boundary, never as generic global evidence.

### Cross-section reconciliation

Reconcile project/area boundaries with Sections 2-3; layout/resource shutdowns with Sections 4-5;
grid route with Section 6; construction/logistics/workforce with Section 7; climate hazards and
emissions with Section 9; mitigation/land/monitoring costs and schedule with Section 10; financial
and contractual commitments with Sections 11-14; alternatives with Section 17; and every material
impact/commitment with Sections 18-19.

### Fillable drafting block

- **Assessment status:** `[[State category, standards, studies completed and current formal stage.]]`
- **Material impacts:** `[[State receptors, significance, mitigation and residual effects.]]`
- **Stakeholder/land status:** `[[State process, evidence, unresolved concerns and protections.]]`
- **Gaps/commitments:** `[[Identify study/engagement/action required, owner and decision gate.]]`
- **Review/release:** `[[State independent E&S review and financier/authority decision status.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** Desktop screening identifies potentially sensitive
> receptors within the indicative area of influence, but seasonal surveys and project-specific
> consultation are incomplete. The section does not establish absence of significant impact,
> stakeholder consent or compliance. Design commitment remains conditional on the studies and
> independent E&S review recorded in Section 19.

### Responsibility

The E&S lead authors the integrated assessment. Qualified biodiversity, social, labour, land,
health/safety, cultural-heritage and other specialists check their scopes. Legal review confirms
the applicable host requirements. Independent E&S review and any financier decision are recorded
separately. Personal data and vulnerable-group information receive controlled access.

## 9. `climate_resilience_assessment` - Climate and resilience assessment

### Purpose and decision question

Determine **whether physical and transition climate risks have been assessed over the relevant
project life, whether adaptation is embedded in design and economics, and what residual risk or
evidence gap remains**.

### Required narrative

Define assessment boundary, project life, baseline period, time horizons, climate scenarios,
datasets/models, spatial resolution, downscaling/bias treatment and uncertainty. Clarify that a
scenario is a conditional analytical pathway, not a forecast. Describe present and future hazards,
exposure, vulnerability and consequence for assets, access, grid, resource, water, workforce,
communities, ecosystems and supply chain.

Address relevant hazards such as extreme wind, temperature, precipitation/flood, drought, wildfire,
landslide, coastal erosion, sea-level rise, storm surge, waves, lightning and compound events.
Explain design thresholds, adaptation options, trigger points, monitoring and residual risk.

Describe transition risks/opportunities where material: policy/regulation, carbon/market exposure,
technology change, supply chain, insurance, reputation, offtake and decommissioning. State GHG or
alternatives analysis only where required and supported; do not infer it from avoided-emissions
marketing claims.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Asset/location/life/design thresholds and critical dependencies | Climate-risk scope and materiality basis |
| Observations, official/modelled climate datasets, scenarios and horizons | Hazard projections with uncertainty and data limitations |
| Terrain, hydrology/coastal, ecosystem and infrastructure data | Exposure/vulnerability assessment and maps |
| Failure modes, consequences, recovery and insurance assumptions | Risk ratings, adaptation measures and residual risk |
| CAPEX/OPEX/schedule/energy/finance cases | Adaptation cost, benefit and downside interfaces |

### Minimum exhibits

- scenario, horizon and dataset table;
- hazard/exposure maps with CRS, resolution and uncertainty;
- asset/dependency vulnerability matrix;
- design threshold versus climate range table;
- adaptation options and trigger-pathway exhibit; and
- residual climate-risk/condition register.

### Evidence, review and applicability

This section applies unless an approved scope rule demonstrates otherwise. A historical climate
record alone does not establish future resilience. Conversely, a global scenario layer may be too
coarse for project design. State the decision scale supported by the data.

Screening identifies hazards and priority studies. Decision-grade requires project-specific
vulnerability, adaptation and cost/schedule integration with proportionate specialist review.
Lender-grade claims require the transaction's adopted framework, accepted climate evidence and
independent review. Climate or human-rights requirements arising from EP4 or another framework
remain transaction/category-specific.

### Jurisdiction and technology applicability

Use host-country official data, standards and emergency/planning requirements where applicable,
alongside globally recognized datasets. Each technology contributes its failure modes and design
limits. Shared infrastructure, community and ecosystem dependencies must not disappear behind an
equipment-only analysis.

### Cross-section reconciliation

Reconcile resource trends with Section 4; design thresholds with Section 5; grid/network dependence
with Section 6; work windows/access with Section 7; E&S/community/ecosystem effects with Section 8;
adaptation costs and replacements with Section 10; revenue/insurance/finance effects with Sections
11-16; alternatives with Section 17; and residual risk/conditions with Sections 18-19.

### Fillable drafting block

- **Scope/scenarios:** `[[State boundary, life, horizons, scenarios, data and uncertainty.]]`
- **Material hazards:** `[[State exposure, vulnerability, consequence and design threshold.]]`
- **Adaptation:** `[[State embedded measures, options, triggers, cost and owner.]]`
- **Residual risk:** `[[State unsupported conclusions, review need and decision consequence.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The regional dataset is sufficient to prioritize flood and
> extreme-temperature studies, but its resolution does not support foundation or drainage design.
> The section is therefore a climate-risk screen; site hydrology, design verification and adaptation
> costing remain conditions before the next design gate.

### Responsibility

The climate-risk lead authors the assessment. Civil, electrical, resource, E&S, operations,
insurance and finance specialists check dependencies and consequences. A qualified independent
reviewer challenges scenarios, data fitness and adaptation logic where required. The project
authority accepts residual risk within its delegated scope.

## 10. `capex_opex_contingency_procurement` - Capex, opex, contingency and procurement basis

### Purpose and decision question

Establish **what it costs to develop, build, operate, replace and decommission the defined project,
at what price/currency/date basis, with what evidence and uncertainty, and whether procurement and
contingency treatment are credible for the intended decision**.

### Required narrative

Define estimate class/stage, boundary, WBS, base date, price level, currencies, FX, taxes/duties,
escalation, quantities, rates, productivity, exclusions and owner/contractor scope. Distinguish
budget, benchmark, vendor quote, tender, negotiated and contracted amounts. Explain normalization
and transformations applied to sources.

Present development, land, E&S, engineering, equipment, balance-of-plant, grid, logistics,
construction, owner, financing-related, insurance, reserve, replacement/augmentation and
decommissioning costs as applicable. Explain OPEX fixed/variable components, service agreements,
leases, grid charges, insurance, spares, asset management and lifecycle changes.

Describe contingency by identified uncertainty/risk and estimate maturity. Do not use one percentage
to conceal omitted scope. Separate base estimate, escalation, contingency, risk allowance and
financing costs. State procurement strategy, packaging, market engagement, local-content/customs,
price validity, indexation, securities, warranty and contracting gaps.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Reconciled design, quantities, schedule, logistics and grid/E&S scope | WBS-based CAPEX estimate and scope/exclusion register |
| Quotes, contracts, benchmarks and normalization evidence | Source/price-basis matrix and estimate confidence |
| O&M strategy, contracts, failure/replacement and degradation assumptions | Annual OPEX and lifecycle replacement/augmentation schedule |
| FX, inflation, tax/duty and local-content rules | Currency, escalation and tax/duty bridges |
| Risk register and estimate uncertainty | Contingency/risk allowance basis without double counting |
| Procurement plan and market evidence | Package strategy, status, price validity and next actions |

### Minimum exhibits

- CAPEX WBS table with quantity, unit rate, currency, base date, source tier and status;
- scope/exclusion and interface matrix;
- OPEX/lifecycle schedule;
- estimate bridge from base cost through escalation, contingency and financing uses;
- quote/benchmark/contract evidence and normalization table;
- contingency rationale by risk/uncertainty; and
- procurement package/status/validity schedule.

### Evidence, review and applicability

This section applies to every economic assessment. Screening may use current benchmarks or
indicative quotes with source and normalization. Decision-grade requires a complete reconciled
scope, project-specific evidence for material packages and checked contingency. Lender-grade
presentation requires transaction-specific cost evidence, contracting/procurement status and
independent technical/model review appropriate to the decision.

Benchmark precision does not imply project precision. Expired, conditional or scope-incomplete
quotes remain labelled. Confidential price evidence may be controlled outside the public report,
but the claim, source ID, scope, date and restriction remain visible.

### Jurisdiction and technology applicability

Host tax/duty, import, labour, transport, local-content and price-index assumptions come from the
active jurisdiction pack. Each technology supplies actual WBS, replacement and operating needs.
Shared infrastructure costs must be allocated transparently and reconcile to the project boundary.

### Cross-section reconciliation

Reconcile scope/quantity to Sections 2 and 5; site/permit obligations to Section 3; energy losses
and availability costs to Section 4; grid upgrades to Section 6; logistics/schedule to Section 7;
E&S/climate mitigation/adaptation to Sections 8-9; escalation/tax/FX to Section 13; sources and uses
and cash flow to Sections 12 and 14; and risk/conditions to Sections 18-19.

### Fillable drafting block

- **Estimate basis:** `[[State class/stage, boundary, date, price level, currencies and exclusions.]]`
- **CAPEX/OPEX:** `[[Insert controlled totals and WBS/lifecycle references, not free-standing numbers.]]`
- **Evidence/maturity:** `[[State quoted/contracted/benchmark shares and material gaps.]]`
- **Contingency:** `[[Explain quantified basis and double-counting controls.]]`
- **Procurement:** `[[State package strategy, market status, validity and decision actions.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The estimate reconciles the reference design for screening,
> but the grid upgrade and environmental mitigation scopes remain unpriced. The displayed
> contingency does not close those omissions. The result is therefore not a fixed or financeable
> project cost and is capped pending project-specific scope and market evidence.

### Responsibility

The cost engineer/commercial lead authors the estimate. Engineering, logistics, grid, E&S, tax and
operations check scope and inputs. Procurement/legal check quote and contract status. The financial
model checker reconciles sources and uses, timing, FX and escalation. Independent cost review and
budget approval remain separate human decisions.

## 11. `revenue_ppa_tariff_assumptions` - Revenue, PPA and tariff assumptions

### Purpose and decision question

Establish **what creates revenue, under which contract or market rules, in which currency and
period, with what allocation of volume, price, curtailment, performance and credit risk**.

### Required narrative

Describe the offtake route: executed/draft PPA, tariff regime, auction award, bilateral contract,
merchant market, capacity/ancillary service, certificate/carbon/attribute revenue or combination.
Identify counterparty, term, delivery point, contracted capacity/energy, pricing formula, currency,
indexation, settlement, billing, taxes, availability/performance tests, liquidated damages,
curtailment/deemed energy, change in law, force majeure, termination, security and dispute terms.

Separate executed terms, published regulatory terms, draft negotiations and model assumptions.
For merchant exposure, identify price source, market zone, capture-price/basis adjustment, shape,
negative price, cannibalization, imbalance, congestion, floor/cap and scenario method. For corporate
or weak-counterparty offtake, state credit/security assessment and replacement/termination risk.

Explain how gross production becomes metered/billable volume and how each revenue stream enters the
financial model. Prevent double counting of deemed energy, certificates, capacity payments,
storage arbitrage or ancillary services. An assumed tariff is not a contract.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Executed/draft offtake instruments, awards, tariff orders and effective dates | Commercial-term matrix with legal/evidence status |
| Metering point, saleable energy, availability and curtailment allocation | Billable-volume bridge and contract/market losses |
| Price, index, FX, inflation and market data | Nominal/real price path and conversion basis |
| Counterparty financial/security information | Credit, security and replacement-risk assessment |
| Certificate/carbon/capacity/ancillary rules and eligibility | Separate eligible revenue streams and non-duplication check |
| Scenario and downside assumptions | Base/downside revenue series supplied to finance |

### Minimum exhibits

- offtake/market structure and delivery-point diagram;
- term sheet matrix showing executed, draft, assumed and missing terms;
- energy-to-billable-volume bridge;
- tariff/price path with currency, base date, indexation and source;
- revenue stack by stream, technology and period; and
- counterparty/security, curtailment and termination risk table.

### Evidence, review and applicability

This section applies whenever economic output includes revenue. Official tariffs and market rules
must be current for the named jurisdiction and eligibility. A published tariff is not proof that
the project has an award, allocation, PPA or grandfathered right. A draft PPA is not executed.

Screening may use sourced indicative prices with downside ranges. Decision-grade requires a
decision-relevant commercial basis, project eligibility and checked contractual assumptions.
Lender-grade presentation requires transaction documents, legal review, counterparty/security
evidence and the review/release required by the financing parties.

### Jurisdiction and technology applicability

Jurisdiction-pack contributions are explicit. Unknown locations never inherit a Sri Lankan tariff
or PPA form. Technology-specific revenue is activated only if eligibility, meter/dispatch logic and
evidence exist. Hybrid/storage revenue must show charging source, shared-export allocation and
physical/contractual feasibility of simultaneous services.

### Cross-section reconciliation

Reconcile project/counterparties with Section 2; permits/licences with Section 3; saleable energy
with Sections 4 and 6; availability/design with Section 5; schedule/COD with Section 7; environmental
shutdowns with Section 8; OPEX and performance obligations with Section 10; debt/covenants with
Section 12; tax/FX/inflation with Section 13; and model/downside/risk/conditions with Sections 14-19.

### Fillable drafting block

- **Revenue structure:** `[[State contract/market route, counterparty, term and delivery point.]]`
- **Price basis:** `[[State tariff/formula, currency, index, base date and source status.]]`
- **Volume bridge:** `[[Reconcile saleable energy, curtailment, availability and billing.]]`
- **Evidence/gaps:** `[[State executed/draft/assumed terms and legal/credit review.]]`
- **Downside:** `[[Identify the decisive volume/price/credit stress.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The base case applies a published tariff as a screening
> assumption, but no project award or executed offtake agreement has been evidenced. Revenue is
> therefore not contracted, and the price, eligibility and curtailment allocations remain subject
> to the downside cases and conditions in Sections 15 and 19.

### Responsibility

The commercial/offtake lead authors the section. Legal checks contract interpretation; regulatory
and market specialists check eligibility and price sources; resource/grid check volume and
curtailment; tax/FX and model checkers confirm financial transfer. Credit approval and contract
acceptance remain authorized human decisions.

## 12. `financing_plan_debt_sizing` - Financing plan and debt sizing

### Purpose and decision question

Explain **how the project is proposed to be funded, how debt capacity is calculated, which terms
are evidenced or assumed, and whether the structure remains credible under the relevant downside
and covenant tests**.

### Required narrative

Present sources and uses, equity/sponsor support, grants/concessional capital, debt tranches,
currencies, commitment/draw schedule, pricing, fees, interest during construction, tenor, grace,
amortization, maturity/balloon, reserves, hedging, security, guarantees, distribution restrictions,
covenants, cash sweep and refinancing assumptions. Distinguish target, modelled, indicative,
offered, mandated and executed terms.

Explain debt-sizing method and constraints: gearing, DSCR, LLCR/PLCR, debt-service sculpting,
contract tenor, stress case, minimum/average coverage, lender deductions and circularity handling.
Define each ratio and cash-flow numerator/denominator. Identify the binding constraint and whether
it remains binding in sensitivity/downside. A modelled debt amount is not a financing offer.

Explain funding timing, construction overrun/delay support, reserve mechanics, tax/FX exposure,
currency mismatch, refinancing/balloon risk and equity funding. Show how conditions precedent and
document/evidence gaps constrain assumed availability.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Reconciled project uses, schedule, currencies and contingencies | Sources-and-uses and draw/funding schedule |
| Term sheets, mandates, finance documents or screening assumptions | Tranche/term/evidence matrix |
| Canonical CFADS, tariff/energy, tax/FX and downside cases | Debt capacity by sizing constraint and case |
| Covenant/coverage definitions and lender policies | DSCR/LLCR/PLCR profile and breach/lock-up results |
| Reserves, fees, hedging, security and sponsor support | Financing cash-flow and security/condition register |
| Conditions precedent and review status | Availability/release limitations and next financing actions |

### Minimum exhibits

- sources-and-uses table reconciling exactly to Section 10 and the model;
- financing structure and tranche term/evidence table;
- draw, IDC, repayment and maturity profile;
- debt-sizing bridge showing each constraint and the binding result;
- coverage/covenant profile with definitions and thresholds; and
- reserve, security, sponsor support, currency mismatch and conditions table.

### Evidence, review and applicability

This section applies when financing, lender, equity or leveraged-return outputs are presented. A
fully equity-funded screening case may use an approved not-applicable disposition for debt sizing,
but funding sources and uses remain required. Screening structures are illustrative. Decision-grade
requires decision-relevant terms and checked definitions. Lender-grade presentation requires the
transaction-specific financing evidence, independent model review and named release authority; it
does not mean funds are committed.

### Jurisdiction and technology applicability

Financing, security, exchange-control, withholding and local-debt assumptions come from the named
jurisdiction and transaction. Technology affects construction profile, resource risk, degradation,
warranty, reserve and tenor. Do not transplant a Sri Lankan financing or tax structure into an
unknown jurisdiction.

### Cross-section reconciliation

Reconcile project/counterparties with Section 2; permits/conditions with Sections 3 and 19; energy,
grid and schedule with Sections 4, 6-7; costs and procurement with Section 10; revenue with Section
11; tax/FX/inflation with Section 13; cash flow/ratios with Section 14; downside/distributions with
Sections 15-16; and risk/security/conditions with Sections 18-19.

### Fillable drafting block

- **Funding strategy:** `[[State equity, debt, concessional/grant and support sources.]]`
- **Debt terms/status:** `[[State tranche terms and evidence: assumed, indicative, offered or executed.]]`
- **Sizing:** `[[Define method, canonical CFADS, constraints and binding result.]]`
- **Coverage/downside:** `[[State headroom, breaches, balloon/refinancing and currency risks.]]`
- **Conditions:** `[[State evidence and actions required before financing reliance.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** Debt has been sized to an illustrative coverage constraint
> using assumed tenor and pricing. No lender term sheet or credit approval is evidenced. The result
> demonstrates model mechanics only; it is not a financing offer, commitment or lender-accepted
> structure.

### Responsibility

The project-finance lead authors the structure. Cost, schedule, commercial, tax/FX and technical
checkers confirm inputs. The model checker independently reconciles sizing and covenants to the
cash-flow engine and definitions. Legal review covers finance-document interpretation. Credit,
investment and release authorities remain outside automated analysis.

## 13. `tax_fx_inflation_accounting` - Tax, FX, inflation and accounting basis

### Purpose and decision question

Establish **which fiscal, currency, inflation and accounting rules govern the model, whether they
are current and project-applicable, and how uncertainty or unsupported jurisdiction logic affects
the decision and grade**.

### Required narrative

Name each jurisdiction governing project/company income, construction/imports, payments,
withholding, indirect tax, customs/duties, incentives, depreciation/capital allowance, tax losses,
thin-capitalization/interest limitation, transfer pricing, repatriation and decommissioning. State
source, effective date, taxpayer/entity, basis and professional interpretation. Separate statutory
rule, project ruling/incentive, treaty, advice and model assumption.

Describe reporting/functional currencies, numeraire, spot/forward or scenario FX sources, conversion
dates, translation, currency mismatch, hedging and convertibility/repatriation constraints. Describe
inflation indices, base dates, nominal/real treatment, escalation and index lags/caps. Prevent double
escalation or mixed real/nominal discounting.

State accounting basis, construction capitalization, depreciation, revenue/cost recognition,
financial instruments and material book/tax differences where they affect statements, covenants or
distributions. Do not present a model convention as an accounting opinion.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Official law/regulation/treaty/ruling and effective dates | Tax/legal basis register by entity, jurisdiction and period |
| Project/company structure, contracts, supply routes and currencies | Applicable tax/duty/withholding and currency exposure map |
| Tax, accounting and authorized-dealer/professional advice | Interpretation, review status, reliance and unresolved issues |
| FX observations/curves/scenarios and hedging evidence | FX conversion path, mismatch and downside series |
| Inflation indices, forecasts/assumptions and contract indexation | Nominal/real escalation matrix and consistency checks |
| Model statements and canonical finance definitions | Tax cash-flow, accounting treatment and reconciliation outputs |

### Minimum exhibits

- jurisdiction/entity/tax obligation matrix;
- tax-rate, allowance/loss, withholding, indirect-tax and customs table with effective dates;
- tax cash-flow and book-to-tax bridge where material;
- currency exposure and conversion/hedging table;
- inflation/indexation and nominal/real consistency matrix; and
- professional advice/evidence gap and sensitivity register.

### Evidence, review and applicability

This section applies whenever financial outputs are presented. An unknown or unsupported
jurisdiction blocks material local tax/accounting claims; the model must not substitute Sri Lankan
rules. Official text may establish a rule's wording but not necessarily its project application.
Decision/lender grades require current project-specific professional review and, where relevant,
authorized-dealer, tax-authority or accounting decisions.

Screening may use sourced generic rates/conventions with explicit caps. A successful calculation,
green CI or structural tax test proves only implemented logic, not that law, facts or advice are
current for the transaction.

### Jurisdiction and technology applicability

Activate only named jurisdiction packs with effective cutoffs. Cross-border procurement, finance,
offtake and ownership may invoke several jurisdictions; identify which governs each proposition.
Technology may change customs classification, incentives, depreciation, indirect tax or carbon
treatment; it does not justify analogy without a governed source.

### Cross-section reconciliation

Reconcile entities/contracts with Sections 2 and 11-12; permit/incentive eligibility with Section 3;
equipment/import scope with Sections 5, 7 and 10; price/indexation with Section 11; every tax/FX/
inflation series with Section 14; stresses with Sections 15-16; and unresolved interpretations with
Sections 18-19.

### Fillable drafting block

- **Jurisdiction/basis:** `[[Name governing jurisdictions, entities, sources and effective cutoff.]]`
- **Tax:** `[[State material rules, model treatment, advice and unresolved application.]]`
- **FX/inflation:** `[[State numeraire, sources, dates, indexation and real/nominal logic.]]`
- **Accounting:** `[[State basis and material book/tax or covenant consequences.]]`
- **Review/ceiling:** `[[State professional review and grade/release impact.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The screening model uses published general tax rates, but no
> project-specific advice confirms incentive eligibility, withholding treatment or the import-duty
> classification. These items remain assumptions subject to tax/legal review and downside testing;
> they are not a tax opinion.

### Responsibility

The tax/finance lead assembles the model treatment. Jurisdiction-qualified tax and legal advisers
review applicable law and transaction facts; accounting specialists review reporting treatment;
treasury/FX specialists review sources and hedging. The model checker tests scale, timing and
reconciliation. No automated author occupies an advice or approval role.

## 14. `base_case_financial_outputs` - Base-case financial outputs

### Purpose and decision question

Present **the canonical financial consequence of the declared technical, commercial, fiscal and
financing basis, with complete definitions and reconciliations, so the reader can judge viability
without mistaking a model output for a verified project fact**.

### Required narrative

Define the base case, valuation date, price/currency basis, project life, construction/operations
period, discount rate, energy/tariff/cost/funding inputs and scenario identity. Explain any departure
from contractual, expected or most-likely cases. State model version, run identity, validation mode
and limitations before discussing results.

Present periodic revenue, OPEX, CAPEX, tax, working capital, financing, debt service, reserves,
CFADS, distributions and terminal/decommissioning flows. Define project/equity IRR, NPV date/rate,
DSCR/LLCR/PLCR, leverage and other decision measures. Report units, scale and period. An undefined
or non-computable metric remains explicit; do not coerce it to zero or omit it.

Discuss economic drivers, not merely outputs. Separate project economics from sponsor equity,
financial from economic returns, pre- from post-tax, nominal from real and levered from unlevered.
State covenant breaches, trapped cash, refinancing/balloon and funding shortfall openly.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Canonical resolved configuration and run manifest | Exact base-case/run identity and reproducibility reference |
| Saleable energy, availability/curtailment and operating profile | Revenue/production series reconciled to Sections 4, 6 and 11 |
| CAPEX/OPEX, schedule, escalation, tax/FX and financing | Periodic statements, cash waterfall and sources/uses tie-out |
| Discount/return/covenant definitions and thresholds | Canonical return, value, leverage and coverage metrics |
| Validation, model checks and unresolved findings | Reconciliation/validation status and non-computable outputs |
| Base-case limitations and evidence grade | Interpretation bounded to achieved grade and permitted use |

### Minimum exhibits

- base-case assumption and identity panel;
- sources-and-uses and construction-funding table;
- income/cash-flow/balance-sheet or three-statement summary as applicable;
- cash waterfall and distributions profile;
- project/equity return and NPV table with exact definitions;
- DSCR/LLCR/PLCR, debt and reserve profile;
- energy-revenue-cost-tax-CFADS reconciliation; and
- validation/tie-out and unresolved finding table.

### Evidence, review and applicability

This section applies when financial feasibility is claimed. Outputs must use canonical result
contracts and the governed finance functions; this template does not recompute them. Structural
validation and arithmetic consistency are necessary but do not prove that input evidence or the
project is viable. Screening results remain screening even when numerically detailed.

Decision-grade requires decision-relevant evidence, reconciled model logic and proportionate
independent checking. Lender-grade presentation requires transaction-specific evidence, model
audit/effective challenge and authorized release. Avoid “lender model” as a claim based only on
`run.mode=lender`.

### Jurisdiction and technology applicability

Consolidate only active technology and jurisdiction contributions and disclose allocation of shared
cost, energy, curtailment, tax and financing. Do not combine currencies or percentages without
explicit conversion. A technology or jurisdiction gap that moves a material finance input caps the
section's grade.

### Cross-section reconciliation

This section is the numeric convergence point for Sections 2, 4, 6-7 and 10-13. It must also supply
the unchanged base to Sections 15-16 and optimization objectives in Section 17. Every breach,
shortfall, evidence gap and adverse result flows into Sections 18-19 and the executive thesis.

### Fillable drafting block

- **Base-case identity:** `[[State config/run/report IDs, valuation date, currency and price basis.]]`
- **Headline outputs:** `[[Insert canonical values with definitions, units and source cells/objects.]]`
- **Interpretation:** `[[Explain drivers and decision consequence without promotional language.]]`
- **Validation:** `[[State tie-outs, independent checks and unresolved model findings.]]`
- **Evidence/grade:** `[[State which input limitations prevent higher reliance.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The model is internally reconciled for the stated screening
> assumptions, but the result depends materially on uncontracted revenue and benchmark cost. The
> displayed return and coverage metrics are model outputs, not verified transaction economics or a
> financing conclusion.

### Responsibility

The project-finance/model lead authors the interpretation. Independent model checking validates
definitions, formulas, tie-outs, responsiveness and run identity. Technical, commercial, tax/FX
and financing owners attest only their inputs. Investment or credit approval is not delegated to
the model or report author.

## 15. `sensitivity_downside_cases` - Sensitivity and downside cases

### Purpose and decision question

Show **which assumptions and combinations can change the decision, where thresholds are crossed,
and whether the preferred case survives credible downside rather than merely convenient ranges**.

### Required narrative

State the base-case identity and select variables from material uncertainty/evidence, not from ease
of computation. Explain range source, symmetry/asymmetry, units, correlations/dependencies and
whether the test is one-at-a-time, named scenario, break-even/switching value, stress or reverse
stress. Distinguish sensitivity from probability.

Present impacts on the named decision measures: value/returns, coverage/covenants, funding,
construction, energy, schedule or other authorized criteria. Identify thresholds, binding variables,
nonlinearities, interaction and cases that fail to compute. A tornado ranking shows local response,
not evidence strength, causality or likelihood.

Named downside cases should combine coherent events, timings and mitigations: resource/energy,
delay, CAPEX/OPEX, tariff/merchant price, curtailment, FX/inflation, interest/refinancing, tax,
availability/degradation and other project-specific risks. Do not construct a downside by changing
independent values in mutually inconsistent ways.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Exact base case and canonical metric definitions | Reproducible comparison to unchanged base |
| Evidence/uncertainty/contract ranges and risk events | Variable/range/scenario register with basis |
| Decision/covenant thresholds | Break-even, switching and breach points |
| Dependencies, mitigations and timing assumptions | Coherent named downside cases |
| Evaluation results, errors and responsiveness checks | Sensitivity rankings, interactions and failed-run disclosures |

### Minimum exhibits

- driver/range/source/materiality table;
- one-way tornado or comparable response chart with base and units;
- named scenario matrix with coherent assumptions;
- threshold/break-even and covenant-breach table;
- two-factor interaction exhibit where material; and
- failed/non-responsive evaluation and limitation register.

### Evidence, review and applicability

This section applies to decision uncertainty; inability to run an available analysis is not N/A.
Screening ranges may be broad and benchmark-based if labelled. Decision-grade ranges should be
evidence-based or approved judgements tied to project risks. Lender-grade presentation requires
transaction-specific downside definitions, independently checked model response and the relevant
review/release decision.

Pinned outputs alone prove stability, not responsiveness. Material model changes require an oracle
or invariant independent of the change. A sensitivity that never moves when its driver changes is
a failure, not comfort.

### Jurisdiction and technology applicability

Activate jurisdiction-specific tax, tariff, FX, inflation, permit/schedule and market stresses only
from the governed pack/evidence. Technology-specific resource, cost, degradation, outage and
replacement stresses must preserve shared constraints in hybrid projects.

### Cross-section reconciliation

Ranges trace to Sections 4-13 and risks in Section 18; impacts reconcile to Section 14 definitions.
Probabilistic treatment, if any, reconciles to Section 16. Breakpoints, breaches and decisive
downside cases flow to Sections 1, 18 and 19.

### Fillable drafting block

- **Question/metric:** `[[State the decision measure and unchanged base identity.]]`
- **Drivers/ranges:** `[[State source, unit, direction, dependency and materiality.]]`
- **Results:** `[[State threshold crossings and decisive cases, including failed runs.]]`
- **Interpretation:** `[[Separate response from probability and evidence strength.]]`
- **Action:** `[[State mitigation, evidence or decision condition triggered.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The result is most responsive to the combined energy-price
> and delay case within the tested ranges. This ranking does not mean that case is most probable.
> The downside crosses the stated internal threshold and is therefore carried as a decision
> condition rather than averaged into the base case.

### Responsibility

The risk/model analyst authors the tests. Domain owners approve ranges within their evidence and
authority; the model checker confirms responsiveness, definitions and unchanged base identity.
Independent review challenges omitted drivers, implausible combinations and threshold selection.

## 16. `monte_carlo_risk_distribution` - Monte Carlo risk distribution

### Purpose and decision question

Explain **the modeled distribution of decision outcomes under explicitly evidenced uncertainty,
including dependence, convergence and tail/covenant risk, without presenting simulation frequency
as real-world certainty**.

### Required narrative

Define stochastic scope, base case, uncertain variables, distribution family/parameters, truncation,
time treatment, dependency/correlation, sampling method, trial count and deterministic seed. State
the empirical, contractual, expert-judgement or illustrative basis for each parameter. Preserve the
difference between aleatory variability, epistemic uncertainty and model/structural uncertainty.

Explain model failures, infeasible draws, clipping/rejection, convergence/stability and whether
summary measures changed materially with additional trials. Present the distribution of named
decision metrics: percentiles, expected/median where defined, standard/tail measures, probability
of threshold/covenant breach and conditional loss measures such as VaR/CVaR only with exact
definitions, sign convention and horizon.

Do not label a simulated percentile as an energy P-level unless it uses the applicable resource
definition. Do not treat a probability generated from unsupported toy distributions as a project
probability. Identify risks not represented, including discrete legal, permit, grid, catastrophic,
counterparty, construction and model-form events.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Canonical base case and stochastic configuration identity | Run/seed/trial/sampler manifest bound to the base case |
| Variable/distribution parameters and source/judgement records | Parameter and evidence register with grade status |
| Correlation/dependency assumptions and supporting analysis | Dependency matrix and positive-definiteness/validity checks |
| Thresholds, covenants and decision measures | Percentiles, breach probabilities and tail metrics with definitions |
| Convergence, failed-draw and numerical diagnostics | Stability plots/tables and transparent failure treatment |
| Excluded/non-modelled risks | Model-boundary and residual-risk statement |

### Minimum exhibits

- stochastic parameter/evidence table;
- dependency/correlation heat map with source and limitations;
- convergence/stability and failed-draw summary;
- distribution plots for material metrics with base/threshold markers;
- percentile, VaR/CVaR and covenant-breach table with definitions; and
- modeled versus unmodeled risk inventory.

### Evidence, review and applicability

Stochastic analysis may be `not_applicable` only when the approved scope does not require a
probability distribution and the decision can be addressed by deterministic/downside analysis.
If requested or available work is merely not run, use `intentionally_deferred` or the applicable
failure disposition.

Illustrative/toy distributions remain illustrative regardless of trial count. Screening can use
transparent benchmark/judgement parameters to explore mechanics. Decision-grade probabilistic
claims require project-relevant parameter evidence, dependency logic, reproducibility and
independent model/domain checks. Lender-grade presentation requires transaction-specific evidence,
effective challenge and authorized release.

### Jurisdiction and technology applicability

Parameter sets must reflect the active technologies, jurisdictions and contract structure. Do not
reuse Sri Lankan FX/tariff/tax distributions or wind-resource uncertainty in a different country or
technology without a governed basis. Hybrid dependencies must preserve common resource, price,
grid, construction and financing factors.

### Cross-section reconciliation

Parameter sources trace to Sections 4-13, base metrics to Section 14, deterministic ranges and
named scenarios to Section 15, and constraints/alternatives to Section 17. Tail events, breach
probabilities, excluded risks and evidence gaps flow into Sections 1, 18 and 19.

### Fillable drafting block

- **Run basis:** `[[State base/run IDs, seed, sampler, trials and convergence rule.]]`
- **Parameters:** `[[State distributions, dependence and evidence/judgement status.]]`
- **Results:** `[[Insert percentiles/tail/breach outputs with definitions and sign convention.]]`
- **Limits:** `[[State failed draws, excluded risks and parameter evidence gaps.]]`
- **Decision meaning:** `[[Explain what the distribution changes and what it cannot establish.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The simulation is reproducible for the stated seed and
> converged within the declared diagnostic tolerance. Its distributions are screening assumptions,
> not calibrated transaction evidence. The reported breach frequency therefore illustrates model
> exposure and must not be presented as a lender-accepted probability of default.

### Responsibility

The quantitative risk analyst authors the design/results. Domain specialists review parameters and
dependence; the model checker verifies reproducibility, failed-draw treatment and responsiveness;
the independent reviewer challenges model form, exclusions and interpretation. No automated
simulation approves risk acceptance.

## 17. `optimization_alternatives_analysis` - Optimization and alternatives analysis

### Purpose and decision question

Demonstrate **which credible alternatives were considered, what objectives and constraints governed
comparison, why options were rejected or selected, and whether an optimizer's result is feasible
and decision-relevant rather than merely numerically superior**.

### Required narrative

Define the decision: site/layout, technology/model, capacity, phasing, storage size/duration,
interconnection, contracting, construction, mitigation, financing or other alternative. State the
option set, decision variables, fixed assumptions, objectives, constraints and evaluation metrics.
Include the “do nothing”, defer, smaller/larger and materially different technical/commercial
options where credible.

Explain the method: comparative appraisal, multi-criteria analysis, search/optimization algorithm,
Pareto analysis or other governed approach. State weights/utility only with authority and
sensitivity. For numerical optimization, report bounds, constraint handling, initialization,
random seed, stopping/convergence, infeasible/failed evaluations, local/global limitations and
verification of the selected solution.

Evaluate technical, energy, grid, E&S, climate, land/permit, constructability, cost, finance, risk
and evidence implications. A highest NPV or lowest LCOE option is not selected if it violates a
non-negotiable legal, grid, E&S, technical or delivery constraint. Explain trade-offs and why the
recommended option is robust to key uncertainty.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Decision statement, option set and scope authority | Complete alternatives inventory and exclusion rationale |
| Technical/commercial/environmental objectives and thresholds | Objective/criterion definitions and decision weights if authorized |
| Hard/soft constraints with source/owner | Constraint and feasibility matrix |
| Canonical evaluation method and case identities | Comparable results on one controlled basis |
| Algorithm/settings/seed/convergence where used | Optimization receipt, feasible set and verification results |
| Evidence, sensitivity and risk information | Trade-off/Pareto analysis and selected-option rationale |

### Minimum exhibits

- alternatives longlist/shortlist and screening rationale;
- criteria/objective/constraint matrix with authority and source;
- comparable option table using common units, dates and boundaries;
- Pareto frontier or trade-off chart where useful;
- feasibility/rejected-option and convergence record; and
- selected-option decision and conditions table.

### Evidence, review and applicability

This section applies when a meaningful design, size, site, technology, phasing, commercial or
financing decision exists. It is N/A only when scope authority documents that no meaningful
alternative exists. Failure or unwillingness to analyze alternatives is not N/A.

Screening may compare reference options with transparent assumptions. Decision-grade requires a
complete decision-relevant option set, credible constraints, comparable evaluations and reviewed
judgement. Lender-grade presentation requires transaction-specific evidence and independent review
appropriate to the selected design; an optimizer cannot grant approval.

### Jurisdiction and technology applicability

Option eligibility and constraints come from active jurisdiction/technology packs and project
evidence. An unsupported option remains identified with the reason it cannot be evaluated; it is
not silently discarded. Hybrid/shared-asset alternatives must preserve common grid, land, schedule,
cost and revenue constraints.

### Cross-section reconciliation

Use the same boundaries and outputs as Sections 2-16. Selected design flows back to Sections 2,
4-13 and 14; sensitivity/uncertainty connects to Sections 15-16; rejected/conditional alternatives
and residual trade-offs flow into Sections 18-19 and the executive thesis.

### Fillable drafting block

- **Decision/options:** `[[State the decision and all credible alternatives, including defer/do nothing.]]`
- **Criteria/constraints:** `[[State definitions, thresholds, weights/authority and evidence.]]`
- **Method/results:** `[[State comparable basis, algorithm/settings and option outcomes.]]`
- **Selection:** `[[Explain trade-offs, feasibility, robustness and why options were rejected.]]`
- **Conditions:** `[[State verification/evidence needed before commitment.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The screened configuration has the strongest result under
> the stated objective, but its grid and land constraints remain unverified. It is therefore a
> preferred development option, not an optimized or approved final design. The alternative must be
> re-evaluated after the external constraints are resolved.

### Responsibility

The alternatives/optimization lead authors the method. Domain owners define constraints and review
option feasibility; the model checker verifies comparable cases and algorithm receipts; the E&S,
legal and grid reviewers can identify non-negotiable constraints. Selection and weight approval
belong to the named human decision authority.

## 18. `risk_register_and_mitigations` - Risk register and mitigations

### Purpose and decision question

Provide **one controlled account of uncertainty and threat across the project, showing cause,
event, consequence, ownership, mitigation, residual exposure and decision escalation rather than a
decorative heat map**.

### Required narrative

Define risk framework, objectives, taxonomy, scoring scales, time horizon, risk appetite/tolerance,
acceptance/escalation authority and review cadence. State whether rating is qualitative,
semi-quantitative or quantitative and avoid false arithmetic precision.

Each risk statement should identify cause, uncertain event and consequence to a project objective.
Record phase, affected sections, inherent likelihood/consequence/rating, existing controls,
treatment, owner, due date, leading indicator/trigger, residual rating, dependencies and status.
Opportunities may be recorded separately without netting away threats.

The register must ingest evidence gaps, unsupported packs, model limitations, failed/degraded or
deferred capabilities, adverse sensitivities/tails, contract conditions and review findings. A
mitigation is not complete because it is proposed. Show evidence of implementation and residual
risk acceptance. Risks with no owner are not controlled.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Findings, gaps, failures, limitations and holds from all sections | Consolidated risk statements linked to sources/sections |
| Risk methodology, appetite/tolerance and authority | Inherent/residual scoring and escalation rules |
| Controls, mitigations, commitments and conditions | Treatment plan with owner, due date, evidence and status |
| Sensitivity, scenario, stochastic and schedule/cost outputs | Quantified consequences and triggers where supportable |
| Review/audit findings and management responses | Finding-to-risk-to-action traceability |
| Change/events since prior issue | Movement, closure, reopening and emerging-risk record |

### Minimum exhibits

- risk methodology and scale table;
- ranked risk register with cause-event-impact phrasing;
- heat map only as a navigation aid, with textual status cues;
- treatment/action and overdue/escalation table;
- risk movement since previous issue; and
- evidence/review hold and conditions cross-reference.

### Evidence, review and applicability

This section is always applicable. Risk scores are judgements supported by evidence, not facts.
State the scorer, basis, date and review. Missing evidence does not justify a lower likelihood; it
creates uncertainty and often a separate risk. Screening may use broad ratings; decision-grade
requires current ownership, actionable treatment and decision linkage. Lender-grade presentation
requires the transaction's risk governance and independent specialist/model review, not merely a
complete register.

### Jurisdiction and technology applicability

Risk taxonomy may be global, but causes, likelihood, consequence, legal obligations and mitigations
must be project-, jurisdiction- and technology-specific. Unknown jurisdictions and unsupported
technologies appear as risks/conditions; Sri Lankan experience may be contextual evidence only
when relevance is demonstrated.

### Cross-section reconciliation

Every material risk links to the originating Sections 2-17 and relevant evidence/assumption/
limitation. Treatments reconcile to cost/schedule, design, contract and E&S commitments. Risks
above appetite, external holds, overdue actions and accepted residual exposure flow unchanged to
Sections 1 and 19.

### Fillable drafting block

- **Framework:** `[[State scales, appetite, authority, cutoff and review cadence.]]`
- **Top risks:** `[[State cause-event-impact, rating basis and affected decisions.]]`
- **Treatment:** `[[State control/action, owner, timing, evidence and residual risk.]]`
- **Escalation:** `[[State risks above tolerance, holds and acceptance authority.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The absence of an operator-approved grid study is recorded
> as both an evidence hold and a schedule/cost risk. Commissioning studies cannot mitigate the
> present development decision. Residual risk remains above the stated tolerance until the operator
> study and related upgrade responsibility are evidenced.

### Responsibility

The project risk manager owns the integrated register; domain leads own and evidence their risks
and treatments. A checker tests duplicates, omissions, score consistency and section linkage.
Independent reviewers challenge material risks within scope. Only the delegated authority may
accept residual risk, waive action or close a finding.

## 19. `decision_checklist_conditions_precedent` - Decision checklist and conditions precedent

### Purpose and decision question

Convert analysis into a controlled decision by stating **what is being decided, against which
criteria, which conditions remain open, who may close or waive them, and whether release/action is
authorized for the exact report and artifacts**.

### Required narrative

Name the decision, authority, date/gate, alternatives, required grade, risk tolerance and evidence
cutoff. Summarize each criterion and its status without re-performing the underlying analysis.
Separate analytical conclusion, management recommendation, committee decision, condition
precedent/subsequent, waiver/deviation and package release.

For every condition, state source/requirement, description, affected decision, owner, required
evidence, reviewer/approver, due date/gate, status, dependencies, waiver authority and closure
record. “Pending” must not count as satisfied. A waiver is an authorized decision with rationale
and consequence, not a deleted requirement.

External evidence and independent review holds retain their authority. The producing process,
model owner, document author or CI system cannot close them. Package authorization identifies the
exact report revision, run/payload and artifact hashes, audience, distribution and conditions.

### Required inputs and analytical outputs

| Required inputs | Required outputs |
|---|---|
| Intended decision, authority, criteria, grade and risk tolerance | Decision statement and controlled evaluation checklist |
| Material findings/limitations/risks/holds from Sections 1-18 | Complete blocker and condition schedule |
| Required evidence, review and legal/contractual conditions | Closure criteria and authority for each item |
| Actions, owners, dates, dependencies and status evidence | Action/condition dashboard and overdue escalation |
| Decision minutes, approvals, waivers and release record | Hash-bound decision, conditions and distribution authority |

### Minimum exhibits

- decision criteria/status table linked to source sections;
- conditions precedent/subsequent schedule;
- external-evidence and independent-review hold register;
- action/owner/due-date dashboard;
- waiver/deviation log; and
- package release panel with exact identity and authorized audience.

### Evidence, review and applicability

This section is always applicable, even if the conclusion is “no decision authorized”. Each
status requires evidence and authority. Screening may end with information-gap actions rather than
an investment decision. Decision-grade requires the named internal decision and all required
reviews. Lender-grade presentation requires transaction-specific independent review and release;
the report cannot compel or predict lender acceptance.

Conditions precedent to financing, first drawdown, construction, energization or operation must not
be conflated. The report stage and decision determine which schedule applies.

### Jurisdiction and technology applicability

Official, contract, lender and pack-specific conditions are attributed to their source and
jurisdiction. An unsupported jurisdiction/technology cannot be waived by substituting another pack.
Hybrid/shared conditions must identify whether they apply to the whole project, one technology or
an interface.

### Cross-section reconciliation

Every material unresolved item in Sections 2-18 must appear here or carry a documented immaterial/
accepted rationale with authority. Closure evidence links back to the originating section and the
risk register. The decision/release outcome reconciles exactly to Section 1 and Section 20
manifests; no renderer may show a more favorable status.

### Fillable drafting block

- **Decision:** `[[State exact decision, authority, criteria, date/gate and alternatives.]]`
- **Current outcome:** `[[State authorized / not authorized / deferred without implying release.]]`
- **Conditions:** `[[List requirement, evidence, owner, approver, due gate and status.]]`
- **Waivers:** `[[Record none, or exact authority/rationale/consequence.]]`
- **Package release:** `[[State HOLD or authorization bound to exact report/run/artifact identities.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** Continued development is recommended only to close the
> listed evidence gaps; no investment, procurement, construction or financing commitment is
> authorized. The package remains on HOLD. Internal checking and successful automated tests do not
> close the independent resource, grid, legal or E&S review conditions.

### Responsibility

The project secretary/governance lead assembles the checklist from approved requirements. Domain
owners supply closure evidence; checkers verify traceability and status. Independent reviewers close
only their assigned review conditions. The named committee, officer or institution records the
decision, waiver and release within delegated authority.

## 20. `appendices_provenance_audit_trail` - Appendices: data provenance and model audit trail

### Purpose and decision question

Provide **the controlled evidence, definitions, methods, manifests and decision trail needed to
explain, reproduce and audit the report without confusing byte integrity with truth or access with
publication permission**.

### Required narrative

Explain report and run identity, contract/template/code/config/pack versions, active capabilities,
environment, seeds, validation mode, evidence cutoff, valuation date, canonical serialization and
artifact production. State dirty-tree or external-service/data-snapshot limitations. Describe what
can be recomputed, what can only be explained, and what is unavailable because of licence,
confidentiality, expiry or mutable external services.

Preserve source entity, transformation activity, derivation and responsible agent. Separate raw
source, interpreted datum, assumption, calculation and judgement. A SHA-256 digest can establish
byte identity/integrity; it does not establish authenticity, truth, legal authority, review,
confidentiality or fitness.

Record applicable capability dispositions. “Marrying the codebase” means every applicable product
capability is executed or explicitly dispositioned, not that every helper, inactive technology,
unsupported jurisdiction or synthetic lane runs. Record cross-delivery identity and current gaps;
CURRENT XLSX independently reruns and therefore requires explicit reconciliation until unified.

### Required appendices and registers

| Appendix/register | Minimum content |
|---|---|
| A. Definitions, abbreviations, units and precision | Canonical terminology, units, currencies, signs, date/period and rounding rules |
| B. Scope and applicability | Boundary, active packs/technologies, materiality, exclusions and 20-section dispositions |
| C. Input register | Supplied, enriched/resolved and derived inputs; raw value, unit, source, validation and cutoff |
| D. Source register | ID, issuer/author, title/revision, dates, locator, access/licence, hash and extraction method |
| E. Evidence register | Claim, evidence, authenticity/relevance, jurisdiction/period, limitation, review and expiry |
| F. Assumption and judgement register | Basis, owner, materiality/sensitivity, approval, replacement action and review date |
| G. Limitation/error/degradation register | Affected claims, controlled error, substitute, consequence, grade ceiling, owner and remedy |
| H. Capability disposition register | Capability, activation predicate, owning section/contract, result and explicit disposition |
| I. Methodology and model map | Canonical gateways/contracts, method versions, calculation boundary and no-duplication statement |
| J. Validation and reconciliation | Schema/pre-flight, model checks, independent oracles, cross-section/artifact results and failures |
| K. Review/finding/decision register | Human/agent roles, independence, scope, findings, responses, decisions and supersession |
| L. Run manifest | Report/case/run IDs, code/config/pack versions, input/source digests, seed, environment and timestamp |
| M. Artifact manifest | Format/MIME, producer, report/run binding, disclosure profile, timestamp, digest and supersession |
| N. Distribution and release | Audience, reliance, confidentiality, rights, expiry, redactions and exact package release decision |

### Minimum exhibits

- report lineage diagram from source/input through run/package to each artifact;
- section/capability disposition matrix;
- source-to-claim and assumption-to-output traceability tables;
- code/config/pack/run/artifact identity table with digests;
- validation/reconciliation and independent-review findings table;
- revision/supersession and distribution/redaction history; and
- machine-readable artifact locations where authorized, using meaningful link text.

### Evidence, review and applicability

This section is always applicable and grade-critical. Restricted evidence may be referenced rather
than embedded, but its existence, authority, access condition and effect remain visible. Missing
evidence is not cured by a broken link, private path or hash. The appendix must not expose secrets,
personal data, privileged advice or licensed material beyond the authorized audience.

Screening requires enough provenance to reproduce or explain material results and limitations.
Decision/lender grades require progressively stronger project evidence, independent review,
controlled decisions and artifact binding under the contract. A complete appendix cannot elevate
weak underlying evidence.

### Jurisdiction and technology applicability

All active pack IDs, versions, effective dates, sources, reviews and grade ceilings are recorded.
Inactive packs and unsupported subjects receive dispositions. Sri Lanka is labelled the first
reference pack only when used; it is never implied as a global default. Technology-specific data
rights, standards and methods remain attached to their contributions.

### Cross-section reconciliation

The appendices reconcile every section, input, output, evidence item, assumption, limitation, risk,
condition and decision. The report manifest binds the exact ordered twenty-section projection. The
artifact manifest identifies any current semantic or delivery divergence and prevents a PDF/XLSX/
API output from silently claiming another run's status.

### Fillable drafting block

- **Identity:** `[[State report/case/run, code/config/pack, cutoff and environment identities.]]`
- **Provenance:** `[[State source, transformation, agent and derivation controls.]]`
- **Reproducibility:** `[[State what can be recomputed/explained and under which limitations.]]`
- **Artifacts:** `[[List authorized artifacts, hashes, semantic parity and supersession.]]`
- **Review/release:** `[[State human/agent roles, findings, decisions, audience and package release.]]`

> **EXAMPLE - FICTIONAL WORDING ONLY:** The recorded digest confirms the identity of the cited
> source file at ingress; it does not establish that the issuer was authorized, the contents are
> correct, or the source is sufficient for the claimed grade. Those questions remain in the
> evidence and review registers.

### Responsibility

The report controller/provenance lead assembles the appendices. Data, model, evidence, security,
privacy and domain checkers verify their records. Independent reviewers record their own scope and
findings without alteration by the author. The package release authority confirms only the exact
identified artifacts and distribution rights; it does not retroactively repair missing evidence.

## E. Final issue checklist

Before any report is issued, confirm:

- all twenty section IDs appear once and in YAML order;
- every section is completed or explicitly dispositioned;
- target grade, achieved grade, run posture, review and package release are separate;
- every headline statement traces to its source section and evidence;
- all cross-section and cross-artifact reconciliations are recorded;
- unknown jurisdictions did not inherit Sri Lankan assumptions;
- synthetic/advisory output remains labelled and grade-capped;
- missing evidence, dependencies, failures, degradation and holds are visible;
- agent provenance is separate from human responsibility;
- distribution, confidentiality, reliance and publication controls are applied;
- every artifact carries the same report/run identity or states the current implementation gap;
- DBPL PDF production followed the fail-loud print contract and surfaced font provenance; and
- release remains `HOLD` unless a named authority has issued a hash-bound decision for the exact
  package and artifacts.

## F. Source basis and limitations

This template derives its contract propositions from
[`FEASIBILITY_REPORT_CONTRACT_SOURCES.md`](FEASIBILITY_REPORT_CONTRACT_SOURCES.md). No new external
proposition is introduced here. Source applicability must be rechecked for the active jurisdiction,
technology, transaction, lender framework and edition at the report's evidence cutoff. The source
ledger does not establish project compliance, professional advice, achieved grade or release.
