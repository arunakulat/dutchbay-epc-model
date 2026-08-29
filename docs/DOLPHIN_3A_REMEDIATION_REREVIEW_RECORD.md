# Dolphin 3A remediation rereview record

**Record status:** second through fifth independent domain vetoes and sixth independent domain
acceptance under PERSIST-01
**Latest exact reviewed candidate:** `2a3831542a3160f6d02cb2f592c4487981647f19`
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

## 19. Fourth exact-head domain disposition

The bounded R5-R7, exact-allocation, and deterministic Decimal-serialization successor was
committed and pushed as `c47aa8ffc1ff658b03216dbba93680d1eff2618d`. The fourth independent
review verified a clean worktree and index, with local `HEAD`, the local remote-tracking topic ref,
the live remote topic ref, and PR `#1191` all at that exact SHA. Local and live `origin/main` and
the PR base were `782c9588ef2685fcf0608d48f7745493aaa15b78`; the topic was nine commits
ahead and zero behind. The PR remained open and draft. Required checks and the wider six-shard test,
coverage, quality, security, fastlane, and smoke run were green. The reviewer made no file, Git,
GitHub, issue, release-state, or `HOLD` mutation.

The fourth reviewed fingerprints were:

```text
40c3b506b30e042f5d8b72ebc01b7a5dbbbd44a9c71e87e9009cad641f77ad76  analytics/feasibility_report_contract/project_case.py
c47038ff13e6135a9f8fe33c57ef0aacc424d8eab233e6f880c5d796b7ba8f5d  analytics/feasibility_report_contract/__init__.py
0287ffbc394ea869aa2f491a78b7fe49d7ba5faf0933d1d7a7589a75132e8ad0  tests/contracts/test_project_case_contract.py
4302baae6546d18b173c3c2d24e61cb4a1ebd7b478e46963df199e280dc8f01e  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
0868bd67fb4ca25b8822ea3c4fa4f2698813c4260d5f1747a6f738e320878e39  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
bf403fbc19b20d20f5573e203f6455d93999406b23253877b16960a29de15949  docs/SESSION_HANDOVER_2026-08-29_2.md
```

**DOMAIN REJECTED.** The fourth review independently accepted the repaired original
`D3A-DOM-01` through `-09` and R1-R7 boundaries, then found two new blocking shared-boundary
classes: R8 JSON-number/schema precision and R9 a shared missing FX variable receiving inconsistent
per-line witnesses. Green tests and CI did not override the counterexamples. This remains a D3A
input-contract disposition only and grants no professional, statutory, engineering, lender, Board,
grade, release, deployment, or `HOLD` authority.

## 20. D3A-DOM-R8 — JSON-number ingress is not precision preserving or schema equivalent

The candidate's exact plain-string Decimal path and Python-Decimal-to-plain-JSON serializer work,
but `FiniteDecimal` also advertises and accepts a JSON numeric branch. Standard JSON parsing turns
non-integral tokens into binary floats before `_validate_finite_decimal` converts them with
`Decimal(str(raw_value))`. The generated Draft 2020-12 schema likewise expresses the magnitude and
`multipleOf: 1e-36` controls with binary floats. That branch cannot preserve the submitted Decimal
identity or agree reliably with runtime.

Independent full-ProjectCase probes showed:

```text
raw JSON number                               runtime result                  Draft 2020-12 result
3e-36                                        ACCEPT Decimal('3E-36')         REJECT
6.9999999999999999999999999999999999999e-36 ACCEPT changed to Decimal('7E-36') ACCEPT
7.0000000000000000000000000000000000001e-36 ACCEPT changed to Decimal('7E-36') ACCEPT
1.23456789012345678901234567890123456        ACCEPT changed to 17 digits     ACCEPT changed float
1.0000000000000000000000000000000000001      ACCEPT changed to Decimal('1.0') ACCEPT changed float
1000000000000000000000000000000000000        REJECT 37 integer digits        ACCEPT
```

The exact `10^36` schema acceptance comes from the Python float `1e36` being slightly larger than
the exact integer. The `multipleOf` branch also falsely rejected valid quanta including `3e-36`,
`6e-36`, and `9e-36`. Adjacent sub-grid tokens collapsed to the same admitted float. Changing only
the magnitude literals would not repair identity loss or quantum mismatch.

The generated count schema has a related strictness seam: Draft 2020-12 treats JSON `1.0` and
`1e0` as integers, while strict `ResolvedCount` runtime rejects them. Exact 36-digit and 37-digit
integer-token boundaries otherwise behaved correctly.

Required bounded remediation:

- make the anchored plain-ASCII Decimal string the sole JSON representation for every
  `FiniteDecimal`, while retaining native `Decimal` in normalized Python mode and the deterministic
  plain-string serializer;
- reject raw JSON floating-number tokens instead of silently changing them;
- explicitly align `ResolvedCount` runtime, serializer, and generated schema for integral JSON
  forms; a string-only count representation is the fail-closed option if exact lexical parity is
  required;
- add full-ProjectCase runtime/schema tests for valid grid values, adjacent sub-grid values,
  exact `+/-10^36`, high-precision identity, Decimal dump/re-ingress, and `1`, `1.0`, and `1e0`
  count forms; and
- narrow the changelog and handover to the representation actually proved.

## 21. D3A-DOM-R9 — a shared missing FX rate receives inconsistent per-line witnesses

`CurrencyConversion.rate` is one shared graph variable, but the candidate called
`_reconcile_partial_conversion` independently for every consuming cost line. When the rate was
missing, each call proved that its own line had some witness; it did not prove that one common rate
completed all consumers.

The independent accepted-invalid schedule used one missing six-place `USD/LKR` conversion and two
otherwise valid OPEX lines. Both had quantity `1 year`, native unit rate `100 LKR/year`, and native
amount `100.00 LKR`. Their reporting amounts were respectively `1.00 USD` and `2.00 USD`.

```text
line 1 permitted quote grid: 0.009950 through 0.010050 inclusive
line 2 permitted quote grid: 0.019950 through 0.020050 inclusive
result:                       ACCEPTED incomplete_missing_input
```

The intervals are disjoint, so no one value can complete the shared conversion. An
inferable-native variant failed the same way. A second false acceptance combined one line with
native amount `10^36 - 1` and missing reporting amount with another line forcing the common rate
near `2`; that rate makes the first eventual reporting amount approximately `2 * 10^36`, outside
the material domain. The candidate imposed no rate-dependent bound for a missing report. Controls
with a common rate accepted, zero-native/zero-report accepted, and zero-native/nonzero-report
rejected.

Required bounded remediation for each missing conversion rate:

1. identify every consuming line;
2. derive each line's exact allowed positive quote-grid interval or set from its effective native
   amount, reporting state, minor units, half-even rounding, quote precision, and numeric bounds;
3. include representable-output bounds when reporting is missing;
4. intersect every consumer constraint with the positive, in-domain rate grid; and
5. accept only when one common rate witness remains.

The documented v1 refusal must remain when a resolved reporting target has both effective native
amount and FX unresolved. Sampled witnesses remain prohibited. Tests must include disjoint/common
two-line cases, missing-report overflow and feasible controls, inferable-native variants,
zero-native controls, mixed minor/quote precision, and at least one three-consumer intersection.

## 22. Fourth-review accepted boundaries and gate receipt

The fourth rejection does not reopen the earlier repairs. Independent replay accepted every
positive and rejected every negative original D3A-DOM-01 through -09 pair. All seven nonempty
generation missing masks and all seven BESS missing masks accepted feasible witnesses; every
one-missing impossible generation/storage boundary rejected, with six nearby positives accepted.
Exact complete and partial allocation boundaries matched policy under hostile Decimal contexts.

The 32-state single-line quantity/rate/native/FX/reporting missing matrix produced 29 accepted
witness-bearing states and exactly the three documented both-effective-native-and-FX-unresolved
refusals. Independent exact oracles reported:

```text
_missing_factor_solution_exists: 9,680 cases; 0 mismatches
native grid interval solver:     2,293,128 cases; 0 mismatches
```

The exact Python Decimal -> ProjectCase -> plain JSON -> Draft 2020-12 -> ProjectCase round trip
passed for positive exponents, positive/negative zero, and 36-place signed zero. Hostile ambient
Decimal precision, rounding, and traps did not affect generation, BESS, money, FX, or half-even
results. The direct module import remained pure, contextual provenance remained allocation scoped,
and production contained no Sri Lankan fallback.

The fourth review's command receipt was:

```text
ProjectCase focused gate:                 185 passed; one pre-existing warning
Inherited D2 focused gate:                386 passed; one pre-existing warning
Complete tests/contracts gate:            511 passed; one pre-existing warning
Ruff check and format:                    PASS
Black check:                              PASS
isort check:                              PASS
mypy --no-incremental:                    PASS
in-memory compile:                        PASS
Draft 2020-12 schema structure check:     PASS
Public exports/schema definitions:        62 / 47
git diff --check:                         PASS
AST forbidden direct imports:             none
production LKA/Sri Lanka scan:            no matches
D3A excluded execution-surface diff:      empty
required exact-head GitHub checks:         PASS
```

The warning was the pre-existing Hypothesis `norecursedirs` warning. Schema structural validity is
not semantic parity; R8 is precisely why `check_schema()` and green CI were insufficient.

## 23. Fourth-remediation boundary

The next candidate is limited to R8 exact JSON scalar representation and R9 shared missing-FX
intersection. It must also correct the current changelog and handover claims. It does not authorize
FastAPI/routes, adapter implementation, orchestration, finance changes, grade/release policy,
canonical whole-document hashing, multi-site support, issue state, or any `HOLD` change.

After implementation, rerun the focused hostile, inherited D2, complete contract, coverage, Ruff,
Ruff Format, Black, isort, mypy, schema/runtime parity, import-direction, exclusion, and diff gates.
Commit and push a new exact head, then obtain another independent domain disposition. Separate
assurance review remains blocked until exact-head domain acceptance.

## 24. Fifth exact-head domain disposition

The bounded R8-R9 successor was committed and pushed as
`b0020ece4e864cc2cf589bae40f82edd5c30320d`. The fifth independent review verified a clean
worktree and index, with local `HEAD`, the local remote-tracking topic ref, the live remote topic
ref, and PR `#1191` all at that exact SHA. Local and live `origin/main` and the PR base were
`782c9588ef2685fcf0608d48f7745493aaa15b78`; the topic was eleven commits ahead and zero behind,
and the base remained its ancestor. The PR was open, draft, mergeable, and reported a clean merge
state. All applicable exact-head CI jobs and all four required checks passed; Grid Study, Report
Qualification, and Stochastic Qualification were the expected changed-path/scheduled skips. The
reviewer made no file, index, Git-ref, GitHub, PR, issue, audit-ledger, release-state, or `HOLD`
mutation during that immutable read-only review.

The exact candidate-tree fingerprints before this documentation-only PERSIST append were:

```text
52d1fa1f33272d4e448e14ef4fdbcfafcd0a27223495512cd246b2bc80a26b38  analytics/feasibility_report_contract/project_case.py
c47038ff13e6135a9f8fe33c57ef0aacc424d8eab233e6f880c5d796b7ba8f5d  analytics/feasibility_report_contract/__init__.py
3120e205f9c19ddb5e5323b0a12543eea9f74a82e0fda7dd0dfba3e81f1a81e9  tests/contracts/test_project_case_contract.py
48a3c164be65af001466b11d50614c449d3c79ad2eb48288df0e9d4c1f3929d5  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
46d2115b5f8112dd4c9340621e513c20290557311df2d4b0dc59226f466ba343  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
3247009c40cc906fb833014c833be9361180a4e2996012645d8e2c73c24d3607  docs/SESSION_HANDOVER_2026-08-29_2.md
```

The re-ingressed normative-chain fingerprints were:

```text
2029b57d53b279e1163889b5b707cc3ff3248095f1ea0de9904b40a780dab09e  docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md
e4585e3ba0c38c7cf8bcd59bfc70ee92b745ccc22564f94e20b91d3dad5cecfb  docs/FEASIBILITY_REPORT_CONTRACT.md
22594abf994b90883cf3272ab6bac9029e6a7aeb2e43a1d2fb6d55f0f4b8d276  docs/FEASIBILITY_REPORT_CONTRACT_SOURCES.md
5a3edbb49798890dee3f78bcd9f71afd4f32fc67d78f6e2f87b675ff8ff50ffc  docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
69827eb77903f3efbc5f88bf3bd8dceef42219529839d9ca67de6b720f1395d1  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
b9e5d9e38137438db59406db82bce668513af629049017ddc6950baf4d498c2b  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
25933beb47609efc976bbf754810bd4c761bf2f330daa99a35adab22e73d535a  docs/SESSION_HANDOVER_2026-08-29.md
```

**DOMAIN REJECTED.** The fifth review independently accepted the original `D3A-DOM-01` through
`-09` and R1-R9 repair classes, then found one new blocking topology defect, R10. Green tests and CI
do not supersede that counterexample. This disposition is contract-domain evidence only; it grants
no professional, statutory, engineering, audit, lender, Board, achieved-grade, release, deployment,
or `HOLD` authority.

## 25. D3A-DOM-R10 - dedicated topology admits a shared electrical path

`InterconnectionArrangement.DEDICATED_SEPARATE` declares that technology assets use dedicated
electrical paths (`project_case.py:219-223`). The validator, however, adds a technology asset to
`common_path_users` only when a `uses_shared_infrastructure` target equals
`common_interconnection_asset_id` (`project_case.py:1327-1336`). Its dedicated branch then checks
only that this optional common identifier is null (`project_case.py:1383-1386`). It never reconciles
the dedicated declaration against the complete electrical shared-facility relationship graph.

The independent mutation of the canonical wind-plus-BESS fixture was:

```text
interconnection_arrangement:        dedicated_separate
common_interconnection_asset_id:    null
wind -> shared POI link:             uses_shared_infrastructure
BESS -> same shared POI link:        uses_shared_infrastructure
shared-facility role:                grid_interconnection
result:                              ACCEPTED
```

Changing only the shared-facility role to `electrical_collection` was also accepted. That is a
shared electrical path under a declaration of dedicated separation. Changing the role to
`access_road` remained accepted, which is correct: dedicated electrical paths must not prohibit
shared non-electrical facilities. The existing dedicated positive test
(`tests/contracts/test_project_case_contract.py:785-801`) removes the shared facility entirely and
therefore cannot detect this false acceptance. R10 reopens the substantive false-common-electrical-
path class of the original D3A-DOM-01 even though its narrower named-common-asset replay passes.

Required bounded remediation:

1. reconcile `interconnection_arrangement` against every electrical shared-facility relationship,
   not only the optional `common_interconnection_asset_id`;
2. under `dedicated_separate`, reject a `grid_interconnection` or `electrical_collection` facility
   used by or materially connected to more than one technology asset, unless a future typed model
   represents genuinely distinct circuits or paths;
3. include material `connected_to` electrical links in that invariant, or prohibit that generic link
   form where it would create an untyped escape;
4. preserve valid shared non-electrical facilities such as access roads and operations facilities;
5. add the exact shared-POI and shared-electrical-collection negatives, a dedicated no-electrical-
   sharing positive, and a dedicated shared-access-road positive; and
6. narrow the changelog and handover only after the production invariant and hostile tests exist.

## 26. Fifth-review accepted boundaries and independent receipt

R8 is accepted at this exact candidate. The sole JSON scalar representation is the anchored Decimal
or count string, runtime and Draft 2020-12 refuse raw numeric tokens, native Decimal serialization is
deterministic, and absolute-end handling agrees for LF, CR, CRLF, U+2028, and U+2029 cases. R9 is
also accepted: one missing FX rate is intersected across every consumer, including report-domain
bounds when a reporting amount is missing. Independent controls rejected disjoint schedules and
accepted common-rate, inferable-native, zero-native/zero-report, mixed-precision, and three-consumer
schedules; zero-native/non-zero-report and forced-rate missing-report overflow cases rejected.

The fifth review replayed all original and R1-R9 negative/positive classes. Its independent exact
oracles reported:

```text
Decimal runtime/schema strings:              1,524 cases; 0 mismatches
resolved-count runtime/schema strings:        1,016 cases; 0 mismatches
raw JSON numeric-token controls:                  9 cases; all refused
hostile-context native Decimal round trips:      18 cases; 0 mismatches
two-consumer shared-FX schedules:               120 cases; 0 oracle mismatches
shared-FX grid intervals:                     1,488 cases; 0 oracle mismatches
missing-factor feasibility:                 12,096 cases; 0 oracle mismatches
half-even tie controls:                          20 cases; 0 failures
generation/BESS nonempty missing masks:        7/7 each; feasible witnesses accepted
```

The 32-state single-line cost/native/FX/reporting matrix admitted 23 witness-bearing states and
refused nine deliberately fail-closed underdetermined states consistently with the surfaced v1
policy. No raw Decimal exception escaped. The exact command/gate receipt was:

```text
Python:                                      3.12.13
Governed venv check:                         PASS; active worktree selected
GWTF bootstrap:                              72 active rules
ProjectCase focused gate:                    233 passed
Selected original and R1-R9 replay:          113 passed
Inherited D2 focused gate:                   386 passed
Complete tests/contracts gate:               559 passed
Ruff check and format:                       PASS
Black check:                                 PASS
isort check:                                 PASS
mypy --no-incremental:                       PASS
in-memory compile:                           PASS
Draft 2020-12 schema check:                  PASS
Public exports/schema definitions:           62 / 47
AST forbidden direct imports:                none
production LKA/Sri Lanka scan:               no matches
D3A excluded execution-surface diff:         empty
git diff --check:                            PASS
required exact-head GitHub checks:           4/4 PASS
all applicable exact-head CI jobs:           PASS
final reviewed worktree/index:               clean
```

The direct D3A module remains transport-neutral and free of finance, evaluation, app, API,
persistence, renderer, engine, grade, and release imports. Importing through the parent
`analytics` package still loads pre-existing eager finance/evaluation imports; that is a future
package/web-topology note, not this veto. Raw JSON can enter through `model_validate_json()`, while
an already parsed web dictionary still needs an explicit normalizing adapter and request-size
controls. D3A continues to defer a multi-site physical-asset case, not every additional non-site
jurisdiction subject. No Sri Lankan fallback, FastAPI route, adapter, orchestration, finance,
canonical whole-document hashing, package assembly, grade/review aggregation, issue-state, release,
or protected-`HOLD` surface changed.

## 27. Fifth-remediation boundary

The next candidate is limited to R10 dedicated-versus-shared electrical topology closure, its
hostile positive/negative tests, and truthful changelog/handover wording. It must preserve R8/R9,
all prior accepted classes, shared non-electrical infrastructure, the single-site physical-asset
boundary, direct import purity, exclusions, and every assurance and `HOLD` separation.

After implementation, rerun the focused hostile, original/R1-R10 replay, inherited D2, complete
contract, coverage, Ruff, Ruff Format, Black, isort, mypy, schema/runtime parity, import-direction,
exclusion, and diff gates. Commit and push a new exact head only under the controlling delivery
authority, then obtain another independent domain disposition. Separate assurance review remains
blocked until exact-head domain acceptance.

## 28. Sixth exact-head domain disposition

The bounded R10 successor was committed and pushed as
`2a3831542a3160f6d02cb2f592c4487981647f19`. The sixth independent reviewer verified that local
`HEAD`, the local remote-tracking topic ref, the live remote topic ref, and PR `#1191` all identified
that exact SHA. Local and live `origin/main` and the PR base were
`782c9588ef2685fcf0608d48f7745493aaa15b78`; the base was an ancestor, and the topic was thirteen
commits ahead and zero behind. The PR was open, draft, mergeable, and reported a clean merge state.
The worktree and index were clean before and after review. The reviewer made no file, index, Git-ref,
GitHub, PR, issue, audit-ledger, release-state, or `HOLD` mutation.

The exact candidate-tree fingerprints before this documentation-only PERSIST append were:

```text
1e9d6fefaf1697710068d9d4886ffaa29a10f00e4d0b658aada268503d19534f  analytics/feasibility_report_contract/project_case.py
c47038ff13e6135a9f8fe33c57ef0aacc424d8eab233e6f880c5d796b7ba8f5d  analytics/feasibility_report_contract/__init__.py
86827cd5a29c708b73f027c31c27b7f0a5492f86aae8e222977874efbd8d105e  tests/contracts/test_project_case_contract.py
2868899396d7f0cbd5cb2b8cc2d1ce282698623676edda3001a7f93e087a84e2  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
553d5645280ef19985ff74dbf1a7d732edf04b0b19b13af02c1ed4faae7c5d0e  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
cc2378e738a22465355ee76bdd6d68d0b876f256fc4a15047c2d46bfb2c3c119  docs/SESSION_HANDOVER_2026-08-29_2.md
```

The re-ingressed normative-chain fingerprints remained:

```text
2029b57d53b279e1163889b5b707cc3ff3248095f1ea0de9904b40a780dab09e  docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md
e4585e3ba0c38c7cf8bcd59bfc70ee92b745ccc22564f94e20b91d3dad5cecfb  docs/FEASIBILITY_REPORT_CONTRACT.md
22594abf994b90883cf3272ab6bac9029e6a7aeb2e43a1d2fb6d55f0f4b8d276  docs/FEASIBILITY_REPORT_CONTRACT_SOURCES.md
5a3edbb49798890dee3f78bcd9f71afd4f32fc67d78f6e2f87b675ff8ff50ffc  docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
69827eb77903f3efbc5f88bf3bd8dceef42219529839d9ca67de6b720f1395d1  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
b9e5d9e38137438db59406db82bce668513af629049017ddc6950baf4d498c2b  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
25933beb47609efc976bbf754810bd4c761bf2f330daa99a35adab22e73d535a  docs/SESSION_HANDOVER_2026-08-29.md
```

Exact-head GitHub Actions run `33246388975` completed successfully with eighteen successful jobs,
three expected changed-path/scheduled skips (Grid Study, Report Qualification, and Stochastic
Qualification), and no pending or failed job. All four required checks passed: Test Summary,
Verification receipts, fastlane, and smoke.

**DOMAIN ACCEPTED.** At this exact SHA, the sixth independent review found no blocking, high,
medium, or low D3A contract-domain defect. The former R10 false acceptance is closed, and the
original `D3A-DOM-01` through `-09` and R1-R9 repair classes remain accepted. Green tests and CI were
supporting evidence, not substitutes for the independent domain probes below.

## 29. R10 independent topology closure

The successor removes `connected_to` from `AssetLinkKind` and the generated schema. It derives
facility users from every `uses_shared_infrastructure` link and from storage `charges_from` links to
a typed shared grid. Under `dedicated_separate`, a `grid_interconnection` or
`electrical_collection` facility used or materially connected by more than one technology asset now
fails closed. Distinct one-user electrical facilities remain valid. Shared non-electrical
The `access_road`, `operations_facility`, and `other_shared_facility` roles remain valid.

Two independently constructed graph oracles, separate from the writer tests, agreed with the
contract in every case:

```text
hand-constructed topology matrix:       35 cases; 13 accepted; 22 rejected; 0 mismatches
arrangement/role/user-set matrix:        48 cases; 16 accepted; 32 rejected; 0 mismatches
```

Together they covered both arrangements; all five shared-facility roles; two and three technology
assets; same and distinct facilities; one-user and multi-user electrical paths;
`uses_shared_infrastructure`; storage charging from a shared grid or generation asset; common-mode
path completeness; shared-grid charging as a material dedicated-path user; duplicate identifiers
and edges; dangling, self, reversed, wrong-target, and multiple-charging links; unused shared
assets; and unknown link or role vocabulary. Runtime and the independently checked Draft 2020-12
schema both refuse `connected_to`. The exact former R10 shared POI and shared electrical-collection
counterexamples reject, while dedicated distinct facilities, direct storage-to-generation charging,
and shared non-electrical facilities accept.

## 30. Original and R1-R9 regression receipt

The sixth review replayed the original `D3A-DOM-01` through `-09` and R1-R10 negative/positive
classes in proportion to risk. R8 canonical dump, Draft 2020-12 validation, runtime re-ingress, sole
string representation, raw-number refusal, positive-exponent expansion, and signed/scaled-zero
controls passed. An independent R9 six-schedule oracle produced zero mismatches across disjoint,
common, zero, inferable-native, feasible missing-report, and missing-report-overflow schedules.

```text
Python:                                      3.12.13
Governed venv check:                         PASS; active worktree selected
GWTF bootstrap:                              72 active rules
Selected original and R1-R10 replay:         132 passed; one pre-existing warning
ProjectCase focused gate:                    241 passed; one pre-existing warning
Inherited D2 focused/import/taxonomy gate:   386 passed; one pre-existing warning
Complete tests/contracts gate:               567 passed; one pre-existing warning
Ruff check and format:                       PASS
Black check:                                 PASS
isort check:                                 PASS
mypy --no-incremental:                       PASS
in-memory compile:                           PASS
Draft 2020-12 schema check:                  PASS
Public exports/schema definitions:           62 / 47
AST forbidden direct imports:                none
production LKA/Sri Lanka/connected_to scan:  no unintended matches
D3A excluded execution-surface diff:         empty
git diff --check:                            PASS
required exact-head GitHub checks:           4/4 PASS
exact-head GitHub jobs:                      18 successful; 3 expected skipped; 0 failed/pending
final reviewed worktree/index:               clean
```

The warning was the pre-existing Hypothesis `norecursedirs` collection warning. The read-only
reviewer did not create a local coverage artifact; the exact-head GitHub Coverage Gate passed. The
direct D3A module retains its transport-neutral import boundary, all 62 public exports remain
available, its generated schema has 47 definitions, and no finance, evaluation, app, API,
persistence, renderer, engine, grade, release, Sri Lankan fallback, or protected-`HOLD` behavior was
introduced.

## 31. Findings, evolution notes, and authority boundary

There are no blocking, high, medium, or low D3A defects at the exact sixth-review candidate.

The following are non-blocking evolution notes, not D3A defects:

- importing through the parent `analytics` package still executes its pre-existing eager finance
  and evaluation imports, although the D3A module's direct import graph remains pure;
- a future web adapter must retain raw JSON or normalize already parsed dictionaries, impose request
  size and transport resource controls, and map validation errors to stable transport responses;
- v1 intentionally models a dedicated typed electrical facility as having at most one technology
  user; a future explicit circuit/path grouping may broaden that vocabulary without weakening v1;
  and
- the current PERSIST record must be checkpointed before separate assurance review so the accepted
  exact head and its limits survive restart.

This **DOMAIN ACCEPTED** disposition establishes only D3A contract-domain sufficiency at
`2a3831542a3160f6d02cb2f592c4487981647f19`. It is not professional or statutory engineering
assurance, external audit, lender or Board acceptance, achieved-grade authority, release or
deployment authorization, permission to merge before separate exact-head assurance and delivery
controls complete, or authority to lift any project, evidence, F5, package, or release `HOLD`.
