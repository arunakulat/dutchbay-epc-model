# Dolphin 3A remediation rereview record

**Record status:** second independent domain veto under PERSIST-01
**Exact reviewed candidate:** `6e6f07ad9f757af91b155d4776d54d617ccce7ba`
**Exact reviewed base/live main:** `782c9588ef2685fcf0608d48f7745493aaa15b78`
**Pull request:** `#1191`, open and draft at the reviewed head
**Review role:** renewable-project domain specialist
**Authority boundary:** this specialist AI review addresses only Dolphin 3A contract-domain
sufficiency. It is not statutory or professional assurance, engineering certification, external
audit, lender acceptance, achieved-grade authority, package approval, package-release authority,
or permission to alter any project, audit, Board, lender, F5, or release `HOLD`.

## 1. Relationship to the first review

[`DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md) is the
immutable first-review record. It remains the controlling evidence for the original
`D3A-DOM-01` through `D3A-DOM-09` veto at candidate
`efba1e79c1ce400fed13e6fd90a9d31be5a77bbd`.

The first remediation addressed those nine findings and was committed at `ce10721`. CI then
exposed a Black-versus-Ruff formatting conflict in one test assignment. The reviewer was stopped
before issuing a disposition, the assignment was expressed in a stable form accepted by both
formatters, the Black gate was added to the handover, and the full domain rereview restarted at
`6e6f07ad9f757af91b155d4776d54d617ccce7ba`. This record preserves that second exact-head review.

## 2. Exact second-review binding

The reviewer independently confirmed that local `HEAD`, the local remote-tracking topic ref, the
live remote topic branch, and the PR head were all:

```text
6e6f07ad9f757af91b155d4776d54d617ccce7ba
```

The worktree was clean. The reviewer made no file, Git, GitHub, PR, issue, audit-ledger, or
release-state mutation. The exact reviewed fingerprints were:

```text
c8cf4218848f2545f0e4b8e1213709f192e2ce589865543f6149de9dbfd1bba7  analytics/feasibility_report_contract/project_case.py
c47038ff13e6135a9f8fe33c57ef0aacc424d8eab233e6f880c5d796b7ba8f5d  analytics/feasibility_report_contract/__init__.py
5cf12a6cac03204f6938726f835221de642054d00e2de64f6567eeaf6f4b965a  tests/contracts/test_project_case_contract.py
8ef623d5e8276c0b763a1ec9c9ee29e7c18a384936289fdf724650e3d5206f1b  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
12de7f1915326f5ca275af19628ce28002a06dfff0fa42e837031f7e386515dd  docs/SESSION_HANDOVER_2026-08-29_2.md
```

## 3. Second domain disposition

**DOMAIN REJECTED.** The first remediation correctly closed the nine original classes of defect.
The second independent replay nevertheless found two remaining blocking arithmetic-domain defects,
one high-severity contextual-provenance false rejection, and one now-false handover claim. Green
implementer and repository gates do not supersede these semantic counterexamples.

## 4. Blocking finding R1 — partially missing cost and FX states can be impossible

The candidate reconciled quantity, native unit rate, and native amount only when all three operands
were resolved. It applied same-currency equality only when both amounts were resolved, and it
reconciled native amount, FX rate, and reporting amount only when all three operands were resolved.
This still violated the first review's requirement to validate every constraint inferable from the
resolved operands.

Three independent counterexamples were accepted:

1. A CAPEX line with an explicitly missing eventual-positive quantity, resolved rate
   `0 USD/item`, and resolved native/reporting amount `1.00 USD` was accepted. No positive quantity
   can make `quantity * 0 = 1.00`. The fully resolved `quantity=1` counterpart was rejected, proving
   that the missing state hid an already knowable contradiction.
2. A same-currency line with quantity `1 item`, rate `2.00 USD/item`, missing native amount, and
   resolved reporting amount `1.00 USD` was accepted. The missing native amount would have to be
   both `2.00` for cost multiplication and `1.00` for same-currency equality.
3. A mixed-currency line with native amount `0.00 LKR`, reporting amount `1.00 USD`, and an
   explicitly missing eventual-positive FX rate was accepted. No positive rate can make
   `0 * rate = 1.00`. The resolved-rate counterpart was rejected.

Required bounded remediation:

- validate the feasible domain of every partially resolved multiplication and equality instead of
  skipping the equation whenever any operand is missing;
- reject zero-factor/non-zero-product contradictions and conflicting inferred values across cost
  multiplication, same-currency equality, and FX conversion;
- preserve valid partial states, including a missing positive quantity when resolved positive rate
  and amount admit a solution and a missing positive FX rate when non-zero native/reporting amounts
  admit a positive solution; and
- add durable positive and negative controls for all three counterexamples.

## 5. Blocking finding R2 — Decimal operations use the ambient 28-digit context

`FiniteDecimal` declared no digit bound, but unitized generation, BESS reconciliation, cost
multiplication, FX conversion, summation, and money quantization used the process-global Decimal
context. That silently imposed a 28-digit intermediate limit not present in the machine contract or
generated schema.

Independent counterexamples:

1. A valid two-decimal cost with quantity `1`, rate/native/reporting amount
   `1234567890123456789012345678.90`, and minor-unit scale `2` escaped the Pydantic boundary as raw
   `decimal.InvalidOperation` instead of validating or producing a controlled validation error.
2. A valid unitized generation proposition with count
   `10000000000000000000000000001`, unit power `1 MW`, and an identical total was falsely rejected
   after rounded intermediate multiplication.
3. A valid BESS whose power and duration were both
   `100000000000000.00000000000001` and whose energy was the exact product
   `10000000000000000000000000002.0000000000000000000000000001` was falsely rejected for the
   same reason.

Ordinary-scale half-even behavior remained correct:

```text
1 * 1.005 -> 1.00  ACCEPTED
1 * 1.015 -> 1.02  ACCEPTED
1 * 1.005 -> 1.01  REJECTED
```

Required bounded remediation:

- either declare and strictly enforce a domain-justified digit bound in the machine type and
  generated schema, or perform every relevant operation in a local Decimal context sized from the
  operands, result, tolerance, and target minor-unit/quote scale;
- never depend on the process-global Decimal context;
- translate `InvalidOperation`, overflow, and quantization failures to precise Pydantic validation
  errors; and
- add valid high-precision generation, BESS, money, and FX cases, plus controlled over-limit cases
  if a bounded domain is chosen.

## 6. High finding R3 — FX provenance is scoped to the whole project

`ProjectCase._scope_for_field_path()` had exact branches for location, assets, allocations, cost
lines, and price bases, but none for `/costs/currency_conversions/<index>/rate`. Conversion rates
therefore fell through to every project jurisdiction and every active technology.

An independent positive probe assigned the only converted OPEX line entirely to wind in a valid
wind-plus-BESS case and bound its FX rate to a source explicitly scoped to Fictionland and wind.
The case was falsely rejected because the wind FX source did not also claim BESS scope:

```text
source source:wind-fx has wrong scope for /costs/currency_conversions/0/rate
```

Required bounded remediation:

- derive a conversion rate's scope from exactly the cost lines naming its `conversion_id`, then
  through those lines' allocations to the relevant asset jurisdictions and technologies;
- add a positive wind-only conversion/source case in a wind-plus-BESS project; and
- add a negative control proving that a BESS-scoped source cannot support the wind-only conversion.

## 7. Medium documentation finding R4 — handover claims exceed the evidence

The reviewed handover stated that partially missing generation and cost states remain
arithmetically feasible and that money/FX use exact Decimal arithmetic. It also stated that every
resolved value receives the exact contextual scope derived from its asset or allocated cost line.
R1-R3 disprove those unqualified claims. The handover must be corrected only after the production
repair and hostile controls establish the narrower true statements.

## 8. Original D3A-DOM-01 through D3A-DOM-09 replay

The second reviewer independently confirmed that the first remediation correctly addressed every
original finding:

| Original finding | Negative replay | Positive counterpart |
|---|---|---|
| D3A-DOM-01 topology/charging | Missing `charges_from` and access-road common path rejected. | Common typed path and dedicated wind+BESS without shared facility accepted. |
| D3A-DOM-02 capacity basis | Solar `MWdc` declared as AC and mixed BESS bases rejected. | Solar DC nameplate and basis-consistent usable AC BESS accepted. |
| D3A-DOM-03 price-basis provenance | Unbound and wrong-scope bases rejected. | Correctly scoped bound basis accepted. |
| D3A-DOM-04 numeric identity | USD 999 large-value discrepancy rejected. | Exact integer `9007199254740993` preserved and serialized identically. |
| D3A-DOM-05 partial feasibility | Missing count for `11/5` and `1.0 + positive missing share` rejected. | Missing count for `10/5` and `0.8 + missing share` accepted. |
| D3A-DOM-06 site identity | Second site jurisdiction and unlocated LKA asset rejected. | Single site plus separately scoped corporate jurisdiction accepted. |
| D3A-DOM-07 versioning | Missing/unknown/future identifiers rejected. | Exact v1 identity accepted and both fields required by schema. |
| D3A-DOM-08 review vocabulary | `contract_reviewed` rejected. | Neutral `declared` accepted without review/grade/release semantics. |
| D3A-DOM-09 boundary states | Unknown `final` state rejected. | `registered`, `derived`, and `disputed` remained distinct and accepted. |

For the original D3A-DOM-03 arbitrary-2099 probe, the mutation is now accepted only when it retains
an explicit correctly scoped source or assumption binding. D3A records that controlled proposition;
authenticating whether the cited source truly supports it remains later evidence/package work.

## 9. Conventional gate and boundary receipt

The second reviewer recorded:

```text
Python:                                      3.12.13
Governed venv check:                         PASS
GWTF bootstrap:                              72 active rules
ProjectCase focused gate:                    107 passed; one pre-existing warning
Inherited D2 focused/import/taxonomy gate:   386 passed; one pre-existing warning
Complete tests/contracts gate:               433 passed; one pre-existing warning
Ruff check and format:                       PASS
Black check:                                 PASS
mypy --no-incremental:                       PASS
Draft 2020-12 schema check:                  PASS
Public exports/schema definitions:           62 / 47
git diff --check:                            PASS
Required exact-head GitHub checks:           3/3 PASS
Final worktree status:                       clean
```

The warning was the existing Hypothesis `norecursedirs` collection warning. Coverage was not rerun
by the read-only reviewer because the normal command writes a `.coverage` file; the handover's
coverage result was not used as acceptance evidence.

The D3A source retained pure import direction. Raw JSON remained valid through
`ProjectCase.model_validate_json()`, while already parsed Python/FastAPI dictionaries still require
an explicit normalizing adapter. No finance, evaluation, app, API, renderer, engine, KPI, grade,
release, canonical-hashing, or protected-HOLD file changed.

## 10. Non-blocking evolution notes

These do not widen the present repair:

- importing the public subpackage still executes the pre-existing eager `analytics/__init__.py`
  and loads finance modules; D3A did not create that parent-package behavior, but a future web
  adapter should not call the process import lightweight or finance-free until it is addressed;
- generic `connected_to` links have no role-specific direction rule, while the material
  `charges_from` and `uses_shared_infrastructure` links do; and
- multiple allocations for the same `(cost_line_id, asset_id)` remain possible; arithmetic is
  groupable and closed, but a later consumer should define or constrain that multiplicity.

## 11. Controlling next step

The next candidate needs only the bounded R1-R4 repair:

1. partial cost, same-currency, and FX feasibility;
2. an explicit precision-safe Decimal arithmetic domain;
3. conversion-to-consuming-line provenance scope;
4. corresponding hostile positive/negative tests; and
5. truthful handover claims.

After implementation, rerun the complete focused, inherited D2, contract, coverage, Ruff, Ruff
Format, Black, isort, mypy, schema/export, import-boundary, and diff gates. Commit and push a new
exact head, then obtain another independent domain rereview. Assurance review remains blocked until
domain acceptance. No adapter, orchestration, finance, grade, release, canonical-hashing,
multi-site, issue-state, or `HOLD` change is authorized by this record.
