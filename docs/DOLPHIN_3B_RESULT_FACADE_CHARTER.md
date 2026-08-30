# Dolphin 3B result-facade charter

**Document status:** non-normative implementation charter and review aid — **design proposed, not
implemented**
**Proposed machine contract:** `dutchbay.section_result_facade.v1` / `1.0.0`
**Normative authority:** DBAY-FRC-001 v1.0.0
**Controlled human projection:** DBAY-GFR-MT-001 v1.0.0
**Upstream case contract:** `dutchbay.project_case.v1` / `1.0.0` (Dolphin 3A, merged `cbc0e4c`)
**Target package contract:** `dutchbay.feasibility_report_package.v1` / `1.0.0` (Dolphin 2)

## 1. Purpose and authority

Dolphin 3B implements the contract half of **DBAY-FRC-001 section 12.3 item 2, "Orchestration and
disposition"**: *build one package from the existing evaluation gateway; map all 20 sections and
applicable capability outcomes, including every current optional `None` path.* Dolphin 2 delivered
item 1 of that same sequence.

Operationally this is item 2 of the Dolphin 3 controlled scope recorded in
[`SESSION_HANDOVER_2026-08-29.md`](SESSION_HANDOVER_2026-08-29.md) section 5: *typed per-section
result and disposition contracts that carry existing v14 outputs into the Dolphin 2 package without
copying finance or domain mathematics.* Together with Dolphin 3A it completes the
"additive `ProjectCase` and per-section result facade" of item 1 there.

The normative clause splits cleanly across two dolphins: D3B defines the typed dispositions and the
shape that carries the outputs, and **D3C** builds the package from the gateway (section 10). The
phrase *including every current optional `None` path* is normative, not advisory — it is why
section 6 treats absent-versus-defaulted as the increment's central obligation rather than an
implementation detail.

[`FEASIBILITY_REPORT_CONTRACT.md`](FEASIBILITY_REPORT_CONTRACT.md) remains the normative contract
and [`GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md`](GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md)
the controlled human projection. This charter amends neither, creates no competing section taxonomy,
and takes every stable section identity and order from
`analytics.feasibility_sections.load_feasibility_taxonomy()` over `config/feasibility_sections.yaml`.

**This document is a design for review. No implementation, test or contract module accompanies it.**
It exists so the domain and assurance specialists can veto or accept the design *before* code is
written, which is how Dolphin 2 and Dolphin 3A were actually governed.

## 2. Increment boundary

**In scope.** A strict, immutable, engine-agnostic contract describing, for one canonical section of
one report run: which capability disposition applies, which values that section carries, each
value's provenance and declared precision, and what was absent, defaulted or refused.

**Out of scope, deliberately.** Everything below belongs to a later reversible dolphin and must not
appear in D3B:

- the mapping code itself — calling the engine and populating these types is **D3C** (section 10);
- 20-section package assembly, register construction or `FeasibilityReportPackage` emission;
- grade, review, release or achieved-grade inference of any kind;
- canonical whole-document serialization, hashing or signing policy (Dolphin 4);
- any FastAPI route, transport adapter, UI or form, ORM, persistence, authentication or deployment;
- any change to `analytics/contracts_v14.py`, `finance/`, `app/`, `api/`, `VERSION` or any KPI.

D3B adds no finance mathematics. It defines where a number may be *carried*, never how it is
*derived*. `finance/irr.py` remains the sole definition of IRR, XIRR and NPV, and
`analytics.evaluation_v14.evaluate_with_overrides()` remains the sole evaluation gateway.

## 3. Three-role separation

Unchanged from Dolphin 2, and binding on this increment:

1. **Principal Python contract/formal-methods lead** — implements the typed vocabulary, immutable
   records, discriminated variants, validators, generated schemas and executable negative controls.
2. **Renewable-project domain specialist** — reviews whether the result contracts can faithfully
   carry technical, resource, grid, cost, revenue and financial facts without false equivalence,
   invented precision or silent omission.
3. **Audit and assurance specialist** — independently challenges provenance, disposition,
   absent-versus-defaulted, unit, precision and fail-closed boundaries.

The first role cannot self-approve the other two. Per `TEST-01`, a change whose only evidence is
tests written alongside it is unverified however green, so the D3B contract must answer to an oracle
that did not originate in the same change. Green tests establish contract behaviour — never domain
sufficiency, assurance acceptance, achieved grade or release authority.

## 4. The seam this increment closes

D3B sits between two contracts that were designed to different standards. The gap is the whole
problem, and the charter states it exactly rather than assuming it away.

**Upstream — `analytics/contracts_v14.py`.** Frozen dataclasses with a `ContractMixin.model_dump()`
compatibility shim. Representative of the whole surface, `ScenarioResult` carries:

| Shape | Example fields | Consequence for the facade |
|---|---|---|
| Binary `float` scalars | `project_npv`, `project_irr`, `min_dscr`, `max_debt_usd` | No decimal precision, no unit, can be NaN/Inf |
| Untyped mappings | `kpis`, `annual_rows`, `debt_result`, `metadata`, `config` | Keys are unenumerated and may drift silently |
| Optional sub-results | `wacc`, `cashflow`, `equity_performance`, `fx_block`, `debt_profile` | `None` is overloaded: not applicable, not run, or not populated |
| Numeric defaults | `WaccComponents.risk_free_rate = 0.0`, `wacc_prudential = 0.0`, `target_equity_to_value = 1.0` | A default is indistinguishable from a computed value once serialized |

Units survive only inside field names (`max_debt_usd`, `*_pct`, `*_years`), and there is no
provenance, no run binding and no disposition vocabulary anywhere in the dataclasses.

**Downstream — `analytics/feasibility_report_contract/`.** Strict frozen Pydantic v2 models that
refuse unknown fields and implicit coercion. The relevant targets:

- `CanonicalValue(value_type, value: str, unit, precision)` — precision-preserving lexical text;
  **rejects any numeric without an explicit unit** and requires a finite decimal;
- `OutputReference(output_id, report_id, run_id, section_ids, producing_contract, producing_version,
  output_class, locator, value, digest, warning, derivation_ids)` — where a carried value already
  has a home, including a mandatory persistent warning on `OutputClass.SYNTHETIC`;
- `SectionRecord` — seven orthogonal truths (applicability, production, evidence, review, release,
  target grade, achieved grade) plus materiality and reciprocal register references;
- the nine-member `CapabilityOutcome` union: `executed`, `degraded`, `failed`,
  `not_run_missing_input`, `not_run_missing_dependency`, `not_run_unsupported_jurisdiction`,
  `not_run_unsupported_technology`, `intentionally_deferred`, `not_applicable`.

**The gap, stated plainly.** Five conversions have no honest default:

1. `float` → decimal lexical text is a **precision claim** the float cannot support;
2. `dict[str, Any]` → typed register requires an **enumeration** that does not exist upstream;
3. `None` or a defaulted `0.0` → a value requires deciding **absent versus computed**;
4. every numeric needs a **unit** that upstream encodes only in a field name;
5. every carried value needs **provenance** and a run binding that upstream does not have.

D3B's contract exists to make each of those five an explicit, reviewable, fail-closed declaration
instead of an implicit conversion.

## 5. Proposed contract boundary

| Contract element | Proposed machine implementation | Controlling clauses |
|---|---|---|
| Identity and version | Mandatory `schema_id = dutchbay.section_result_facade.v1` and `contract_version = 1.0.0` with no defaults; unknown or future values fail closed, exactly as D3A does | D1 §5, §12.2 |
| Section binding | `section_id` validated against the taxonomy SSOT, plus exact `report_id`/`run_id`/`case_id` binding to the D3A `ProjectCase` and the D2 report identity | D1 §8, §9.3, §12.1(1) |
| Disposition | One discriminated `SectionResultDisposition` reusing the D2 `CapabilityOutcome` vocabulary verbatim. A non-`executed` disposition **may carry no values at all** — refusing values is the point | D1 §3.2, §6.1, §9.1 |
| Carried value | `CarriedValue` binding one `CanonicalValue` to its declared unit, declared precision, `OutputClass`, producing contract and version, and the upstream field path it came from. The `CanonicalValue.value` is the **full unrounded** lexical value; `precision` is declared metadata and never truncates it | D1 §5, §10.1, §10.2 |
| Value provenance | Every `CarriedValue` names the exact upstream contract type and attribute path (e.g. `contracts_v14.ScenarioResult.project_irr`), never a free-text label | D1 §10.1, §10.2 |
| Absent versus defaulted | A discriminated `ValueAbsence` variant — `not_computed`, `upstream_none`, `upstream_default`, `not_representable` — carried **instead of** a value, never alongside one. Each variant additionally carries the D1 §6.1 quartet: the exact missing item, affected claims, consequence and remedy. A bare reason tag is a generic `None` by another name and is invalid | D1 §6.1, §8.2 |
| Unrecognized upstream keys | Unknown mapping keys are carried explicitly as `UnrecognizedUpstreamKey` records or refused; they are never silently dropped | D1 §9.2, §12.1 |
| No authority | The facade carries no grade, review, release or achieved-grade field. It cannot express them, so it cannot infer them | D1 §4, §7, §10.6, §12.1(8),(17) |
| Strict shape | Frozen Pydantic v2, extra-field refusal, stable discriminators, Draft 2020-12 generated schemas, transport-neutral | D1 §9.2, §12.1, §12.2 |

## 6. Fail-closed hazards this increment must refuse

These are the failure modes a naive facade would introduce. Each needs an executable negative
control before the increment can be accepted.

1. **Defaulted zero presented as a computed value.** D1 §12.3(2) requires covering *every current
   optional `None` path*, and this is that requirement's sharpest edge. `WaccComponents` defaults
   `risk_free_rate`, `wacc_prudential` and others to `0.0`; `ScenarioResult.wacc` and
   `discount_rate_used` default to `None`. A facade that maps `0.0` to canonical decimal `"0"`
   asserts a *computed* zero risk-free rate.
   **This repository has already been bitten twice by exactly this shape** — see
   `tests/lint/test_no_decorative_discount_rate.py` and `tests/lint/test_no_decorative_grid_loss.py`,
   both of which record audit findings where an inert value advertised a haircut or hurdle the
   engine never applied. The facade must distinguish *computed*, *upstream default* and *absent*,
   and must never let the second two reach a `CanonicalValue`.
2. **Precision inflation across the float boundary.** Neither `repr()` nor a fixed format is a
   precision claim, and they fail in opposite directions:

   | Upstream double | `repr` | `f"{x:.15f}"` | `f"{x:.17g}"` |
   |---|---|---|---|
   | `0.1` | `0.1` | `0.100000000000000` | `0.10000000000000001` |
   | `0.1 + 0.2` | `0.30000000000000004` | `0.300000000000000` | `0.30000000000000004` |
   | `1/3` | `0.3333333333333333` | `0.333333333333333` | `0.33333333333333331` |

   `repr` leaks representation error into a lender-facing figure; the fixed format **manufactures a
   clean `0.300000000000000` that the stored double is not**, which is the more dangerous of the two
   because it looks authoritative. `CanonicalValue.precision` must come from a **declared per-field
   rule** reviewed by the domain specialist, never from the decimal expansion of the float at
   runtime.
3. **Unit invention.** `CanonicalValue` refuses a numeric without a unit, and the only upstream unit
   evidence is the field name. Binding must come from a **static, reviewed field-to-unit table**;
   parsing `max_debt_usd` for a `usd` suffix at runtime is forbidden, because it silently succeeds
   on `wacc_label` and fails open on `min_dscr`.
4. **Non-finite floats.** `CanonicalValue` requires a finite decimal; v14 floats may be NaN or ±Inf.
   These map to a `failed` or `degraded` disposition with a stated reason — never to a value, and
   never to a substituted zero.
5. **Silent key drift, and a loss that happens before the facade sees anything.** `kpis`,
   `debt_result` and `metadata` are unenumerated, so a key that appears, disappears or is renamed
   upstream must surface rather than vanish. Worse, the gateway **already drops keys silently**:
   `evaluate_with_overrides(return_full_result=False)` — the parameter's default — returns
   `normalize_kpi_dict(raw_kpis)`, which `float()`-coerces every entry and `continue`s past any
   failure with only a `logger.debug`. A KPI that became `"N/A"` upstream is therefore already
   gone before any facade code runs, and its absence is indistinguishable from never having been
   emitted. D3C must consume `return_full_result=True` for this reason (section 10).
6. **Section misattribution.** A value must not be attributed to a section that did not produce it.
   Section binding is declared per upstream field and reviewed, not inferred from name similarity.
7. **Authority leakage.** No grade, review, release, assurance or bankability meaning may be
   expressed or implied. A `degraded` disposition is not a grade, and an `executed` disposition is
   not evidence sufficiency.

## 7. Import direction and versioning

`analytics.feasibility_report_contract` stays a leaf package. **D3B must not import
`analytics.contracts_v14`**, `analytics.evaluation_v14`, `finance/` or any engine internal: the
facade defines the *target* shape, and D3C supplies the mapping in a separate module that imports
both sides. This keeps D3B independently reversible and prevents the contract package from acquiring
an engine dependency it can never shed.

Upstream field paths are therefore recorded as **text identities**, not imported symbols. That is a
deliberate trade: it costs a static link and buys a contract that can be reviewed, versioned and
reverted without touching the engine. D3C's mapping is where a drifted path must fail loudly, and a
control proving that is named in section 8.

Versioning follows D3A: `schema_id` and `contract_version` are mandatory with no defaults, unknown
values fail closed, and a breaking change takes a new major identity rather than loosening v1.

## 8. Negative controls the implementation must ship

Per `VERIFY-01`, a guard never observed to fail is itself an unverified claim, so each control below
ships with the demonstration that it fires:

- a defaulted `0.0` and an upstream `None` each produce a `ValueAbsence`, and **no** path exists
  from either to a `CanonicalValue`;
- NaN, +Inf and -Inf each produce a `failed`/`degraded` disposition, not a value and not a zero;
- a numeric without a declared unit is refused at construction;
- a declared precision exceeding the reviewed per-field rule is refused;
- a non-`executed` disposition carrying values is refused;
- a `ValueAbsence` carried alongside a value for the same field is refused;
- an unknown `kpis` key is surfaced, never dropped;
- an unknown discriminator, unknown `schema_id` and unknown `contract_version` each fail closed;
- a `section_id` absent from the taxonomy SSOT is refused;
- an `OutputClass.SYNTHETIC` value without a persistent warning is refused;
- generated Draft 2020-12 schemas validate, and round-trip ingress equals the original object;
- **an independent oracle** — a fixture derived from a real recorded v14 run rather than from the
  facade's own construction — proves the contract can carry a genuine result without loss.

## 9. Resolved design questions

An earlier revision of this charter posed five questions as open. Research against DBAY-FRC-001,
the D2 validator and the engine **resolved all five**, and showed that four of them were
**mis-posed** — they offered choices the controlling contract does not leave open, and in two cases
every option on offer was wrong. Each resolution below is recorded with the evidence that settles
it, so a reviewer can overturn it on evidence rather than preference. What remains for the
specialists (section 9.6) is domain data, not design choice.

### 9.1 Precision — carry unrounded, declare per field

*Posed as per-field versus per-type rounding. Both options were illegal.* D1 §5 states: "Canonical
numbers MUST carry units and sufficient unrounded precision. **Display rounding belongs to an
adapter policy and MUST NOT alter the canonical value.**" The canonical value is therefore never
rounded by the facade, and the question is only what `precision` *declares*.

It must be declared **per field**, and the repository's own canonical KPI vector proves a uniform
per-type rule destructive. From `tests/_canon.py`, whose docstring instructs "keep them at full
precision":

| Canonical KPI | Value | A uniform rule breaks it |
|---|---|---|
| `LENDER_PROJECT_IRR` | `-0.001166233356501311` | 2 dp → `-0.00`; even 6 dp loses the fourth significant figure of a near-zero IRR |
| `LENDER_PROJECT_NPV` | `-91810995.06051566` | 6 dp reports a USD figure to sub-microcent noise |
| `LENDER_MIN_DSCR` | `1.3` | a covenant threshold, meaningful to 2 dp, not a measurement |

One rule cannot serve a vector spanning `1e-3` to `1e8` that mixes ratios, currency and covenant
thresholds. **The policy text binds to `DerivationRecord.precision_policy`**, which already exists
in D2 as a mandatory `NonEmptyText` field — D3B must not invent a parallel mechanism. D1 §10.4
requires every delivery to preserve "precision policy" for each exposed fact, so it is a
first-class carried fact rather than an implementation note.

### 9.2 Value-carrying — a pre-package projection, values stored once

*Posed as values-directly versus identities-only. It is a false dichotomy.* D2 is already
normalized and reciprocal: `SectionRecord.output_references` holds output **IDs**, the
`OutputReference` records live in `output_register`, and each record carries `section_ids` back.
`FeasibilityReportPackage` validates both directions.

A section-level facade object carrying values directly would create a **second canonical home for
the same fact**, which is the shape D1 §10.4 forbids when it says an adapter "MUST NOT become a
second canonical financial model or calculate a competing headline value". So the facade is a
**pre-package projection**: it carries the `OutputReference`-shaped records themselves — which is
what makes it useful standalone — plus a section-level disposition that references them by ID.
D3C then splits one projection into its `SectionRecord` and its register entries with no value
duplicated anywhere.

### 9.3 Unrecognized keys — the question is moot as posed

*Posed as refuse-versus-carry at the facade.* The loss happens **upstream of the facade entirely**,
so neither option is reachable. `normalize_kpi_dict` `float()`-coerces every KPI and skips failures
with a `logger.debug`; `evaluate_with_overrides` runs it on the `return_full_result=False` path,
which is the parameter's default. A KPI that became a string upstream has already vanished.

Three consequences follow, and they are requirements rather than preferences:

1. **D3C consumes `return_full_result=True`**, never the normalized dict, so the facade sees the
   raw payload rather than a pre-filtered one.
2. The facade carries a **declared expected-key set per section**. A declared key absent from the
   payload is an absence carrying the D1 §6.1 quartet; an undeclared key present in the payload is
   surfaced as `UnrecognizedUpstreamKey`. Neither is dropped.
3. Refusing the whole result is rejected: it would make any benign upstream addition a hard
   failure, and D1 §6.1 already demands the finer-grained answer.

### 9.4 Annual rows — carry as a digest-bound artifact output, do not type it

*Posed as type-now, defer, or exclude. Excluding is not available* — D1 §14 requires "annual/periodic
revenue, cost, tax, cash-flow and funding statements" as minimum report meaning. But typing a
per-year schema into the contract duplicates a mechanism D2 already has: `OutputReference.value` is
**optional** while `locator` is **required**, so a table-shaped output is expressed as `locator`
plus `digest` with `value=None`, bound to an `ArtifactRecord` carrying format, MIME type, producer,
`content_digest` and confidentiality.

v1 therefore carries `annual_rows` as a digest-bound artifact output. Typing per-row semantics is
revisited only when a consumer needs to reason about individual rows inside the contract, which no
current D1 clause requires.

### 9.5 Engine-less sections — a category error, not a choice

*Posed as `not_applicable`, `intentionally_deferred`, or no record. All three are wrong.*

"No record" is refused twice over: D1 §8 states "Every report carries a record for every
identifier", and the D2 validator enforces `sections` containing *exactly* the taxonomy SSOT IDs in
resolver order. Silent omission is impossible by construction.

`not_applicable` is worse than wrong — it is contract-violating. Per D1 §8, sections 18 and 19 are
**"Always applicable"**, section 8 is "ordinarily material", section 9 is "applicable unless a
documented scope rule establishes otherwise", and sections 3 and 7 are applicable to any physical
project. D1 §6.1 adds that `not_applicable` "cannot be inferred from missing data" and requires an
explicit project-scope rationale and approval basis, and D1 §17 makes the doctrine explicit: "Not
running an available analysis is `intentionally_deferred`, not inapplicability."

The underlying mistake is a category error. **A capability disposition is not a section
applicability.** D1 §3.2 scopes dispositions to *capabilities*, each of which "MUST identify its
owning contract, applicable sections, activation predicate, execution result and disposition". A
narrative section has no engine capability, so it gets **no capability disposition at all** — not a
`not_applicable` one. The facade covers all twenty sections, and for the engine-less six it emits
an empty capability set, leaving applicability to the human and pack authority where D1 puts it.

### 9.6 What remains genuinely open

Only two items need a specialist ruling rather than a contract reading:

1. **The per-field precision table itself.** Section 9.1 settles that it is per-field and unrounded;
   the domain specialist must supply the actual meaningful precision for each carried KPI. That is a
   domain judgement no amount of code reading produces.
2. **The unit table for `float` fields.** Hazard 3 in section 6 forbids parsing field names at
   runtime, so the
   static field-to-unit binding needs domain sign-off — particularly where a name is silent about
   its unit (`min_dscr`, `project_irr`) or where nominal/real basis matters.

## 10. Forward sightline: Dolphin 3C

Outside D3B implementation scope, recorded so the increment boundary is legible:

1. **D3C** — map only through `analytics.contracts_v14` and
   `analytics.evaluation_v14.evaluate_with_overrides()`, preserving the existing engine and import
   direction with no big-bang rewrite. D3C proves absent, unsupported, failed, degraded and executed
   mappings with negative controls, and is where the declared unit and precision tables become
   executable and where a drifted upstream field path must fail loudly. Per section 9.3 it **must
   call the gateway with `return_full_result=True`**: the default path returns
   `normalize_kpi_dict(...)`, which has already discarded every non-numeric KPI before the mapping
   can see it.
2. **Golden Path 1** — DutchBay/Sri Lanka produces a complete report from one governed package
   through every required delivery mode.
3. **Golden Path 2** — a second real jurisdiction and project validate that the jurisdiction and
   technology abstractions are genuine rather than Sri Lankan assumptions relabelled.
4. **Productization** — web wizard, accounts, persistence, downloads, portfolios and licensing,
   only after semantic convergence.
5. **Performance** — measurement first; only justified native kernels extracted, with Python
   retaining orchestration and the contract/audit boundary.

## 11. Independent review disposition

**Not yet reviewed.** No domain or assurance disposition exists for this charter. Until both are
recorded against an exact tree, this design is a proposal only, and nothing in it establishes
contract sufficiency, domain sufficiency, achieved grade, package approval or release authority.

Issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) remains `OPEN` with 0 of
23 controls checked, and every Board, lender, audit and release `HOLD` remains in force. This
charter checks no control and lifts no `HOLD`.
