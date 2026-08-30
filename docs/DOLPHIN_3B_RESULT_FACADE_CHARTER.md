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
| Carried value | `CarriedValue` binding one `CanonicalValue` to its declared unit, declared precision, `OutputClass`, producing contract and version, and the upstream field path it came from | D1 §5, §10.1, §10.2 |
| Value provenance | Every `CarriedValue` names the exact upstream contract type and attribute path (e.g. `contracts_v14.ScenarioResult.project_irr`), never a free-text label | D1 §10.1, §10.2 |
| Absent versus defaulted | A discriminated `ValueAbsence` variant — `not_computed`, `upstream_none`, `upstream_default`, `not_representable` — carried **instead of** a value, never alongside one | D1 §6.1, §8.2 |
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
5. **Silent key drift.** `kpis`, `debt_result` and `metadata` are unenumerated. A key that appears,
   disappears or is renamed upstream must surface, not vanish.
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

## 9. Open questions for the specialists

Answers change the contract, so they are asked before implementation rather than assumed:

1. **Precision policy.** Should declared precision be per-field (reviewed, static) or per-value-type
   (uniform, e.g. all ratios to 6 decimal places)? Static per-field is more honest and more work.
2. **Value-carrying scope.** Should a `SectionResult` carry values directly, or only
   `OutputReference` identities with the values living in the D2 `OutputRegister`? The second is
   more normalized but makes the facade useless standalone.
3. **Unrecognized keys.** Refuse the whole result, or carry the keys explicitly and let the package
   validator decide? Refusing is safer; carrying survives benign upstream additions.
4. **Annual rows.** `annual_rows: list[dict[str, Any]]` is a per-year table, not a scalar. Does D3B
   type it now, defer it to D3C, or exclude time series from v1 entirely?
5. **Sections without v14 outputs.** Sections 3, 7, 8, 9, 18 and 19 have no engine output at all.
   Do they get a `SectionResult` with `not_applicable`/`intentionally_deferred`, or no record?

## 10. Forward sightline: Dolphin 3C

Outside D3B implementation scope, recorded so the increment boundary is legible:

1. **D3C** — map only through `analytics.contracts_v14` and
   `analytics.evaluation_v14.evaluate_with_overrides()`, preserving the existing engine and import
   direction with no big-bang rewrite. D3C proves absent, unsupported, failed, degraded and executed
   mappings with negative controls, and is where the declared unit and precision tables become
   executable and where a drifted upstream field path must fail loudly.
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
