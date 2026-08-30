# Dolphin 3B-0 second-pass review record

**Reviewed object:** `analytics/feasibility_report_contract/assessment_scope.py` as merged to
`main` by [`#1198`](https://github.com/arunakulat/dutchbay-epc-model/pull/1198), squash
`5c492c350be40bcdc354252e66e27e7c97eecea9`, reviewed at `main` = `70e7d37`.

**Reviewed against:** the D0–D3A corpus — `FEASIBILITY_REPORT_CONTRACT.md` (D1, normative),
`GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md` (D0), `DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md` and its
two review records, `DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md`, and
`DOLPHIN_3B_EXECUTION_CHARTER.md` section 5.

**Disposition: ACCEPTED, with one medium finding and two corrections to the first-pass record.**
This is the second reviewer the owner's 2026-08-30 reviewer-depth policy requires for complex
scripts. It confers no achieved grade, package approval, assurance, release, lender or Board
authority, and lifts no `HOLD`.

## 1. Independence — what this pass is, and what it is not

This pass was performed by the **same agent** that produced
[`DOLPHIN_3B_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_3B_INDEPENDENT_REVIEW_RECORD.md). It is
therefore **not** reviewer-independent in the sense D2's three-role separation and the D3B charter's
two-reviewer chain intend, and it should not be counted as satisfying that structural requirement.
Anyone relying on this record must weigh that.

What is genuinely different is the **basis**. The first pass was a code-level adversarial probe run
with no domain corpus: it read the D3B charter and the module, and tested lexical, digest and
determinism behaviour. This pass first ingested D0, D1, D2 and D3A — including the nine confirmed
D3A domain findings — and reviews D3B through the question the first pass could not ask:

> **Does D3B repeat any defect that a predecessor's reviewers already confirmed?**

That question found two errors in the first record and one finding neither the first pass nor the
implementer's 136 tests caught. Where this pass merely re-confirms the first, it says so and claims
no additional weight.

## 2. Corrections to the first-pass record

Both corrections have the same root cause, and it is the exact trap the corpus warns about: **the
first pass inferred test coverage from a passing count instead of reading the test file.** D3A was
rejected with 81 green tests, and the D3C charter records that D3B-0's own reviewers vetoed three
successive candidates that each passed their own focused suite. "136 passed" describes the
implementation's confidence, not its coverage.

### C-1 — The cross-runtime ECMAScript gate was never unexecuted

The first record's section 5 declared this gate "not run", then its section 5A reported executing it
as though closing an open gap. Both statements are wrong.
`tests/contracts/test_assessment_scope_contract.py::test_assessment_text_blank_policy_matches_actual_ecmascript`
already spawns a real `node` subprocess, feeds it the pattern taken from the **generated JSON
Schema**, and asserts verdicts over a 13-value hostile matrix including `"🌊" * 4096` → accept and
`"🌊" * 4097` → reject.

More pointedly, that test already uses `Array.from(value).length <= 4096` — the **code-point-correct**
idiom. The first record presented the UTF-16-versus-code-point divergence as a discovery; the
implementer had identified it and written the correct check before any review existed. The
divergence remains a true and useful caveat **for downstream consumers** who hand-roll a
`String.length` check, and section 5A's analysis of direction (it fails closed) stands. But it was
not an open charter gate, and the first record should not have claimed it as one.

### C-2 — The Draft 2020-12 dual-mode gate was also already covered

The first record listed this as not executed.
`test_json_round_trip_and_both_draft_schemas` calls `Draft202012Validator.check_schema` on **both**
`model_json_schema(mode="validation")` and `mode="serialization")`, then validates the dumped
instance against both validators, then asserts a full JSON round trip equals the original object.
That is the gate.

**Net effect:** of the three items the first record declared not executed, **two were never open.**
Only the second reviewer was genuinely outstanding — which is what this record supplies.

**The first record is deliberately left unedited.** D2 established the convention that a review
record is an immutable dated receipt — `DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md` section 2 states that
"the immutable first-review record is not rewritten" and routes every correction through a successor
record instead. Rewriting a merged review to erase its errors would destroy the audit trail that
makes the chain worth keeping. This record is that successor: where the two disagree, **this one
controls**, and sections 5A and 5 of the first record should be read as superseded by C-1 and C-2
above.

## 3. D3B against the confirmed D3A defect classes

This is the corpus-informed core of the pass. Each row was independently probed, not read off the
charter.

| D3A finding | Recurs in D3B-0? | Evidence |
|---|---|---|
| **DOM-07** versioned contract silently accepts unversioned payloads | **No** | All six D3B models declare `schema_id`/`contract_version` as `Literal[...]` with **no default**, matching D3A's remediated pattern. `test_material_schema_and_explicit_fields_have_no_defaults` deletes each of 11 field positions and requires a `ValidationError` |
| **DOM-04** binary floats lose financial identity | **Structurally cannot** | D3B carries **zero** `float`/`Decimal` material fields. The only `int`s are `min_length`/`max_length` on the internal `_ExactStringJsonSchema` metadata dataclass. D3B-0 declares a compatibility *plan* — selectors, units, bases — never a value, so the entire precision class is out of reach by construction |
| **DOM-02** capacity semantics erase DC/AC/nameplate | **No — and stricter than required** | The solar DC route is a **biconditional**: `SOLAR_RESOURCE_DC_CAPACITY_MW` requires `solar_pv` + `electrical_basis=dc` + nameplate, and *any other* selector presented with `dc` is refused. Units close it: `AC→{MWac}`, `DC→{MWdc, MWp}`, `NOT_APPLICABLE→{MW}` |
| **DOM-01** storage topology incomplete | **No** | `V14StorageCapacitySelector` carries all three routes (`technology_power_mw`, `technology_energy_mwh`, `technology_duration_h`); `test_hybrid_and_storage_only_request_graphs_are_element_complete` covers both shapes |
| **DOM-06** multi-jurisdiction lacks site identity | **No** | `_scope_is_closed_and_explicit` requires **exactly one** `JurisdictionSubject.SITE`, and `test_non_site_jurisdiction_remains_subject_routed_not_site_inferred` proves a non-site jurisdiction is not promoted to a site |
| **DOM-08** unprovable claim states | **No** | The receipt takes DOM-08's *first* remediation: `receipt_scope: Literal["declared_authored_scenario_validation"]` names itself a declaration, and the docstring disclaims independent assurance. `test_schema_has_no_achieved_grade_review_release_or_support_fields` holds the line |
| **DOM-03** material basis lacks provenance closure | **Partially — see finding D3B-2P-01** | Currency, `price_basis_id` and nominality are cross-bound scope↔assertion and all drift is refused. The **dates are not closed** |
| **DOM-05** partial states that can never become valid | **Not applicable as posed** | D3B holds no partial numeric operands to reconcile. Its analogue — the deliberate refusal to order `evidence_cutoff` against `valuation_date` — is correct: no universally valid ordering exists, and the charter says so explicitly |

D2's own hard-won boundaries also hold: no achieved grade, no release or review authority, no AI or
software actor in an authority role, no Sri Lankan fallback, and a strictly pure import direction.

## 4. Finding D3B-2P-01 — the two material assessment dates have no closure (MEDIUM)

**Neither the implementer's 136 tests nor the first review pass caught this.**

`AssessmentScope` declares `evidence_cutoff: date` and `valuation_date: date`. Neither has any bound.

`valuation_date` *appears* protected — moving it alone is refused. That protection is **incidental,
not designed**: it comes only from `PriceBasisAssertion` carrying a second copy of the same value,
and the refusal message says exactly that — `price-basis assertion must match every corresponding
scope axis`. Move both copies together and any date is accepted:

```
scope valuation_date -> 2099-12-31 alone          : refused
scope AND price assertion -> 2099-12-31 together  : ACCEPTED
scope AND price assertion -> 0001-01-01 together  : ACCEPTED
```

`evidence_cutoff` has no second copy anywhere in the contract and is unconstrained across the whole
representable range — `0001-01-01`, `1900-01-01`, `2099-12-31` and `9999-12-31` are all accepted,
including with `evidence_cutoff` 7,973 years after `valuation_date`.

**This is the D3A-DOM-03 failure shape, reproduced one layer up.** That finding was recorded as: *"An
arbitrary future nominal basis dated 2099-12-31 was accepted after the conversion date was made to
match."* Mutual consistency between two declared copies is not a bound, and D3B relies on exactly
that for `valuation_date` and on nothing at all for `evidence_cutoff`.

**Why it matters.** `evidence_cutoff` is not decorative — in D2 it is a live admissibility gate
(`package.py`): a source after cutoff is refused, a source not effective at cutoff is refused,
evidence and packs expired before cutoff are refused. A far-future cutoff **widens** what counts as
current, which is the fail-open direction.

**Why it is medium and not blocking.** Three mitigations, each verified:

1. Nothing consumes `AssessmentScope` yet — `grep` across `analytics/`, `app/` and `api/` finds only
   the package's own re-export. The gap is **latent**, not live.
2. D2 has a backstop: `evidence_cutoff cannot postdate package captured_at`. But it guards **D2's
   own `ScopeDeclaration`**, a different object, so it only fires if and when D3C faithfully
   propagates D3B's value into it — and it is one-directional, catching far-future only.
3. The far-past direction is largely self-limiting: an ancient cutoff refuses almost everything.

**The gap is structural, between dolphins.** D3B-0's charter says it declares only and never inspects
a live `ProjectCase`. D3B-1's charter section 6 enumerates what must reconcile — "capacity, AEP,
turbine, cost, and FX bases" — and **never mentions dates**. The D3C charter does not own them
either. So neither the layer that declares the dates nor the layer that reconciles everything else
is currently responsible for them.

**Recommended repair**, in preference order:

1. Assign the dates explicitly to **D3B-1**'s reconciliation set, alongside capacity/AEP/cost/FX, so
   they are compared against the authored scenario rather than against a second copy of themselves.
2. Bind `valuation_date` and `evidence_cutoff` to real `ProjectCase` source or assumption identities,
   which is the repair D3A-DOM-03 actually received.
3. At minimum, add a negative control fixing the present behaviour as intentional, so a future reader
   cannot mistake the incidental cross-binding for a designed bound.

A bare calendar range (say 1970–2100) would suppress the symptom without closing the class and is
**not** recommended on its own.

## 5. Observations (non-blocking)

**O-3 — `outcome: Literal["pass"]` is informationally vacuous.** The receipt can only ever say
`pass`; `fail` and `pending` are both refused (the latter has its own negative control). This is
correct fail-closed design — a request without a passing validation must be unconstructible — but the
field carries no bits, and a future version admitting `fail` would silently change its meaning for
every reader that assumed `pass`. Worth a comment in the model, not a change.

**O-1 and O-2 from the first record stand**, and this pass adds nothing to them: the `__all__`
ordering drift that no enabled ruff rule catches (`[tool.ruff]` sets only `src`/`exclude`, so
`RUF022` never runs), and the `AssessmentText` interior control-code-point caveat for downstream
emitters.

## 6. Independent command receipt

At `main` = `70e7d37`, `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`
(Python `3.12.13`), `PYTHONPATH="$PWD"`.

| # | Probe | Result |
|---|---|---|
| 1 | `grep -nE 'schema_id\|contract_version' assessment_scope.py` | 6 models, all `Literal[...]`, **no defaults** |
| 2 | `grep -nE ':\s*(float\|int\|Decimal)\b' assessment_scope.py` | only `min_length`/`max_length` on internal schema metadata — **zero material numeric fields** |
| 3 | scope `valuation_date` moved alone | refused — `price-basis assertion must match every corresponding scope axis` |
| 4 | scope **and** price assertion moved together to `2099-12-31` / `0001-01-01` | **ACCEPTED** (finding D3B-2P-01) |
| 5 | `evidence_cutoff` ∈ {`0001-01-01`, `1900-01-01`, `2099-12-31`, `9999-12-31`} | **ACCEPTED** in every case |
| 6 | scope `reporting_currency`, `price_basis_id`, `price_nominality` drift | each refused |
| 7 | `ProjectCaseReference.revision` ∈ {`0`, `-1`, `10^18`} | each refused |
| 8 | receipt `outcome` ∈ {`fail`} | refused |
| 9 | `grep -rln AssessmentScope analytics/ app/ api/` | only the package re-export — **no consumer yet** |
| 10 | `grep -nE 'evidence_cutoff' package.py` | live admissibility gate + `captured_at` backstop on D2's own scope |
| 11 | Read `test_assessment_scope_contract.py` in full | 64 test functions / 136 cases; C-1 and C-2 established |

## 7. Disposition

**ACCEPTED at `5c492c3`**, as the second pass required for a complex script.

D3B-0 is materially stronger than D3A's rejected candidate, and it is stronger *because* the D3A
findings were absorbed: no default versioning, no binary floats, typed capacity bases, complete
storage routes, exactly one site subject, and a self-declaring receipt that claims no assurance. The
digest guard and the lexical grammars are the best-engineered parts of the slice, and the
implementer's own suite is more rigorous than the first pass credited — it runs a real ECMAScript
cross-check and both Draft 2020-12 modes.

One finding stands: **D3B-2P-01**, the unclosed assessment dates, which reproduces the D3A-DOM-03
shape and currently belongs to no dolphin. It is medium, latent, and should be assigned to D3B-1
before that slice is implemented — that is the cheapest moment to close it, and after D3B-1 lands it
becomes materially more expensive.

This record does not lift `#1110`'s `HOLD`, which remains OPEN with 0 of 23 controls checked, and
changes no KPI, finance or release state. `VERSION` remains `15.4.0`.
