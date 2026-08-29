# Dolphin 3A remediation rereview record

**Record status:** second and third independent domain vetoes under PERSIST-01
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

## 12. Third exact-head domain disposition

The bounded R1-R4 successor was committed and pushed as
`de897d0aff7daa1caaf7797ce5556cdd040c8627`. The third independent review confirmed that the local
head, local remote-tracking topic ref, live remote topic branch, and PR head all identified that
exact candidate. Live `origin/main` remained
`782c9588ef2685fcf0608d48f7745493aaa15b78`, the worktree was clean, and PR `#1191` remained open
and draft. The reviewer made no file, Git, GitHub, PR, issue, audit-ledger, or release-state
mutation.

The third reviewed fingerprints were:

```text
728827b0069ed7d4214523b6e89aca1a5cd95470f27b64a5630a7a7598b2ffcb  analytics/feasibility_report_contract/project_case.py
c47038ff13e6135a9f8fe33c57ef0aacc424d8eab233e6f880c5d796b7ba8f5d  analytics/feasibility_report_contract/__init__.py
28b4d96570c19930d151b0fa85e74e45287ccc3069964c56177b855fbbfa8a48  tests/contracts/test_project_case_contract.py
be205c6a7b779f3f91af4d6828cd9fd2f518e3a4f6e4510e7d6146bfec9c679d  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
220297360210cba9ac1a09f2518a6fd6919644d0392ca2f98deab2b0b364a105  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
1c3ee234e7e8f26fe127c14847b463d111aeec51674bc5e3f98ff6ae9335ccfd  docs/SESSION_HANDOVER_2026-08-29_2.md
```

**DOMAIN REJECTED.** The third review accepted the original `D3A-DOM-01` through `-09` replay and
the writer-authored R1-R3 cases. It then found three independent high/blocking boundary classes and
one medium allocation-policy inconsistency. This remains a D3A contract-domain disposition only;
it provides no professional, statutory, engineering, lender, Board, grade, release, or `HOLD`
authority.

## 13. D3A-DOM-R5 — coupled cost and FX feasibility is not solved jointly

The candidate proved cost multiplication and FX conversion separately, but did not intersect their
solution sets when native amount and another operand were both missing.

The independent admitted counterexample was:

```text
OPEX quantity:                 resolved 1 year
unit rate:                     missing LKR/year
native amount:                 missing LKR
native minor-unit places:      0
reporting amount:              resolved 1 USD
reporting minor-unit places:   0
FX rate:                       resolved 2 USD/LKR
missing records/status:        exact and complete
result:                        ACCEPTED
```

No completion exists. A zero-minor-unit LKR native amount must be an integer, and half-even rounding
of `integer * 2` to zero USD places can only produce an even integer, never USD 1. The eventual
native amount must simultaneously satisfy the quantity/rate equation.

Required bounded remediation:

- solve the connected chain jointly:

  ```text
  quantity * unit rate
      -> native amount on its minor-unit grid
      -> FX rate on its quote-precision grid
      -> reporting amount on its minor-unit grid
  ```

- apply positivity/nonnegativity, native/reporting minor units, FX quote precision, numeric-domain
  bounds, and explicit half-even rounding throughout;
- add the exact negative and a nearby feasible USD 2 positive under the same native/FX basis; and
- cover different combinations of missing quantity, rate, native amount, and FX rate so pairwise
  satisfiability cannot masquerade as joint satisfiability.

The third reviewer independently matched `_missing_factor_solution_exists` against an exact
integer/rational half-even oracle over 98,432 bounded cases. R5 therefore does not reopen that
single-equation search; the defect is failure to join connected equations and their different
declared grids.

## 14. D3A-DOM-R6 — one-missing generation and BESS states can have no completion

The candidate validated the missing-count generation branch, but returned whenever unit power or
total power was missing. BESS reconciliation returned whenever any of power, energy, or duration
was missing.

All four independent raw-JSON probes were accepted:

```text
G1_out_of_domain_missing_total   ACCEPTED
G2_no_grid_solution_missing_unit ACCEPTED
S1_out_of_domain_missing_energy  ACCEPTED
S2_no_grid_solution_missing_duration ACCEPTED
```

The exact propositions were:

1. count `10^36 - 1`, unit power `10^36 - 1 MW`, total missing: the product is approximately
   `1e72 MW`, outside every admitted total-power value;
2. count `10^36 - 1`, total `1e-36 MW`, unit power missing: the minimum eventual-positive unit
   rating `1e-36 MW` produces approximately `1 MW`, far outside the `1e-9 MW` tolerance;
3. BESS power and duration both `10^36 - 1`, energy missing: their product is outside the material
   domain; and
4. BESS power `10^36 - 1 MW`, energy `1e-36 MWh`, duration missing: the minimum positive duration
   produces approximately `1 MWh`, not `1e-36 MWh` within tolerance.

Required bounded remediation:

- validate missing count, unit rating, and total capacity for every one-missing generation state;
- validate missing power, energy, and duration for every one-missing BESS state;
- reject inferred resolved values outside the declared domain;
- use exact rational/grid feasibility and the engineering tolerance, never ambient Decimal
  arithmetic;
- retain two-or-more-missing states only when a bounded completion genuinely exists; and
- add the four exact negatives plus nearby feasible positives.

## 15. D3A-DOM-R7 — runtime and schema do not enforce the advertised input domain

The `FiniteDecimal` alias delegated `max_digits` and `decimal_places` to Pydantic, while the
independent tuple-based domain helper applied only to inferred results. Direct raw-JSON validation
therefore changed with the process-global Decimal context and accepted high-significand values
outside the documented boundary.

Independent runtime results included:

```text
36 integer digits plus 37 fractional digits: ACCEPTED
0 plus 37 fractional nines:                  ACCEPTED
0 plus 73 fractional nines at precision 3:  ACCEPTED
0 plus 100 fractional nines at precision 28: ACCEPTED
0 plus 500 fractional nines at precision 3: ACCEPTED
```

At ambient precision 100, the same 500-place input rejected under `ROUND_DOWN` but accepted under
`ROUND_UP`. Scale-overflow zeros such as `0e-37`, `0e-1000000`, a 500-place lexical zero, and
`-0e-999999` were also accepted while retaining their exponents. This contradicted the documented
ambient-independent 72-total/36-place contract.

The generated Draft 2020-12 schema did not fail closed either. Its Pydantic-produced string pattern
allowed the first alternation to match an empty or short prefix, so the independent schema validator
accepted a runtime-admitted 37-place string. Merely asserting that `\d{0,36}` appeared in the
pattern provided false confidence.

Required bounded remediation:

- make one authoritative runtime validator own the input rule using `Decimal.as_tuple()` or exact
  lexical/scale logic independent of ambient normalization;
- avoid a preceding Pydantic constraint that can context-dependently reject or admit the value;
- decide and encode zero-scale semantics: either excessive zero scale fails, or deterministic
  canonicalization is explicit in runtime, serialization, and schema;
- retain schema-visible bounds through an actually anchored/refusing string schema;
- test hostile strings against both runtime and generated Draft 2020-12 schema; and
- cover exact 72/36 positives, 73-total and 37-place high-significand negatives, 100/500-place
  negatives, zero-scale boundaries, and multiple ambient precision/rounding settings.

No raw Decimal exception escaped in these probes. R7 is a false-acceptance, schema, and
context-dependence failure.

## 16. Allocation closure policy inconsistency

The reviewer's first allocation note was corrected before final disposition. Under the implemented
`1e-12` complete-share tolerance, two missing shares of `1e-36` could yield a completed sum that the
validator accepts. The decisive issue is instead inconsistency:

- complete sum `1 + 1e-36` is accepted within tolerance; but
- partial sum exactly `1` plus one missing eventual-positive share is rejected immediately.

If exact closure is intended, the complete state is falsely accepted. If tolerance closure is
intended, the partial state has a completion accepted by the complete validator and is falsely
rejected. The repair must choose one surfaced rule and apply it consistently: exact rational
closure, or a declared tolerance/minimum-share policy whose partial-feasibility predicate derives
from the same rule.

## 17. Third-review accepted boundaries and gate receipt

The third rejection does not reopen every prior repair. The reviewer passed 27 selected original
`D3A-DOM-01` through `-09` propositions and all 20 writer-authored R1-R3 controls. Confirmed
boundaries included topology/charging direction, solar and BESS bases, single-site behavior with a
separately scoped corporate jurisdiction, bound price/conversion provenance, mandatory versions,
neutral `declared` vocabulary, distinct boundary states, exact large-value identity, half-even
rounding, and the raw-JSON versus normalized-Python adapter boundary.

The exact command receipt was:

```text
ProjectCase focused gate:                  127 passed; one pre-existing warning
Selected original D3A-DOM-01..09 replay:  27 passed; one pre-existing warning
Selected writer R1-R3 replay:              20 passed; one pre-existing warning
Inherited D2 focused gate:                 386 passed; one pre-existing warning
Complete tests/contracts gate:             453 passed; one pre-existing warning
Ruff check and format:                     PASS
Black check:                               PASS
isort check:                               PASS
mypy --no-incremental:                     PASS
in-memory compile:                         PASS
git diff --check:                          PASS
AST forbidden imports:                     none
production LKA/Sri Lanka scan:             no matches
D3A excluded-surface diff:                 empty
```

The warning was the existing Hypothesis `norecursedirs` warning. D3A's direct AST remained free of
finance, evaluation, app, API, persistence, and renderer imports. The pre-existing eager
`analytics/__init__.py` still loads finance/evaluation modules when importing the public subpackage;
that remains a non-blocking future package-topology note rather than a new D3A dependency.

## 18. Third-remediation boundary

The next candidate is limited to R5-R7 and the allocation-policy consistency decision. It must also
narrow or re-prove the current changelog and handover claims. It does not authorize adapter work,
orchestration, finance changes, grade/release policy, canonical hashing, multi-site support, issue
state, or any `HOLD` change.

After implementation, rerun the full focused, selected hostile, inherited D2, complete contract,
coverage, Ruff, Ruff Format, Black, isort, mypy, schema/runtime-boundary, import-direction, and diff
gates. Commit and push a new exact head, then obtain another independent domain disposition before
dispatching assurance review.
