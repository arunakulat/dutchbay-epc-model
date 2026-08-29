# Dolphin 2 machine-contract charter

**Document status:** non-normative implementation charter and review aid
**Machine contract:** `dutchbay.feasibility_report_package.v1` / `1.0.0`
**Normative authority:** DBAY-FRC-001 v1.0.0
**Controlled human projection:** DBAY-GFR-MT-001 v1.0.0

## 1. Purpose and authority

Dolphin 2 implements only item 1 of DBAY-FRC-001 section 12.3: a strict, immutable,
machine-readable feasibility-report package and exact parity with the existing 20-section
taxonomy. [`FEASIBILITY_REPORT_CONTRACT.md`](FEASIBILITY_REPORT_CONTRACT.md) remains the normative
contract. [`GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md`](GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md)
remains the controlled human projection. This charter cannot amend either document and does not
create a competing section taxonomy.

`config/feasibility_sections.yaml`, resolved only through
`analytics.feasibility_sections.load_feasibility_taxonomy()`, remains the source of every stable
section identity and its order. The five always-applicable constraints in the package validator are
semantic enrichments taken from DBAY-FRC-001 section 8; they do not declare a second identity list.

## 2. Three-role separation

The delivery roles remain deliberately independent:

1. **Principal Python contract/formal-methods lead:** implements the typed vocabulary, immutable
   records, discriminated state variants, validators, JSON Schema and executable negative controls.
2. **Renewable-project domain specialist:** reviews whether the records and invariants can faithfully
   represent technical, power-system, financial, environmental, geospatial, social, jurisdiction
   and technology facts without false equivalence or silent omission.
3. **Audit and assurance specialist:** independently challenges evidence, review, authority,
   responsibility, manifest, distribution, state-transition and fail-closed boundaries.

The first role cannot self-approve the other two. Green tests establish contract behaviour, not
domain sufficiency, assurance acceptance, achieved grade or release authority. Human `Prepared`,
`Checked`, `Reviewed` and `Approved` assignments reject software and AI actors and require an exact,
positive, scope-bound decision. The first independent specialist review produced both a domain veto
and an assurance veto; its immutable pre-remediation receipt is
[`DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md). Only an
independent retest of the remediated exact tree can replace those dispositions. The second and
third exact-tree vetoes, their remediation and the final accepting specialist dispositions are preserved in
[`DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md`](DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md); the
immutable first-review record is not rewritten.

## 3. Implemented contract boundary and traceability

| Contract element | Machine implementation | Controlling clauses | Executable proof |
|---|---|---|---|
| Version and identity | Explicit v1 schema/contract constants, `ReportIdentity`, required UTC `captured_at` snapshot and immutable report/project/case/run binding | D1 sections 5, 10.3 and 12.2; D0 C.1 and C.3 | JSON round trip, UTC rejection, foreign-reference/identity and lifecycle chronology validators |
| Scope and pack boundary | `ScopeDeclaration`, `JurisdictionSubjectBinding`, `PackRegistry` and `PackBinding` require explicit technologies, jurisdictions, governed subjects, active versions, exact one-axis disposition packs and reciprocal contribution or unsupported refusal | D1 sections 3, 3.1, 5 and 6.2; D0 C.4 and D.3 | Supported and honestly unsupported Fictionland, absent-jurisdiction, governed-subject, two-jurisdiction, wind+BESS and unknown/untyped/unsupported-technology controls |
| Orthogonal section truths | `SectionRecord` separately records applicability, production, evidence, review, achieved grade, section release and materiality. D2 v1 accepts only section grades `ungraded` or `not_applicable` | D1 sections 4, 6 and 8; D0 D.2 and all 20 drafting blocks | State contradiction, N/A material refusal, sentinel-grade, run-mode and release tests |
| Capability reachability | A discriminated `CapabilityDisposition` union represents executed, degraded, failed, missing-input, missing-dependency, unsupported-jurisdiction, unsupported-technology, deferred and N/A outcomes | D1 sections 3.2, 6.1 and 9.1; D0 B, D.2 and per-section capability expectations | Unknown discriminator, exact outcome-to-section and unsupported-pack tests |
| Facts and provenance | Typed input, source, output, claim, evidence, assumption, judgement and derivation registers preserve distinct meanings, exact scope and reciprocal references | D1 sections 5, 8.1, 10.1 and 10.2; D0 D.1 and section 20 | Claim/evidence, section/input/output/source and derivation property mutations; cutoff, expiry, scope, period and authenticity controls |
| Constraints and review | Typed limitation, error, finding, review, decision, responsibility, validation and reconciliation registers; review/decision subjects bind exact report/run/section/claim/evidence or pack/version/grade/effective period; the root requires one honest record for each of the six reconciliation families | D1 sections 5, 6.1, 8.2, 9.1 and 9.4; D0 D.7, section responsibilities and section 20 | Missing/duplicate/all-same reconciliation, unrelated/reused review, AI sign-off, snapshot chronology, all-role responsibility and assured-pack controls |
| Run and delivery identity | `RunManifest`, `ArtifactManifest`, structured disclosure bindings, `DistributionRegister` and `PackageRelease` bind exact report/run/artifact/source/control identities and a bounded package snapshot | D1 sections 5 and 10.3-10.6; D0 C.1, C.5, D.5 and section 20 | Manifest completeness, validation/responsibility/artifact/review/decision chronology, restricted-source/public-artifact and exact distribution/release controls |
| Strict publication shape | Frozen Pydantic v2 models reject unknown fields and implicit Python-side coercion; generated JSON Schema is Draft 2020-12 valid | D1 sections 9.2, 12.1 and 12.2 | Pydantic strict controls plus independent `jsonschema` schema/instance validation |
| Taxonomy parity | The root requires exactly one record for every resolver-supplied ID, in resolver order | D1 sections 8, 9.3 and 12.1(1); D0 numbered sections 1-20 | Missing, duplicate, unknown and Hypothesis-generated reorder controls |
| No automatic authority | The v1 root accepts only package `achieved_grade=ungraded` with `grade_decision_id=None`; non-sentinel grade vocabulary is reserved for a future version with a typed grade-policy receipt. Positive decisions alone can authorize review, assurance or release | D1 sections 4, 7, 10.6 and 12.1(8),(17); D0 C.2, D.2 and D.7 | Every non-sentinel grade, unrelated grade decision, denial outcome, weak signatory, CI/schema, `RunMode` and AI-authority controls |

Canonical numeric values use precision-preserving lexical text plus an explicit lexical type, unit
and precision. This avoids binary-float loss and keeps display rounding outside the semantic
package. Digest fields are typed identities only; Dolphin 2 neither computes nor promises canonical
serialization digests.

## 4. Independent-veto remediation boundary

The initial domain and assurance vetoes exposed combinations that were structurally valid but
semantically false. The remediated v1 contract now fails closed on each class, with D0/D1-traceable
executable controls:

- **Grade authority (domain 1-3; assurance A-B):** package grade is always `ungraded`, section grade
  is `ungraded` or N/A, and `grade_decision_id` is absent. This removes the prior unsafe half-policy;
  it does not implement Dolphin 3 aggregation.
- **Reciprocal graph (domain 4, 8, 10; assurance C and E):** claim/evidence,
  section/claim/evidence/output/input/source, derivation/input/output and pack/section/capability
  edges are checked in both directions. D1 sections 5, 8.1 and 10.1-10.3 control these edges.
- **Scope and packs (domain 5-7; assurance D and F):** supported packs require real structural
  sources, passed validation, limitations and declared degradation/substitution boundaries;
  assured packs additionally require a current exact-version independent review and positive,
  evidence-backed assurance decision. Source/default jurisdiction, technology, project boundary,
  period, dates and authenticity cannot escape their pack or claim scope (D1 sections 3.1, 5, 6.2,
  8.1 and 10.1-10.2).
- **N/A and reconciliation (domain 9; assurance E):** N/A forbids current production material and
  requires the same exact positive scope decision as its N/A capability. A passed reconciliation
  requires a typed D1 section 8.2 family and real section/output operands.
- **Human and release authority (assurance G-J):** completed reviews, performed responsibility,
  assurance and release require typed positive outcomes, exact subjects and verified human or
  institutional signatories with organization and authority basis. Independent evidence requires a
  current exact claim/evidence review. Prose cannot reverse a typed denial.
- **Distribution (assurance K):** every public artifact that enumerates a restricted or
  no-publication source requires a source-and-artifact-bound redaction, omission or reference-only
  treatment with a passed validation. A full artifact must enumerate the complete source registry
  (D1 sections 10.4-10.6; D0 C.5 and D.5).

The second independent pass added further strict boundaries without importing Dolphin 3 policy:

- every performed human role uses the exact verified performer as its positive decision authority;
- assured ownership, human review and assurance authority require identity, organization, authority
  and producer-independence appropriate to each role;
- a source effective after cutoff cannot support the current package, and review/assurance evidence
  must be relevant, usable and sourced from the exact pack because v1 has no typed compatible-source
  edge;
- `captured_at` is the package lifecycle snapshot: report/run creation, artifacts, decisions,
  completed reviews and authorized release cannot be in its future. Report-bound reviews and
  decisions cannot predate report creation, while a pack review may legitimately predate it.
  Evidence cutoff remains only the source/evidence currency boundary;
- a typed release `HOLD` carries no authority, decision or decision-date metadata, and pack
  assurance binds exactly the qualifying review set; and
- the six reconciliation-family totality, governed-jurisdiction mapping and exact single-axis pack
  constraints are explicit. Controlled two-jurisdiction and wind+BESS fixtures prove only the type
  boundary, not real-project validation or asset topology.

The third independent pass adds one final narrow clarification. `JurisdictionSubjectBinding` uses
the neutral `disposition_pack_id`: supported and assured packs contribute as before, while a known
unsupported jurisdiction is represented by an exact `UNSUPPORTED` pack and matching typed
unsupported capability for every reciprocally bound affected section. It therefore fails closed
without inventing a supporting pack, falling back to Sri Lanka or silently omitting the section.
Duplicate binding IDs and duplicate `(jurisdiction, subject_kind, subject_id)` mappings are refused,
while multiple distinct governed subjects in one jurisdiction remain expressible.

Lifecycle event timestamps are bounded by the captured package snapshot. Report responsibilities
follow report creation, precede their supporting decisions and complete by capture; artifacts exist
between report creation and capture; pack assurance follows every qualifying review and its signed
decision; validation checks and section production events cannot occur in the snapshot's future.
Authorized release names the exact current distribution controls for exactly its artifacts; `HOLD`
names none. These event rules do not turn prospective valuation, effective-until or expiry horizons
into execution times. Evidence cutoff remains the source/evidence currency boundary.

D1 section 8's example permits a section to link pack identities while also being N/A, but it does
not specify whether those links are historical, applicable or controlling. D2 resolves that
ambiguity conservatively: pack links may remain as scope/coverage identity, while N/A forbids all
current production material and the exact scope decision controls the disposition. This is a
documented v1 interpretation, not a change to D1.

## 5. Current semantic holes and exclusions

The following remain visible work, not implied conformance:

- There is no global `ProjectCase` input contract or canonical per-section result contract yet.
- Existing evaluation/orchestration does not yet build `FeasibilityReportPackage`; current optional
  `None` paths have not been mapped into dispositions.
- Applicability/materiality policy, grade aggregation, grade ceilings and release policy remain
  Dolphin 3 work. D2 retains non-sentinel grade vocabulary for forward compatibility but the v1
  root cannot assert those grades until a future typed grade-policy receipt exists.
- Canonical serialization, payload/section digest production, migration readers and privacy-aware
  manifest generation remain Dolphin 4 work.
- HTML, API, XLSX, PDF and DBPL do not yet consume this package; adapter convergence, execution spies,
  semantic parity and rendered checks remain later Dolphins.
- The Sri Lankan reference material has not been extracted into an assured jurisdiction pack and no
  second real jurisdiction or technology pack has been validated.
- No finance, wizard, report orchestration, renderer, adapter, audit ledger, P01/P02/P03, F5-02 or
  live release state is changed. Existing reports are not retroactively graded.
- JSON Schema validates the portable data shape. Cross-registry, taxonomy, authority and conditional
  invariants are enforced by the Pydantic root and its tests because JSON Schema cannot express all
  of those relational constraints without a second policy engine.
- Current `technology_ids` are technology-type identifiers, not project asset instances. Turbine,
  battery, hybrid, shared-facility and allocation topology belongs in the additive Dolphin 3
  `ProjectCase` facade.

## 6. Import direction and versioning

The new package is a pure analytics contract layer. It depends only on the existing taxonomy
resolver and `RunMode` vocabulary; it does not import finance, orchestration, renderers, adapters or
`analytics.contracts_v14`. `analytics.contracts_v14` re-exports the new surface additively, while all
existing v14 classes and calculations remain untouched. This direction permits old v14 producers
to remain operational while later facades translate their governed outputs into the package.

The v1 package is strict and fail-closed. Additive fields still require an explicit compatibility
decision because strict readers reject unknown fields. Renames, removals or semantic changes require
the DBAY-FRC-001 section 12.2 major-version and migration discipline. Historical packages remain
bound to the schema, engine, code and pack identities under which they were created.

## 7. Forward delivery sightline

This sightline guides later Dolphins; it is expressly outside Dolphin 2 implementation scope:

1. Introduce global `ProjectCase` and per-section result contracts as an **additive facade** over the
   existing v14 evaluation engine. Preserve the existing engine and migrate incrementally; do not
   attempt a big-bang rewrite.
2. Complete **Golden Path 1**: DutchBay/Sri Lanka produces the definitive, complete report from one
   governed package through every required delivery mode.
3. Complete **Golden Path 2**: a second real jurisdiction and project validate that jurisdiction and
   technology abstractions are genuine rather than Sri Lankan assumptions with renamed labels.
4. Productize only after semantic convergence: web wizard, client accounts, durable projects, report
   download, portfolio management, licensing and commercial operations consume the same contracts.
5. Consider native or lower-level implementation only after profiling production workloads. Extract
   only measured, justified kernels; preserve Python orchestration and the semantic/audit boundary.

## 8. Independent handoff disposition

The domain and assurance specialists independently reran the
counterexamples recorded in `DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md` and
`DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md` against the same exact remediated implementation/test
tree and reviewed:

- whether pack contribution, section applicability and capability dispositions cover real multi-
  technology and multi-jurisdiction projects without hidden Sri Lankan fallback;
- whether evidence, source, assumption, judgement, limitation and reconciliation meanings remain
  distinct across lender-, legal-, grid-, E&S- and resource-material claims;
- whether every human responsibility, independent review, grade and release authority path fails
  closed and remains bound to exact report/run/artifact/distribution identities and honest event
  chronology;
- whether the unsupported-jurisdiction disposition refuses wrong packs, fallbacks and silent section
  omission while preserving the supported/assured contribution path; and
- whether any field or invariant prematurely encodes policy that belongs to Dolphin 3 or hashing and
  migration behaviour that belongs to Dolphin 4.

Both final specialist dispositions are `ACCEPTED` within that bounded D2 scope and are preserved in
the rereview record with their verification receipts and exact fingerprints. They are specialist AI
reviews, not statutory assurance, external audit, verified human professional sign-off, lender
acceptance, achieved-grade authority or release authority. The reference fixture therefore remains
`achieved_grade=ungraded` and `package_release.status=hold`, and every live audit/release `HOLD`
remains unchanged.
