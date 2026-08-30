# Dolphin 3C result-facade contracts — independent disposition record

**Reviewed object:** [`DOLPHIN_3C_RESULT_FACADE_CHARTER.md`](DOLPHIN_3C_RESULT_FACADE_CHARTER.md)
at SHA-256 `031eeb8e1619d1e301f25c5a9e8cdb908adc5e7d34e24c686abd95061c59f74e`, on `main` =
`2945a087703bb1da17df839a25c3a389d6c6bcd3`.

**Proposed contract:** `dutchbay.section_result_facade.v1` / `1.0.0` — design only, no
implementation accompanies it.

**Disposition: ACCEPTED, subject to four required amendments** (§4). Three bind before
implementation begins; the fourth is a separate dolphin. This disposition **unblocks** D3C's
remaining scope — the translation into D2 records and the emission of an ungraded, held package —
which charter §10 gates on acceptance of these contracts.

This record establishes no achieved grade, package approval, assurance acceptance, release, lender
or Board authority, and lifts no `HOLD`. Issue `#1110` remains `OPEN` with 0 of 23 controls checked.

## 1. Role separation, and its limitation here

The owner confirmed on 2026-08-30 that dispositions keep D2's domain-plus-assurance pairing rather
than the single reviewer that documentation attracts. This record is structured accordingly: §2 is
the renewable-project domain pass, §3 the audit-and-assurance pass, and they use different lenses
and different probes.

**Both passes were performed by the same agent.** That does **not** satisfy the structural
independence D2 §2 intends — "the first role cannot self-approve the other two" is a statement about
*separate actors*, and separating lenses inside one actor is a weaker substitute. Two mitigations
apply and neither removes the limitation: the reviewer did not author the charter, and every
load-bearing claim was independently executed against the repository rather than read. Where a probe
contradicted the reviewer's own expectation, the reviewer was wrong twice (§5) and the record says
so.

What would satisfy the requirement is two distinct reviewers, and the profiles for them are given in
the second-pass review discussion: a renewable feasibility-domain specialist able to construct
counterexamples, and a contract/assurance specialist independent of them.

## 2. Domain pass — renewable-project specialist lens

### 2.1 What the charter gets right, and it is substantial

The charter's §4 analysis of the seam is the strongest part of the document. It states the gap as
**five conversions that have no honest default** — float to decimal is a precision claim the float
cannot support; `dict[str, Any]` to a typed register needs an enumeration that does not exist
upstream; `None`-or-`0.0` forces an absent-versus-computed decision; every numeric needs a unit
upstream encodes only in a field name; every value needs provenance upstream does not carry. That is
an accurate and unflattering description of `contracts_v14`, and it is the right framing: each
becomes an explicit fail-closed declaration rather than an implicit conversion.

Its §9 is unusually honest for a design document. It records that four of its own five originally
posed questions were **mis-posed**, and that in two cases every option offered was wrong. A charter
that overturns its own framing on evidence is doing the thing this programme keeps asking for.

**Claims independently verified and held:**

| Charter claim | Verification |
|---|---|
| §6.1 `WaccComponents` defaults `wacc_prudential`/`risk_free_rate` to `0.0`, `target_equity_to_value` to `1.0` | `contracts_v14.py:174,175,180` — exact |
| §6.1 `ScenarioResult.wacc` and `discount_rate_used` default to `None` | `contracts_v14.py:248,249` — exact |
| §6.1 the repository was "bitten twice by exactly this shape" | `tests/lint/test_no_decorative_discount_rate.py` and `test_no_decorative_grid_loss.py` both exist |
| §4 nine-member `CapabilityOutcome` union | `vocabulary.py:212-223` — all nine members, exact names |
| §4 `CanonicalValue` **rejects a numeric without an explicit unit** | `records.py` model validator raises `numeric CanonicalValue requires an explicit unit`; empirically refused |
| §9.1 `DerivationRecord.precision_policy` already exists as mandatory `NonEmptyText` | `records.py:668` — exact |
| §9.1 canonical KPI values | `tests/_canon.py:35,37,42` — `-0.001166233356501311`, `-91810995.06051566`, `1.3`, exact |
| §4 `OutputClass.SYNTHETIC` requires a persistent warning | `records.py:561` — exact |

### 2.2 Finding D3C-DOM-01 — nothing requires precision to be *declared* (required amendment)

§9.1 is the charter's central domain thesis: precision is declared **per field**, because one rule
cannot serve a KPI vector spanning `1e-3` to `1e8` that mixes ratios, currency and covenant
thresholds. The reasoning is correct and the worked table is persuasive.

**The control list does not enforce it.** D2's `CanonicalValue.precision` is
`NonNegativeInt | None = None` — optional. §8 lists *"a declared precision exceeding the reviewed
per-field rule is refused"*, which presupposes a precision is present, but **no control requires one
to exist at all**. Verified directly:

```
CanonicalValue(value_type=DECIMAL, value='-0.001166233356501311', unit='ratio')
  -> ACCEPTED with precision = None
```

That is the canonical project IRR carried with a unit, a full-precision lexical value, and **no
declared precision**, satisfying every control §8 lists while defeating §9.1 entirely. The unit
requirement is enforced by D2; the precision requirement exists only in the charter's prose.

**Required amendment:** add an explicit control — *a carried numeric whose `CanonicalValue` declares
no precision is refused at construction* — and state that D3C's `CarriedValue` narrows D2's optional
`precision` to mandatory. D3C may legitimately be stricter than D2; it must say so rather than
inherit an optionality that contradicts its own thesis.

### 2.3 Finding D3C-DOM-02 — the engine-less sections are never enumerated (required amendment)

§9.5 resolves a genuine category error well: a capability disposition is not a section applicability,
so a narrative section gets **no capability disposition at all** rather than a `not_applicable` one.
The reasoning holds and is properly grounded in D1 §3.2.

Two defects in the execution:

1. **"the engine-less six" appears exactly once, at line 370, and is never enumerated.** Which six is
   a domain judgement with contract consequences, and §6 hazard 6 explicitly forbids inferring
   section binding — *"declared per upstream field and reviewed, not inferred from name
   similarity."* Leaving the six to the implementer contradicts the charter's own hazard.
2. **§9.5 understates D1 §8.** It cites sections 18 and 19 as "Always applicable". D1 §8 marks
   **five** — sections 1, 2, 18, 19 and 20 — and §20 is additionally "grade-critical". This cuts in
   the charter's favour, strengthening the argument that `not_applicable` is contract-violating, but
   an understated citation invites an implementer to under-apply the rule.

**Required amendment:** enumerate the engine-less sections by stable ID in the charter, and correct
the always-applicable citation to all five.

## 3. Assurance pass — audit and assurance specialist lens

### 3.1 Fail-closed and authority boundaries

The authority boundary is the strongest control in the design, and it is structural rather than
procedural: §5 states the facade *"carries no grade, review, release or achieved-grade field. It
cannot express them, so it cannot infer them."* Structural inexpressibility is the only form of this
guarantee worth having, and it matches what D2 did when it hard-pinned `achieved_grade=ungraded`.

§8's adoption of the D3B veto history is well-judged. Three of those five classes — mutable schema
metadata, hash-seed-dependent error selection, insertion-order-dependent error selection — are
**invisible to an ordinary green suite**, because they change which error appears or change a schema
without changing acceptance. Requiring them as controls is precisely the `VERIFY-01` posture.

The `independent oracle` requirement — a fixture from a real recorded v14 run rather than the
facade's own construction — is the single most valuable control in the list, and directly answers
`TEST-01`.

### 3.2 Finding D3C-ASR-01 — the obvious oracle fixtures are the wrong shape (required amendment)

§8 requires an oracle *"derived from a real recorded v14 run rather than from the facade's own
construction"* but does not say which. The repository's obvious candidates are
`tests/fixtures/finance/*_expected_kpis.json` — four of them, covering lendercase, capex cases,
kalpitiya and mullikulam.

**Those fixtures are the wrong shape, and using them would defeat the charter's own hazard 5.** They
are flat scenario-to-KPI numeric vectors — the `expected_kpis` shape, which is what
`return_full_result=False` produces *after* `normalize_kpi_dict`. That is exactly the lossy path
hazard 5 identifies: a KPI that became non-numeric upstream is already gone, indistinguishable from
never having been emitted. An oracle captured downstream of the loss cannot prove the facade carries
a genuine result without loss; it can only prove the facade reproduces an already-lossy projection.

**Required amendment:** state that the oracle fixture must be captured with `return_full_result=True`
and must retain `annual_rows`, `debt_result`, `metadata`, warnings and `None` values, and explicitly
exclude the existing `*_expected_kpis.json` fixtures from that role. The repository already has seven
call sites using `return_full_result=True`, so capture is feasible today and does **not** wait for
D3B-1 — a point worth stating, since §10 lists D3B-1 as prerequisite and a reader could conclude the
oracle is unbuildable until then.

### 3.3 Finding D3C-ASR-02 — the gateway drop is less observable than its own docstring claims (separate dolphin)

§6.5's claim is **verified exactly**: `evaluate_with_overrides` has `return_full_result: bool = False`
as its default, and the `False` branch returns `normalize_kpi_dict(raw_kpis)`, which `float()`-coerces
every entry and, on `TypeError`/`ValueError`, emits `logger.debug(...)` then `continue`s.

The charter understates it in one respect. `normalize_kpi_dict`'s own docstring says it *"Filters out
non-numeric values and **logs warnings** for skipped entries"* — but the code logs at **debug**. The
documented observability overstates the actual, so a maintainer reading the docstring would expect a
dropped KPI to surface at warning level in ordinary operation, and it does not.

This is a defect in `analytics/evaluation_v14.py`, not in the D3C design, and the charter's
conclusion — that the gateway must be called with `return_full_result=True`, which is D3B-1's
obligation — is correct and unaffected. **Recommended as its own dolphin**, since it is a
one-line-class fix in engine code with its own review surface, and bundling it into D3C would
violate `DELIVERY-01`.

## 4. Required amendments

Binding before D3C implementation begins:

1. **D3C-DOM-01** — add a control requiring declared precision on every carried numeric, and state
   that D3C narrows D2's optional `CanonicalValue.precision` to mandatory.
2. **D3C-DOM-02** — enumerate the engine-less sections by stable ID; correct the always-applicable
   citation from two sections to five.
3. **D3C-ASR-01** — specify the oracle fixture as `return_full_result=True` capture retaining
   `annual_rows`, `debt_result`, `metadata`, warnings and `None`; exclude the existing
   `*_expected_kpis.json` fixtures from that role; note that capture does not wait for D3B-1.

Separate dolphin, not blocking:

4. **D3C-ASR-02** — correct `normalize_kpi_dict`'s docstring, or raise the drop to `logger.warning`,
   so documented and actual observability agree.

§9.6's two genuinely open items — the per-field precision table and the field-to-unit table — remain
open and are correctly characterized as domain data rather than design choice. They are inputs to
implementation, not defects in the design, and D3C-DOM-01 makes supplying the first of them
enforceable rather than aspirational.

## 5. Reviewer errors, recorded rather than dropped

Two expectations of this reviewer were wrong, and the probes corrected them:

1. **`CanonicalValue` unit enforcement.** Reading the field declaration `unit: UnitToken | None = None`
   suggested the charter's "rejects any numeric without an explicit unit" was false. It is true: a
   model validator raises for `INTEGER`/`DECIMAL` with no unit, and construction was empirically
   refused. Field declarations are not the contract; validators are.
2. **Oracle availability.** An initial concern that the independent-oracle control could not be
   satisfied before D3B-1 was wrong — seven `return_full_result=True` call sites already exist. The
   real problem turned out to be different and sharper, and became D3C-ASR-01.

## 6. Command receipt

At `main` = `2945a08`, `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`
(Python `3.12.13`), `PYTHONPATH="$PWD"`.

| # | Probe | Result |
|---|---|---|
| 1 | `shasum -a 256 docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md` | `031eeb8e…f74e` |
| 2 | `grep -n 'return_full_result' analytics/evaluation_v14.py` | `330: return_full_result: bool = False`; `400: if return_full_result:` |
| 3 | `sed -n '223,258p' analytics/evaluation_v14.py` | `float(value)` … `except (TypeError, ValueError): logger.debug(...); continue`; docstring says "logs warnings" |
| 4 | `grep -nE 'risk_free_rate\|wacc_prudential\|target_equity_to_value' contracts_v14.py` | `174`, `175`, `180` — defaults `0.0`, `0.0`, `1.0` |
| 5 | `grep -nE '^\s+(wacc\|discount_rate_used)\s*:' contracts_v14.py` | `248`, `249` — both default `None` |
| 6 | `ls tests/lint/test_no_decorative_{discount_rate,grid_loss}.py` | both present |
| 7 | `grep -nA12 '^class CapabilityOutcome' vocabulary.py` | nine members, exact |
| 8 | `CanonicalValue(DECIMAL, '0.30000000000000004')` no unit | **refused** — `numeric CanonicalValue requires an explicit unit` |
| 9 | `CanonicalValue(DECIMAL, '-0.001166233356501311', unit='ratio')` | **ACCEPTED, `precision=None`** → D3C-DOM-01 |
| 10 | `grep -n 'precision_policy' records.py` | `668: precision_policy: NonEmptyText` |
| 11 | `grep -nE 'LENDER_PROJECT_IRR\|_NPV\|_MIN_DSCR' tests/_canon.py` | `35`, `37`, `42` — values exact as charter cites |
| 12 | `grep -c 'Always applicable' docs/FEASIBILITY_REPORT_CONTRACT.md` | **5** (charter cites 2) → D3C-DOM-02 |
| 13 | `grep -n 'engine-less' docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md` | one hit, line 370, never enumerated → D3C-DOM-02 |
| 14 | `ls tests/fixtures/finance/*expected_kpis.json` + key shape | four fixtures, flat scenario→KPI numeric vectors → D3C-ASR-01 |
| 15 | `grep -rl 'return_full_result=True' tests` | 7 files — oracle capture feasible today |

## 7. Disposition

**ACCEPTED at charter SHA-256 `031eeb8e…f74e`, subject to the four amendments in §4.**

The design is sound. Its seam analysis is accurate, its authority boundary is structural rather than
promised, it adopts the D3B veto classes that an ordinary green suite cannot observe, and it
overturns four of its own five original questions on evidence. Every load-bearing factual claim
tested here held.

The three binding amendments are refinements to the control list and to two citations, not
structural defects: one closes a gap between the charter's central precision thesis and its
enforceable controls, one removes an inference the charter's own hazard forbids, and one prevents an
oracle that would certify the very loss the design exists to prevent.

**D3C's remaining scope is therefore unblocked** and may be chartered. Two constraints carry into
that charter: the amendments above bind its implementation, and this disposition was produced by one
agent wearing two lenses, which is weaker than the two independent reviewers D2 §2 requires.
