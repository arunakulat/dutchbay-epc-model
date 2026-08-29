# Dolphin 2 independent specialist review record

**Record status:** blocking review checkpoint under PERSIST-01
**Reviewed surface:** uncommitted `codex/feasibility-report-machine-contract` tree based on
`22d342ac32b7921de9b5cde0156f483fecf26294`
**Review roles:** renewable-project domain specialist and audit/assurance specialist
**Important boundary:** these are specialist AI reviews. They are not statutory assurance, an
external audit opinion, lender acceptance, a verified human professional engagement, or package
release authority.

## 1. Protected state at review

- The reviewed worktree was `/Users/aruna/Downloads/dutchbay-wt-feasibility-report-machine-contract`.
- The implementation was uncommitted and had not been pushed or submitted as a pull request.
- The reviewers made no file, Git, GitHub, audit-ledger, issue, or release-state mutation.
- Live issue `#1110` was independently re-queried as `OPEN`, with 0 checked and 23 unchecked gates.
- P01/P02/P03, F5-01/F5-02, resource/grid evidence conditions and package release remained `HOLD`.
- The intended focused suite passed 123 tests and `tests/contracts` passed 63 tests, each with one
  non-failing Hypothesis collection warning. Ruff, format, mypy and `git diff --check` passed. The
  vetoes therefore record missing semantic oracles, not a conventional red test failure.

The assurance reviewer recorded these pre-remediation fingerprints:

- tracked binary diff stream: `628c84817ecfbc6e1d6a122884520802c15b6c0cffde9533f91e63990d965286`;
- `package.py`: `d577cd1a2303adac20cd3653ee1a0ac048f15b43e70e434114e07b87c9653426`;
- `records.py`: `dc414992184932cc6ba15968972ef57adae22e032c64091929a1ecd97a37d32c`;
- `vocabulary.py`: `2871746384ad0c6c1416e7060fcddcfb1c5c308ad5ea65ac161c3108850dc2d0`;
- contract tests: `d18dd478f0bb6b3d7e7bf009b89fa6572c8cdcdcdaa50ea2019a0537262ce412`;
  and
- successor 6: `f02119ed53ad0f9615592d4975781c930c3795e03c5eff7320b173153e7950aa`.

## 2. Domain disposition

**DOMAIN VETO.** The reviewer accepted the additive architecture, exact YAML-resolver taxonomy
parity, frozen/discriminated models, absence of finance or adapter changes, and the forward delivery
sightline. The veto applied because the package admitted feasibility-false combinations that could
be serialized as valid v1 state.

Blocking counterexamples accepted by the pre-remediation tree were:

1. a screening-target, ungraded, missing-input/missing-evidence/unreviewed section claiming
   `lender_grade` without a grade decision and above screening-only pack ceilings;
2. a lender-grade package despite material unproduced sections, missing evidence/review, held
   release, evidence-free decision and screening-only pack ceilings;
3. an ungraded package whose `grade_decision_id` named an unrelated scope decision;
4. Claim A citing Evidence E while Evidence E declared Claim B;
5. an `ASSURED` pack backed only by a pending internal review and an evidence-free assurance
   decision;
6. an unknown technology made `SUPPORTED` by relabelling a source-free, validation-free pack;
7. Fictionland carrying a 0.30 default from a source whose declared jurisdiction was Sri Lanka;
8. an applicable section with no jurisdiction or technology pack links;
9. a `PASSED` reconciliation with no sections or operands;
10. a resolved derived input with no derivation/source and no reciprocal section link; and
11. a numeric canonical value with no unit.

The domain reviewer also required the current meaning of `technology_ids` to be stated honestly as
technology-type identifiers; project asset instances, storage/hybrid relationships and shared-asset
allocation belong in the additive Dolphin 3 `ProjectCase` facade and must not be claimed as present
D2 capability.

## 3. Assurance disposition

**ASSURANCE VETO.** Eleven hostile packages were independently sent through
`FeasibilityReportPackage.model_validate()` and were all accepted before remediation:

| ID | Accepted-invalid package |
|---|---|
| A | Section `lender_grade` without grade authority, production, evidence or review. |
| B | Ungraded package using a scope decision as `grade_decision_id`. |
| C | Claim/evidence cross-binding contradiction. |
| D | `ASSURED` pack with pending internal review and a denial/evidence-free assurance decision. |
| E | N/A section retaining current canonical output owned by another section. |
| F | Future-retrieved, expired, wrong-scope source marked sufficient. |
| G | Unrelated review marking a section independently accepted. |
| H | Weak self-declared human plus denial/evidence-free release decision authorizing the package. |
| I | Nominal independent review whose signed review decision was authorized by AI. |
| J | Performed human `APPROVED` responsibility without a decision reference. |
| K | Restricted/no-publication evidence represented in a full public artifact without disclosure or redaction control. |

The direct hostile receipt was:

```text
A_section_lender_grade_without_grade_decision: ACCEPTED
B_ungraded_with_unrelated_scope_grade_decision: ACCEPTED
C_claim_evidence_bidirectionality_broken: ACCEPTED
D_assured_pack_pending_internal_review_denial_decision: ACCEPTED
E_na_section_with_stale_cross_section_current_output: ACCEPTED
F_future_expired_wrong_scope_source_marked_sufficient: ACCEPTED
G_unrelated_review_marks_section_independently_accepted: ACCEPTED
H_denial_text_and_weak_actor_authorize_held_package: ACCEPTED
I_independent_acceptance_signed_by_ai: ACCEPTED
J_human_approved_without_decision_reference: ACCEPTED
K_restricted_evidence_in_declared_full_public_artifact: ACCEPTED
```

The assurance reviewer also found that the original successor 6 was descriptive rather than an
executable fresh-task bootstrap. It did not prove the next task's governed Python, import binding,
clean exact main, worktree ownership, live `#1110` HOLD, merged D0/D1/D2 authorities or exact D2
regressions.

## 4. Controlling remediation boundary

The vetoes are cleared only by an exact-tree independent retest. Green implementer tests alone are
not sufficient. The remediation must:

- keep achieved grade sentinel-only in Dolphin 2 (`ungraded` package; `ungraded` or N/A sections),
  because centralized grade profiles, blockers and aggregation remain Dolphin 3;
- remove selective target-grade logic that could look like a partial D3 policy;
- add typed positive/negative decision outcomes and exact subject bindings;
- enforce reciprocal claim/evidence, section/output, section/input, derivation, pack/capability,
  review and decision relationships;
- make N/A incapable of retaining current/stale output and bind it to an exact positive scope
  decision;
- implement the D1 structural meaning of `supported` and `assured` packs, including scope, version,
  evidence, review independence, findings, decision outcome, grade and effective period;
- enforce intrinsic source/evidence cutoff, expiry, project, jurisdiction and technology consistency;
- require provenance for derived inputs and units for numeric canonical values;
- refuse empty passed reconciliations;
- bind performed human responsibility to an organized human and a positive exact decision;
- refuse unresolved public/restricted-rights disclosure contradictions;
- preserve every live audit and release `HOLD`; and
- add each admitted counterexample as a durable negative control that fails for its intended reason.

This repair does not authorize grade aggregation, orchestration, finance changes, adapter migration,
canonical hashing, pack approval, audit-gate movement or package release.

## 5. Required rereview receipt

Before delivery, the remediated exact tree requires:

1. the expanded focused tests and complete `tests/contracts` suite;
2. Ruff check and format, mypy, JSON Schema/round-trip checks and `git diff --check`;
3. independent domain re-execution of the domain counterexamples;
4. independent assurance re-execution of A-K and the authority/privacy variants;
5. correction of the charter, changelog and successor claims; and
6. exact-head protected CI before merge.

Independent acceptance of the D2 code means only conformance to this narrow machine-contract scope.
It cannot lift or replace any current project, evidence, audit, lender, Board or release authority.
