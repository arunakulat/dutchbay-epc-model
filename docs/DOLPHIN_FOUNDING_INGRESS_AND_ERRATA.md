# Founding-dolphin ingress brief and governance errata

**Produced at:** `main` = `e90cfc2b6c196f17322bd1a7b52badd89a46d782` (recorded here at base `0a18364`).
**Method:** a `RECRUIT-01` recruited pod of read-only reviewers, each freshly ingressing one founding
dolphin from source with no reliance on memory, handovers or prior assistant statements.
**Yield:** 109 binding constraints and 39 traps across D0, D1 and D3.

**This record confers no authority.** It is not a disposition, not an achieved grade, not package
approval, not assurance acceptance, and not release, lender or Board authority. It lifts no `HOLD`.
Issue `#1110` remains `OPEN` with 0 of 23 controls checked and was not touched.

## 1. Why this exists

`RECRUIT-01` makes review records and dispositions **work product** that must be written to `docs/`
the moment they land, because *"a review chain that lives only in a session's context is lost, and
the pass must be redone."* This programme has already paid that price once: the entire D3B-0 review
chain — four candidate rounds and a three-round veto — was lost with its session.

The pod that produced this brief was itself cut off mid-run by an account session limit. Of six
recruited workers, **three completed and three failed**; a prior fourteen-worker run failed
completely, returning nothing after 542,779 subagent tokens. What survived did so only because the
runner journals each agent's result as it lands. This record is that journal made durable.

**What is therefore NOT covered, declared rather than left silent:**

| Worker | Outcome |
|---|---|
| D0 fresh ingress | completed — 38 constraints, 14 traps |
| D1 fresh ingress | completed — 41 constraints, 12 traps |
| D3 family fresh ingress | completed — 30 constraints, 13 traps |
| **D2 fresh ingress** | **FAILED — session limit. No D2 constraints in this brief.** |
| **D3D domain disposition** | **FAILED — session limit. D3D remains undisposed.** |
| **D3D assurance disposition** | **FAILED — session limit. D3D remains undisposed.** |

The D1 reviewer additionally declared its own scope limit: it read D1's grade clauses and roughly
60% of D3D, but **not** D0, D2 or the D3A/D3B/D3C charters. Every D3D quotation *of D2* — notably the
"removes the prior unsafe half-policy" pin — is therefore an **unverified second-hand claim** in that
reviewer's hands. It also did not open `config/feasibility_sections.yaml`.

## 2. Errata — three defects found in this programme's own governance records

These were found by independent reviewers against work the coordinator produced. All three are
verified below with commands, not accepted on the reviewers' word.

### E-1 — The D3C contracts disposition LAPSED ON ARRIVAL (governance defect, confirmed)

[`DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md`](DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md) binds
`ACCEPTED` to the charter at SHA-256
`031eeb8e1619d1e301f25c5a9e8cdb908adc5e7d34e24c686abd95061c59f74e`. The charter on `main` today
hashes `8a77f424a7ba3ca73ec4b4167e048a0e4a724812a9f666c0232cff4ad6ff4e3d`.

The reviewer inferred the change was the four required amendments being applied. **That inference is
wrong, and the truth is worse.** `#1202` committed the disposition record *and* a 19-line edit to the
very charter it was disposing, in one commit:

```
git show --stat --oneline 9e1c6fa -- docs/
  docs/DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md | 240 +++++++++
  docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md        |  19 +-

git show 9e1c6fa~1:docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md | shasum -a 256
  -> 031eeb8e…f74e     (the parent state the disposition names)
git show 9e1c6fa:docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md   | shasum -a 256
  -> 8a77f424…4e3d     (the merged state)
```

The edit was the `§11` disposition pointer — cosmetically harmless, governance-fatal. `RECRUIT-01`
states that *"a disposition naming no SHA, or a SHA other than the final head, is not a
disposition"* and that *"acceptance never transfers to another implementation, tree or base."* The
disposition named a SHA that its own pull request destroyed at merge.

**The four amendments were never applied.** `grep -n 'engine-less'` still returns line 370's
un-enumerated *"the engine-less six"*, which was amendment `D3C-DOM-02`. So D3C currently has **no
live disposition and no applied amendments**, and any statement that D3C's remaining scope is
unblocked rests on a lapsed record.

**Repair:** a successor record re-binding a disposition to the current charter SHA, after the four
amendments are applied — and the amendments and the disposition must land in **separate** commits.
The immutability convention forbids rewriting the original record; this erratum is the mechanism.

**Generalised rule for this programme:** *never edit the reviewed object in the commit that carries
its disposition.* Freeze, dispose, then amend under a fresh review.

### E-2 — The `RECRUIT-01` base fast-forward carve-out is NOT in the ruleset (memory claim refuted)

Two independent reviewers reached this separately, and the coordinator confirmed it a third time.

Operator memory asserts the canonical CSV was amended on 2026-09-02 to SHA-256
`af932898700dcbc1f5b4daeda7acffa0cbef53989a3a484661a3823b119a68cc`, carrying a three-proof carve-out
(blob-hash identity, bidirectional import isolation, full reviewed-to-updated diff) permitting a
disposition to survive a base fast-forward.

At `e90cfc2` the CSV is 75 lines (header + 74 rules) and hashes
`cbf2c6a709a1be5e2d7aeab53e5f865984a4263104d884821f83da2dccfd01f3`. The single occurrence of
"fast-forward" in the whole file sits inside `MERGE-01`, about synchronizing `main` after a merge —
not inside `RECRUIT-01`. Greps for "blob hash", "import isolation", "LAPSE" and "carve" inside the
`RECRUIT-01` row return nothing.

**Consequence:** at this SHA the *un-amended* `RECRUIT-01` governs, and its unqualified *"acceptance
never transfers to another implementation, tree or base"* applies with no carve-out. **No disposition
in this programme may currently rely on crossing a base fast-forward.** The amendment is open work in
`#1224`, not merged fact.

This is the `RECRUIT-01` ingress rule doing its job: *every prior assistant, handover or memory
statement is a claim to verify, never an authority.*

### E-3 — Four amendment flags against the D3D charter (D1 conformance)

The D1 reviewer read D1's grade clauses against
[`DOLPHIN_3D_GRADE_RELEASE_POLICY_CHARTER.md`](DOLPHIN_3D_GRADE_RELEASE_POLICY_CHARTER.md) and found
that the charter, which claims to *"design no policy"*, in places **strengthens beyond D1's text**.
The direction is conservative in every case — it can only lower a grade — but under D1 §14 an adopted
stricter standard must be *escalated and recorded*, not silently chosen.

**Flag 1 — the universal human-decision gate collapses two of D1's seven orthogonal truths.**
Verified: D1 §4 lists *assessment grade* (truth 6) and *release authority* (truth 7) as separate,
with *"No one field is a proxy for another."* D1's only self-award prohibition is grade-specific —
line 270, *"The platform MUST NOT self-award **this** grade"*, in the `lender_grade` row alone. D3D
generalises that bar to **all four grades**. D1 §7 does permit stricter profiles, but scopes that
permission to *"technology-, jurisdiction-, transaction- or section-specific requirements"* — a
universal structural gate is none of those four. D1 §7 also *defines* achieved grade as a derived
property, and §12.3 item 3 commissions "grade aggregation" as the deliverable. Note too that
§12.1(8) forbids self-**clearing** a hold, review or release — which is not the same act as
self-**computing** a grade.

**Flag 2 — the empty-set rule inverts D1's literal text.** D3D asserts the minimum over an empty set
is `ungraded`. D1 contains no empty-set rule at all, and its literal formulation — *"the highest
grade for which **every** applicable material section satisfies…"* — is **vacuously satisfied by
`lender_grade`** over an empty set. D3D's rule is a safety-positive gap-fill, not an implementation.
The reviewer's stronger, D1-grounded alternative: refuse a materiality determination that
de-materialises any always-applicable section, since D1 §8 marks five always applicable and §6.2
holds that *"materiality may change the depth of treatment, not conceal a risk or legal
requirement."* Recommended **alongside** the empty-set control, not instead of it.

**Flag 3 — the "minimum" quotation drops its antecedent.** D3D quotes *"the package grade is the
minimum across applicable material sections"* without D1's *"If sections achieve different
grades, …"*. The outcome is unchanged, but the two computations are genuinely different: the §7
primary definition is a **conjunctive satisfaction test** against a profile, while "minimum of
per-section grades" is an **order statistic** over already-assigned grades. They coincide only if
section grades were themselves assigned by the same conjunctive test. Implement the conjunctive
definition as primary, the minimum as corollary, with a property test proving they agree.

**Flag 4 — "eight separate controls" is a floor, not the requirement.** The blocker count of eight is
verified against D1 §7.1. But blocker 2 carries four independent sub-conditions
(failed / deferred / unsupported / lacks required input-dependency), blocker 3 carries three, and
blocker 4 carries two. Eight passing controls can leave sub-conditions never observed to fire, which
`VERIFY-01` treats as unverified. Enumerate the discriminated union at **sub-condition granularity**
(≥15 observed firings).

**Also recorded, non-amendment:** D3D §9 has a notation collision — it uses `§8`, `§9`, `§20` to mean
both D1 *document* sections and *manifest rows* in one paragraph, and D1 document §9 is "Harness
requirements", which says nothing about scope rules. Content verified correct; the notation is
ambiguous in exactly the paragraph a domain specialist is asked to rule on. Use "manifest row N" for
rows and reserve `§` for document sections.

**Two further D1-conformance corrections for the D3D implementation:**

- **Self-clearing has four named actors, not one.** D1 §12.1(8) names the producing process, CI, the
  **model owner** and an **evidence score**. "Model owner" is a *human* role, so a signatory check
  that only asks "is a human / not an AI" accepts the model owner and does nothing about an evidence
  score. Enumerate all four and demonstrate each firing.
- **`ungraded` must not be orderable at all.** D3D tests that it never sorts above `illustrative`;
  the D1-faithful position is that it is not in the ordering — a `min()` over a lattice containing it
  is a category error. Prefer a distinct type over a lowest enum member.

## 3. The founding constraint brief

109 constraints were extracted. The load-bearing ones for any successor contract:

### From D0 — the controlled human projection (38 constraints)

D0 is **subordinate and non-generative**: *"No new external proposition is introduced here."* It
governs the *form* in which a human reader is told about grade, materiality, applicability and
release; it creates none of those states.

- **Six states stay separate and separately expressible** — applicability, production, evidence,
  review, achieved-grade, release. The most common collapse is treating "not applicable" as a
  production or evidence outcome.
- **Absence never removes a required subsection.** *"An author must never delete a required
  subsection merely because information is unavailable."* The lawful response is a disposition
  carrying cause, consequence, owner and remedy.
- **Presentation is a disclosure surface.** *"The cover must identify the report without making a
  grade or release claim by design alone."* Run posture may never be rendered as, or adjacent to and
  confusable with, achieved grade.
- **Grade aggregates downward** to the weakest material dependency; no downstream completeness raises
  it.
- **`HOLD` is the default**, movable only by a named human authority with a hash-bound decision over
  the exact package and artifacts. Nothing computational touches it.
- **Forbidden reliance language** is an enumerated list: prediction of lender acceptance,
  self-certification of compliance/connection/resource conditions, "lender model" inferred from run
  posture, promotion of screening or synthetic output by detail or trial count, generic concealing
  disclaimers, false precision, anthropomorphism, responsibility-hiding passives.
- **D0 carries no materiality threshold.** "Materiality" occurs 7 times in 2,092 lines and every one
  requires it to be *stated, recorded or declared* — never defines it. Mining D0 for a threshold is a
  trap.

### From D1 — the normative contract (41 constraints)

- **Four grades**, ascending: `illustrative`, `screening`, `decision_grade`, `lender_grade`.
- **`ungraded` is a required sentinel, not a fifth grade** — never orderable or sortable as one.
- **`target_grade` MUST NOT be copied into `achieved_grade`.**
- **`not_applicable` is section-level only** and needs *both* `applicability=not_applicable` **and**
  `production_status=not_required_by_scope`. Report-level achieved grade is never `not_applicable`.
- **Aggregation** is the highest grade every applicable material section satisfies on production,
  evidence *and* review — *"never an average"* — with the minimum rule as the differing-grades
  corollary, applied *after* all report-level blockers.
- **Eight report-level blockers** in §7.1, several compound (see E-3 flag 4).
- **Reading rule, easily missed:** D1 §1 states that unless marked CURRENT, every normative
  requirement is **FUTURE**. None of §7, §7.1, §8, §8.1, §8.2 or §12.1 carries a CURRENT marking, so
  these clauses describe the target contract, **not present behaviour**. No document may cite them as
  evidence the platform does any of this today.

### From the D3 family — confirmed defect classes (30 constraints)

The nine D3A `DOM` classes remain live for every successor, and two meta-lessons dominate:

- **Green counts are not coverage, and this programme has four separate proofs.** D3A was domain
  rejected with 81 passing tests. D3B-0's reviewers vetoed three successive candidates at 81, then
  116, then 130 tests. D3B-0 shipped with 136 green and the second pass still found `D3B-2P-01`.
  D3C-1b's candidates were rejected with green receipts that *"did not override the semantic"* defect.
- **A closed defect reappears one layer up with a different field.** `D3A-DOM-03` — an arbitrary
  2099-12-31 basis accepted once its paired date was made to match — was closed in D3A and reproduced
  *verbatim in shape* as `D3B-2P-01`. **Probe every new contract against the shape of each prior
  finding, not its original field names.**
- **D3A needed six domain rounds and acceptance still did not stick** — rejected four times, accepted,
  then rejected again on a successor over a narrow vocabulary omission (`MWp` missing from
  `electrical_collection`). Budget for multiple rounds.
- **Probe for false rejects, not only false accepts.** Two of D3A's nine findings caught the contract
  wrongly *rejecting* ordinary valid projects. A suite of only negative controls passes a contract
  that cannot express reality.
- **Field declarations are not the contract; validators are.** A reviewer was wrong in both
  directions on this: `unit: UnitToken | None = None` *is* closed by a validator, while
  `precision: NonNegativeInt | None = None` really is open. Grep the validators, then construct the
  object.
- **Same-agent review is not independence**, and two records in this family say so about themselves.
  Neither discharges the two-reviewer requirement `RECRUIT-01` imposes on code, contract and finance
  work.

## 4. Open items this brief does not close

1. **D3D has no disposition.** Both reviewers failed on the session limit. Its §11 still records that
   none exists, and the four E-3 flags now stand against it unanswered.
2. **D3C has no live disposition and no applied amendments** (E-1).
3. **D2 was never freshly ingressed** in this run, so no D2 constraints appear above.
4. **`D3B-2P-01` remains open**, re-verified at `e90cfc2`: `assessment_scope.py` carries bare `date`
   fields with no validator touching them. A one-directional downstream backstop did land at
   `assembly_authority.py:791`, refusing an `evidence_cutoff` later than the engine run — but it lives
   in the consuming layer, not the declaring one, and `valuation_date` has no absolute bound anywhere.
5. **`D3C-ASR-02` remains open**: `normalize_kpi_dict` still logs the drop at `debug` while its
   docstring claims warnings.
