# Dolphin 3D grade/release policy charter — independent disposition record

**Reviewed object:** [`DOLPHIN_3D_GRADE_RELEASE_POLICY_CHARTER.md`](DOLPHIN_3D_GRADE_RELEASE_POLICY_CHARTER.md)
**Bound to:** `main` = `829fd14`, charter SHA-256 unchanged at
`9ac0e1f8aaabc9fcaaa0343ad16e97049ff0c1a0e6a5ed75656e2844a9aed769` (verified at recording, base
`1240a9a`).

## COMBINED DISPOSITION: **REJECTED**

| Reviewer | Lens | Disposition | Findings |
|---|---|---|---|
| Reviewer 1 | Renewable-project domain specialist | **REJECTED** | 11 — 3 blocking, 5 high, 2 medium, 1 observation |
| Reviewer 2 | Audit and assurance specialist | **REJECTED** | 14 — 3 blocking, 4 high, 4 medium, 2 low, 1 observation |

Under `RECRUIT-01` either rejection is decisive. **25 findings, 6 blocking, 9 high.**

This record confers no achieved grade, package approval, assurance acceptance, release, deployment,
lender or Board authority, and lifts no `HOLD`. `#1110` remains `OPEN` with 0 of 23 controls checked
and was not touched.

## 1. Independence — this one is real

Unlike the D3B second pass and the D3C contracts disposition, both of which self-declared that one
agent wore both lenses, **these are two genuinely separate reviewers**, dispatched in parallel, each
told not to assume the other covered its gaps and not to defer to any prior reviewer. Neither wrote
to the tree. Each bound its disposition to an exact SHA.

Neither authored the charter. The coordinator did — and the coordinator is the party this record
finds against.

## 2. The blocking findings

### Domain

**D3D-DOM-01 — grade-specific materiality is structurally unrepresentable.** D1 §6.2: *"Materiality
thresholds MUST be explicit, grade-specific where necessary."* The charter's `MaterialityDetermination`
binds a section to a two-valued `Materiality` enum with **no grade dimension**, while D1 §7's
aggregation is a *walk over candidate grades*. A section material for `lender_grade` but not for
`screening` cannot be expressed, which makes `screening` unreachable for any lender-target project.

**D3D-DOM-02 — "profiles may only narrow, never widen" is vacuous.** The charter's central safety
claim is enforced by one control. But `GradeProfile` can only express production, evidence, review
and pack-support sets, while D1 §7's `lender_grade` row names five requirement axes the vocabulary
cannot represent at all. A profile cannot widen what it cannot express — so the guarantee holds
trivially and protects nothing on those axes.

**D3D-DOM-03 — de-materialisation is an uncontrolled inflation path.** D1 §7.1's stem gates every
blocker on *"a material claim"*. So removing a section from materiality removes it from **both** the
aggregation domain **and** the blocker set. The charter's only control catches the fully empty set.
The reviewer's counterexample — a standalone 250 MW / 1000 MWh BESS at `lender_grade` target,
retaining only the five always-applicable rows as material — passes every listed control.

### Assurance

**F-01 — the charter's central factual premise is false.** It states *"D2 already carries every input
the D1 §7 rule consumes."* D1 §7 is a **per-grade** test; D2's evidence axis has exactly one positive
value, `EvidenceStatus.SUFFICIENT_FOR_ACHIEVED_GRADE`, which is self-referential and carries no grade
dimension. It cannot distinguish *sufficient for screening* from *sufficient for lender_grade*. The
review axis has the same defect. The claim that the increment is "blocked on nothing" rests on this
premise.

**F-02 — `lender_grade` remains self-awardable.** *Independently re-verified by the coordinator.*
`package.py:1382 _validate_authority_actor` tests exactly four things: `kind ∈ {HUMAN, INSTITUTION}`,
`organization is not None`, `identity_verified`, `authority_basis is not None`. **There is no
independence test and no comparison against the producing organisation.** The charter's hazard 4
claims self-clearing is refused *"as D2 already refuses it"* — D2 does not refuse it in the sense D1
§7 requires. The model owner passes, and D1 §12.1(8) names the model owner as one of four
self-clearing actors.

**F-03 — the charter's own central positive control is unobservable within its own increment.** Its
central mechanism is that only a `GradeDecision` may populate `achieved_grade`. But §7 states the
increment "ships as a contract with no live effect on any package", and `package.py:204-211` still
raises on any non-`ungraded` grade. So the mechanism can ship **100% green having never once been
demonstrated to work** — precisely the `VERIFY-01` posture the charter itself invokes against others.

## 3. Findings the coordinator re-verified rather than accepted

`RECRUIT-01` makes every statement a claim to verify, and that applies to reviewers too. Three were
checked directly; all three hold.

| Claim | Command | Result |
|---|---|---|
| **F-07** `ungraded` is not merely un-ordered but sorts **above everything** | `sorted([g.value for g in AchievedGrade])` | `['decision_grade','illustrative','lender_grade','screening','ungraded']`; `min()` → **`decision_grade`**; `ungraded > lender_grade` → **True** |
| **F-02** the D2 authority guard has no independence test | `sed -n '1382,1395p' …/package.py` | four checks only: kind, organization, identity_verified, authority_basis |
| **F-05** the contract package is not a leaf | `grep -n 'from analytics.contracts_v14 import' …/feasibility_report_contract/*.py` | `context_binding.py:29` — it already imports it |

**F-07 is the sharpest of the set.** The charter's hazard 8 asserts `ungraded` must "never sort above
`illustrative`". The real defect is far worse: because all three grade enums are `str, Enum`, Python's
native `min()` — the obvious implementation of D1 §7's minimum rule — returns `decision_grade` for a
set containing `ungraded` and `lender_grade`. The fail-closed sentinel sorts to the **maximum**. The
charter tested the wrong invariant, and a naive implementer following it would ship an inflation bug.

## 4. Factual errors in the charter, found by reading the merged code

The charter asserted several things about the codebase that are simply untrue at `829fd14`. Every one
was assertable-then-checkable, and none was checked before writing:

- **§4 item 4** — *"Nothing defines the decision that would populate `grade_decision_id`."* False.
  `records.py:753` defines `DecisionRecord` with `kind: DecisionKind` (including `GRADE`), a nullable
  `grade`, `authority_actor_id`, `evidence_ids` and a `_grade_decision_is_typed` validator. Proposing
  a second decision record is a **CCCDIR breach** (F-04).
- **§4 item 2 / §10** — *"No contract states how materiality is determined"* and *"Upstream: none."*
  **Two** declaration surfaces already exist: `ScopeDeclaration.materiality_rule` (`records.py:176`)
  and the `AssessmentScope` rule (`assessment_scope.py:578`). The charter proposes a third, at a
  different cardinality, naming neither (D3D-DOM-04).
- **§7** — *"stays a leaf package… must not import `analytics.contracts_v14`… as the programme already
  pins it."* False in both halves (F-05).
- **§6** — D1 §12.1(5) forbids three derivations **by name**: average, target copy and **run-mode
  map**. The charter has hazards for the first two and nothing for the third; `grep -c 'run.mode'`
  over the charter returns **0** (D3D-DOM-05).

## 5. Two live defects in merged code, surfaced by this review

These are not charter defects. They exist on `main` now.

- **F-06 — a package with zero material sections validates today.** Runtime receipt: using the
  repository's own `_build_package()` fixture factory, setting `materiality=NON_MATERIAL` on all
  twenty sections and re-validating through `FeasibilityReportPackage.model_validate` was **ACCEPTED**.
  `SectionRecord.materiality` is read by no validator at `829fd14`.
- **F-07 — the grade enums are natively mis-ordered**, as above. Any consumer calling `min()`/`max()`
  or `sorted()` on them today gets a wrong answer silently.

Both warrant their own dolphins, independent of whether D3D is ever revised.

## 6. Disposition of the four pre-existing E-3 flags

Both reviewers were required to take a position on each flag recorded in
[`DOLPHIN_FOUNDING_INGRESS_AND_ERRATA.md`](DOLPHIN_FOUNDING_INGRESS_AND_ERRATA.md) §2. **None was
disagreed with; all survive, most refined:**

| Flag | Domain | Assurance |
|---|---|---|
| 1 — universal human-decision gate collapses D1 truths 6 and 7 | REFINE | REFINE |
| 2 — empty-set rule inverts D1's literal text | REFINE | AGREE |
| 3 — "minimum" quotation drops its antecedent | REFINE | AGREE |
| 4 — "eight separate controls" is a floor | REFINE | REFINE |

The domain reviewer sharpened flag 1 materially: the universal gate does not merely over-reach, it
makes `illustrative` and `screening` **unreachable**, since requiring an institutional signatory to
award "demonstrates workflow on a hypothetical case" produces a *worse* disclosure outcome than the
correctly-labelled low grade it replaces (D3D-DOM-11).

One finding runs the other way and is recorded because the errata brief had flagged it as unverified:
**D3D-DOM-10 confirms the charter's §1.3 quotation of D2 is accurate.**

## 7. What this means

The charter is **rejected as a design**, not merely amended. Its two structural claims — that D2
already carries every input the rule needs, and that grade profiles can only narrow — are both false,
and its materiality model cannot express the grade dimension D1 requires. Six blocking findings is
not a revision list; it is a redesign.

What survives: the *problem statement* is sound. D1 §12.3 item 3 is genuinely orphaned, the naming
collision that orphaned it is correctly diagnosed, D2's half-policy hazard is quoted accurately, and
the increment is still worth doing. A successor charter should start from the D2 receipt
requirements the fresh D2 ingress produced in the same pod run — 21 enumerated requirements, of which
**R1 alone disqualifies the current charter**: D2's "typed grade-policy receipt" means a frozen
Pydantic v2 model, and *"a prose charter does not meet the adjective D2 chose."*

Under `RECRUIT-01` this disposition binds to `829fd14` and does not transfer. A revised charter needs
a fresh review chain.

**Recorded separately from any charter edit**, per the E-1 lesson: the D3C disposition lapsed on
arrival because its own pull request edited the object it was disposing. The charter's §11 still
reads "Not yet reviewed"; correcting it is a **separate** dolphin, deliberately not bundled here.
