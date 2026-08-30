# Dolphin 3D grade, materiality and release policy charter

**Document status:** non-normative implementation charter and review aid — **design proposed, not
implemented**
**Proposed machine contract:** `dutchbay.grade_release_policy.v1` / `1.0.0`
**Normative authority:** DBAY-FRC-001 v1.0.0, sections 4, 7, 7.1 and 12.1(8)
**Controlled human projection:** DBAY-GFR-MT-001 v1.0.0
**Target package contract:** `dutchbay.feasibility_report_package.v1` / `1.0.0` (Dolphin 2, merged)

## 1. Purpose, authority, and why this work was orphaned

Dolphin 3D implements **DBAY-FRC-001 section 12.3 item 3, "Grade and release policy"**: *implement
centralized applicability, materiality, grade aggregation, external hold, review and package-release
contracts without changing the live HOLD.*

### 1.1 The orphaning, recorded so it cannot recur

This item had no charter until now, and the cause is a naming collision worth stating plainly.

`DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md` section 5 deferred **two** different D1 items to the same
label. It assigned item 2 to "Dolphin 3" and, in the same section, wrote that *"applicability/
materiality policy, grade aggregation, grade ceilings and release policy remain **Dolphin 3**
work"* — which is item 3. The Dolphin 3 programme that followed then chartered **only item 2**,
split three ways as D3A, D3B and D3C. Every one of those three charters explicitly excludes grade
inference; D3C's exclusion list names *"grade, review, release or achieved-grade inference of any
kind"*.

So item 3 was inside "Dolphin 3 work" by D2's assignment, and outside every Dolphin 3 charter by
their own exclusions. It fell between them and stayed there.

This charter is therefore **Dolphin 3D**: the fourth member of the Dolphin 3 family, taking the half
of "Dolphin 3 work" that 3A, 3B and 3C each declined. The lettering is retained rather than opening
a new integer, because renumbering would break the D2 charter's existing "Dolphin 4" reference to
D1 item 4 (canonical serialization) and invite a second collision.

| D1 §12.3 item | Owner | Status |
|---|---|---|
| 1. Machine contract and taxonomy parity | Dolphin 2 | merged, both specialists `ACCEPTED` |
| 2. Orchestration and disposition | Dolphin 3A / 3B / 3C | 3A and 3B-0 merged; 3B-1 and 3C outstanding |
| **3. Grade and release policy** | **Dolphin 3D — this document** | **not started** |
| 4. Provenance, manifests, canonical serialization | Dolphin 4 | not started |
| 5. Surface convergence | not chartered | not started |
| 6. DBPL projection | not chartered | not started |
| 7. Pack formalization | not chartered | not started |

### 1.2 This charter designs no policy

**The policy already exists and is normative.** D1 section 7 specifies the four grades, their
permitted uses, their prohibitions and their ceiling conditions in a controlling table. D1 section 7
fixes the aggregation rule — *"the highest grade for which every applicable material section
satisfies the grade's production, evidence and review requirements. **It is never an average**"* and
*"the package grade is the **minimum** across applicable material sections after all report-level
blockers"*. D1 section 7.1 enumerates **eight** report-level blockers. D1 section 12.1(8) forbids the
producing process, CI, model owner or evidence score from self-clearing a hold, review or release.

What is missing is not a policy. It is the **typed contract and evaluator that make the existing
policy machine-enforceable**, plus the materiality and applicability determination D2 section 5 lists
as an open semantic hole. A candidate who opens by proposing a grading formula has misread the
brief: the formula is written, it is a minimum with blockers, and inventing an alternative is out of
scope.

### 1.3 The half-policy hazard, which is this increment's central risk

D2 did not omit grade policy by oversight. It found a partial one **actively unsafe** and removed it:
*"package grade is always `ungraded`, section grade is `ungraded` or N/A, and `grade_decision_id` is
absent. **This removes the prior unsafe half-policy**."* The v1 root therefore hard-pins
`achieved_grade=ungraded` and reserves non-sentinel vocabulary *"for a future version with a typed
grade-policy receipt."*

**This charter is that receipt.** It follows that Dolphin 3D ships whole or not at all: an increment
that implements aggregation without the blockers, or blockers without the human decision authority,
recreates precisely the state D2 judged unsafe and would be worse than the current hard pin.

## 2. Increment boundary

**In scope.**

1. A strict, immutable **grade profile contract** expressing D1 section 7's per-grade production,
   evidence and review requirements as typed, reviewable data rather than code branches.
2. A **materiality and applicability determination contract** — which sections are material for a
   given scope, and on what declared rule — closing the D2 section 5 hole.
3. A **grade evaluation contract**: a pure, deterministic function from the existing `SectionRecord`
   truths plus report-level state to a proposed achieved grade **and its full blocker set**.
4. A **grade decision record** binding a proposed grade to a positive, scope-bound decision by a
   verified human or institutional actor, which is the only thing that can set `achieved_grade`.
5. A **release authorization contract** expressing D1 section 7.1's release condition and the
   external-evidence hold, without changing any live `HOLD`.

**Out of scope, deliberately.**

- Any change to D1 or D0. This charter cannot weaken the section 7 table; grade profiles may impose
  stricter requirements and **must not** relax them.
- Computing, deriving or inferring an achieved grade **without** a decision record. A computed value
  is a *proposal*, never an achievement.
- Self-awarding `lender_grade` under any circumstance — D1 section 7 states *"the platform MUST NOT
  self-award this grade."*
- Lifting, checking or altering any live `HOLD`, `#1110` control, or P01/P02/P03/F5-02 state. D1
  section 12.1(17) makes adoption of this contract explicitly incapable of changing them.
- Section counts, coverage percentages or evidence scores as grade determinants. D1 section 7.1
  permits them to inform management and forbids them from overriding blockers or being labelled
  bankability certificates.
- Engine execution, finance mathematics, report rendering, API, persistence, or any `VERSION`/KPI
  change.

## 3. Three-role separation and recruitment

Unchanged from Dolphin 2 and binding here. The owner confirmed on 2026-08-30 that **dispositions
keep the domain-plus-assurance pairing**; two independent reviewers are required because this is a
complex script, not documentation.

1. **Implementation lead — principal assurance-policy and grade-authority contract engineer.** The
   ordering of competencies matters and is deliberate: assurance-standards literacy (what makes a
   grade *earned* — evidence sufficiency, competence, independence, scope) first; lender and
   investor technical-DD grading conventions second; model-risk discipline about what a model result
   can support third; typed Pydantic v2 contract practice fourth. This is not primarily a Pydantic
   role, and staffing it as one is the likeliest way to get a half-policy.
2. **Renewable-project domain specialist** — reviews whether the materiality rules and grade
   profiles are true for real wind, solar, BESS and hybrid projects across jurisdictions, and
   whether a section can be material in one scope and not another without the rule becoming
   arbitrary.
3. **Audit and assurance specialist, independent of both** — challenges every path by which a grade
   could be reached without a decision, a hold could be self-cleared, or a proposal could be
   mistaken for an achievement. This reviewer should additionally be able to represent the
   **lender and Board consumer**, because those parties are the ones who would rely on a grade, and
   their reliance is exactly what D1's prohibitions exist to protect.

**Disqualifying instinct:** treating a grade as a computed score. Grade is a *decision* under D1
section 7 and D2's remediation; computation only ever produces a proposal and a blocker set.

The D3B writer-lease state machine (`DOLPHIN_3B_EXECUTION_CHARTER.md` section 3.1) is mandatory here
unchanged: `READ_ONLY` → explicit SHA-bound lease → preflight → one bounded patch → verification →
durable checkpoint → `WAIT_FOR_REVIEW`, with any interruption revoking continuity.

**AI reviewers cannot close this increment.** Every record in this programme is explicit that these
are specialist AI reviews, not statutory assurance or verified human professional sign-off. That is
adequate for drafting and reviewing the *policy contract*. It is not adequate for the first actual
graded report, which needs a verified human professional signatory under D2's existing rules. The
charter states this now so it does not surface as a surprise at a Board gate.

## 4. What is actually missing

D2 already carries every input the D1 section 7 rule consumes. `SectionRecord` holds
`applicability`, `applicability_reason`, `production_status`, `evidence_status`, `review_status`,
`release_status`, `target_grade`, `achieved_grade`, `materiality`, and the jurisdiction and
technology pack bindings. `AchievedGrade`, `SectionAchievedGrade`, `AssessmentGrade`, `Materiality`,
`EvidenceStatus`, `ReviewStatus` and the release vocabulary all exist.

**The consequence is that this increment is blocked on nothing.** The evaluator is a pure function of
records D2 already defines, so it can be implemented and hostilely tested today against constructed
`SectionRecord` fixtures — no engine run, no D3B-1, no D3C. Dolphin 3D proceeds in **full parallel**
with the Dolphin 3 orchestration family and does not queue behind it.

Four things are genuinely absent:

1. **The grade profile as data.** D1's table is prose. Nothing expresses "what `decision_grade`
   requires of a material section's production, evidence and review states" in a form a validator
   can enforce or a reviewer can diff.
2. **Materiality determination.** `SectionRecord.materiality` is an input the caller supplies. No
   contract states *how* it is determined for a given scope, which is the D2 section 5 hole.
3. **The evaluator and its blocker set.** Nothing computes the D1 section 7 minimum or the section
   7.1 blockers.
4. **The grade decision record.** `grade_decision_id` exists in D2 and must currently be `None`.
   Nothing defines the decision that would populate it.

## 5. Proposed contract boundary

| Element | Proposed implementation | Controlling clauses |
|---|---|---|
| Identity and version | Mandatory `schema_id = dutchbay.grade_release_policy.v1` and `contract_version = 1.0.0`, **no defaults**, unknown or future values fail closed — the D3A-DOM-07 remediation pattern | D1 §5, §12.2 |
| Grade profile | `GradeProfile` binding one `AssessmentGrade` to the required `ProductionStatus`, `EvidenceStatus` and `ReviewStatus` sets per material section, plus required pack support. Profiles may **narrow** the D1 §7 table and are refused if they widen it | D1 §7 |
| Materiality rule | `MaterialityDetermination` binding one section ID to `Materiality` with an explicit declared rule and scope basis. Never inferred from whether the section produced output | D1 §8, D2 §5 |
| Grade evaluation | `GradeEvaluation` — a pure deterministic result carrying the **proposed** grade, the per-section grades it aggregated, and the **complete** blocker set. The minimum rule, never an average | D1 §7 |
| Blockers | `ReportBlocker` discriminated over all eight D1 §7.1 conditions. A blocker set is carried in full, never summarized to a count | D1 §7.1 |
| Grade decision | `GradeDecision` binding a proposed grade to a positive, scope-bound `DecisionOutcome` by a verified human or institutional signatory with organization and authority basis. **Only this can populate `achieved_grade`/`grade_decision_id`** | D1 §4, §7, §12.1(8); D2 §4 |
| Release authorization | `ReleaseAuthorization` expressing the §7.1 release condition and external-evidence hold, with no capability to alter a live `HOLD` | D1 §7.1, §10.6, §12.1(17) |
| Ceiling, not floor | Every profile and rule can only lower or hold the achieved grade relative to the D1 table. No path raises it | D1 §7 |
| Strict shape | Frozen Pydantic v2, extra-field refusal, stable discriminators, Draft 2020-12 schemas both modes, transport-neutral | D1 §9.2, §12.1 |

## 6. Fail-closed hazards this increment must refuse

Each needs an executable negative control that is first observed to fire.

1. **Target copied into achieved.** D1 §7: *"A target grade expresses intent. It MUST NOT be copied
   into `achieved_grade`."* The likeliest single defect in the increment.
2. **Averaging.** D1 §7 says the achieved grade *"is never an average"*. Any mean, weighted score,
   percentage or count-based aggregation is refused by construction, not by convention.
3. **Proposal mistaken for achievement.** A `GradeEvaluation` must be structurally incapable of
   setting `achieved_grade`. Only a `GradeDecision` can. The two must not share a field.
4. **Self-clearing.** D1 §12.1(8): the producing process, CI, model owner or evidence score cannot
   self-clear an external evidence hold, required independent review or release. A software or AI
   actor as decision authority is refused, as D2 already refuses it for `Prepared`/`Checked`/
   `Reviewed`/`Approved`.
5. **Self-awarded `lender_grade`.** Refused unconditionally, with its own control, because D1 states
   the prohibition in absolute terms.
6. **Blocker summarization.** A blocker set reduced to a count, a percentage or a score. D1 §7.1
   permits those to inform management and forbids them from overriding blockers or being labelled
   bankability certificates.
7. **Empty-set vacuity.** A report with **no** applicable material sections must not aggregate to the
   highest grade on a vacuous "every section satisfies" reading. The minimum over an empty set is
   `ungraded`, and it needs its own control.
8. **Ungraded treated as a fifth grade.** D1 §7: *"`ungraded` is the required sentinel when no grade
   is achieved; it is not a fifth grade."* It must never be orderable above `illustrative`.
9. **Invalid `not_applicable` used as an exclusion.** D2 already holds that invalid `not_applicable`
   dispositions remain blockers rather than exclusions; a section escaping aggregation by a bad N/A
   is a grade-inflation path.
10. **Live `HOLD` mutation.** Any path that alters `#1110`, P01/P02/P03, F5-02 or package release
    state is refused. D1 §12.1(17) is explicit that adopting this contract cannot change them.

## 7. Import direction and versioning

`analytics.feasibility_report_contract` stays a leaf package. The policy contract may import the D2
vocabulary and records it evaluates, and **must not** import `analytics.contracts_v14`,
`analytics.evaluation_v14`, `finance/`, `app/`, `api/`, any renderer, persistence or web stack. This
is `CCCDIR` as the programme already pins it, and it keeps the increment independently reversible.

Versioning follows D3A: `schema_id` and `contract_version` mandatory with no defaults, unknown values
fail closed, breaking changes take a new major identity rather than loosening v1.

Lifting D2's hard pin is a **coordinated, separately reviewed change** to `package.py`, not a side
effect of this contract landing. Until that change is independently accepted, the v1 root continues
to accept only `achieved_grade=ungraded`, and this increment ships as a contract with no live effect
on any package — which is the correct fail-closed default.

## 8. Negative controls the implementation must ship

Per `VERIFY-01`, a guard never observed to fail is an unverified claim, so each ships with the
demonstration that it fires:

- a `target_grade` of `lender_grade` with unsatisfied requirements yields `ungraded`, never the
  target;
- a section set achieving `{lender_grade, screening}` aggregates to `screening`, and **no** input
  produces an average;
- a `GradeEvaluation` cannot construct or mutate `achieved_grade`; a `GradeDecision` is required, and
  its absence leaves the package at the D2 pin;
- a software, CI or AI actor as `GradeDecision` authority is refused;
- `lender_grade` is refused as a self-awarded outcome under every input combination;
- each of the eight D1 §7.1 blockers, individually, caps or ungrades a report that would otherwise
  achieve its target — **eight separate controls, not one parameterized pass**;
- an empty applicable-material-section set yields `ungraded`, not the highest grade;
- `ungraded` never sorts above `illustrative` in any comparison the evaluator performs;
- a section with `achieved_grade=not_applicable` but `applicability != not_applicable` is refused,
  and does not escape aggregation;
- a grade profile that **widens** any D1 §7 requirement is refused at construction;
- a materiality determination without a declared rule and scope basis is refused;
- unknown `schema_id`, unknown `contract_version` and unknown discriminators each fail closed;
- generated Draft 2020-12 schemas validate in **both** validation and serialization modes, and
  round-trip ingress equals the original object;
- the evaluator is deterministic under varied `PYTHONHASHSEED` and under varied section insertion
  order, per the D3B veto classes that an ordinary green suite cannot observe;
- **an independent oracle**: a fixture whose expected grade and blocker set were derived from D1 §7
  by a reviewer, not from the evaluator's own output.

## 9. Open questions for the specialists

Three items need a specialist ruling rather than a contract reading:

1. **The materiality rule set.** Which of the twenty sections are material, under what scope
   conditions. D1 §8 marks sections 1, 2, 18, 19 and 20 "Always applicable" and §20 additionally
   "grade-critical"; §8 is "ordinarily material" and §9 "applicable unless a documented scope rule
   establishes otherwise". The remainder needs domain judgement, and it is the single largest open
   input to this increment.
2. **Per-grade evidence and review minima.** D1 §7's table is prose with clear intent; converting
   *"proportionate independent checks"* for `decision_grade` into an enforceable `ReviewStatus` set
   is a judgement the assurance specialist must make and sign.
3. **Whether grade profiles are per-jurisdiction, per-technology, or both.** D1 §7 permits stricter
   technology-, jurisdiction-, transaction- or section-specific profiles. Whether v1 implements one
   dimension or all four is a scope decision, and implementing fewer is the safer default given
   §1.3.

## 10. Programme position

**Upstream:** none. This increment consumes only D2 records that are already merged, so it is
blocked on nothing and runs in parallel with D3B-1 and D3C.

**Downstream:** a package can carry a non-sentinel achieved grade only after (a) this contract is
independently accepted, (b) the D2 hard-pin lift is separately reviewed and merged, and (c) a
verified human signatory records an actual `GradeDecision`. Golden Path 1 depends on all three.

**Not affected by this charter:** `#1110` remains `OPEN` with 0 of 23 controls checked, every Board,
lender, audit and release `HOLD` remains in force, `VERSION` remains `15.4.0`, and no KPI, finance or
evaluation behaviour changes.

## 11. Independent review disposition

**Not yet reviewed.** No domain or assurance disposition exists for this charter. Until both are
recorded against an exact tree, this design is a proposal only, and nothing in it establishes
contract sufficiency, domain sufficiency, achieved grade, package approval or release authority.
