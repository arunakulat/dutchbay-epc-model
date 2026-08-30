# Dolphin 3B-0 policy-root independent review record

**Disposition:** VETO

**Reviewed candidate:** `b2854c0530e4c58413896ac306a41bd624f6d559`

**Candidate tree:** `37e7c7d0e23eb9b221d2d4734fe02335b0c1483c`

**Base:** protected `main` at `9e1c6fae6220551754c23535caeaa86b37422230`

**Draft pull request:** `#1204`

**Authority:** independent domain and assurance dispositions on one immutable candidate; no grade,
release, deployment, lender, Board or `HOLD` authority

## 1. Outcome

The domain and assurance reviewers independently vetoed the exact candidate. The candidate correctly
moved generation and storage electrical/capacity-basis consistency to the public
`V14BindingPolicy` root, and all three originally named contradictions then refused at both the
standalone policy and containing-request roots. It did not close the defect class.

`V14BindingPolicy` is separately versioned, publicly exported and directly constructible. It owns
the complete compatibility-assertion tuple. The reviewed candidate still allowed the standalone
policy to represent several internally contradictory assertion graphs whose contradictions are
visible without an `AssessmentScope`, `BaseScenarioIdentity`, live `ProjectCase`, authored config or
evaluation run. The outer `EvaluationRequest` masked those defects by enforcing policy-owned rules
inside `_require_internal_request_graph`.

Conventional green tests and CI cannot override this semantic veto. Candidate `b2854c0…` must not
merge. Any correction creates a new exact SHA and requires fresh independent domain and assurance
dispositions.

## 2. Exact reviewed object

At review freeze:

- local `HEAD`, remote topic and draft-PR head were all
  `b2854c0530e4c58413896ac306a41bd624f6d559`;
- the sole parent, local `origin/main` and live protected `main` were all
  `9e1c6fae6220551754c23535caeaa86b37422230`;
- the worktree, index and untracked-file set were clean before and after both reviews;
- the topic was zero commits behind and one commit ahead of protected `main`;
- the PR was open, draft, mergeable and blocked from merge; and
- issue `#1110` remained `OPEN` and its Board/lender/release `HOLD` remained unchanged.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `5d82e386c30e4dfb8a2b642471f890322ae44ee79e9e03a466bd1c5cd6b8cf3d` |
| `tests/contracts/test_assessment_scope_contract.py` | `d5998efa761e7bd27f5ac12a09dc2b21a1ee28c0336d9f09101c305532ff45f5` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `79608f454310a9524e4e563b10f0752427feaaa25c68f2f2ebf4371c327093af` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `f863be813d081c30184e77f3449b00da0736a5ef921de274c89128cd4bb8d224` |

The exact candidate diff SHA-256 was
`b2bcd014d39bd3064d8bf67c76a66f4d8061d7c7a0b279338f6f76fcab18293e`.

## 3. Blocking finding — the public policy graph remains open

Both reviewers independently found the same high-severity ownership defect. The following rules
were still implemented only at the outer request root even though every operand resides in
`binding_policy.assertions`:

- unique physical ownership by `TechnologyBindingAssertion.asset_id`;
- generation and storage capacity assertion ownership by a same-asset technology assertion;
- capacity-versus-technology asset class, authored kind and technology-level `base_config_key`;
- one per-technology capacity route for every policy-declared generation technology;
- complete power, energy and duration routes for every policy-declared storage technology; and
- the policy's own price-assertion count.

### 3.1 Five minimal counterexamples

Starting from the accepted request fixture, the domain reviewer made these exact mutations:

| Probe | Mutation | Standalone policy | Full request |
|---|---|---|---|
| Orphan generation capacity | Move `assertion:wind-technology.asset_id` to `asset:other` while capacity remains on `asset:wind-01` | accepted | refused: matching generation technology assertion required |
| Authored target-key drift | Change `assertion:wind-capacity.base_config_key` from `wind` to `wind-other` | accepted | refused: base config keys must agree |
| Authored-kind drift | Change the wind technology assertion and corresponding base authority to `generic_generation` while capacity remains `wind_turbine` | accepted | refused: authored technology kinds must agree |
| Incomplete BESS routes | Add the valid BESS group and remove only `assertion:bess-energy` | accepted | refused: power, energy and duration required |
| Duplicate physical owner | Add valid BESS and move its technology assertion to `asset:wind-01` | accepted | refused: technology asset IDs must be unique |

The assurance reviewer independently reproduced orphan generation capacity, authored-kind drift,
duplicate physical ownership and storage capacity without a same-asset technology assertion.

### 3.2 Further isomorphic escapes

The domain review deliberately searched beyond those examples and found four more standalone
false accepts:

- one `jurisdiction_binding_id` could carry inconsistent jurisdiction identity across authored
  domain assertions;
- one `technology_binding_id` could carry conflicting technology identity or authored kind across
  technology assertions;
- CAPEX and OPEX assertions could carry different `price_basis_id` values; and
- the sole price-basis assertion currency could disagree with the cost assertions.

These analogues make an example-by-example patch unacceptable. The next candidate must close the
complete self-contained policy graph at one owner and leave only genuinely cross-object comparisons
at `EvaluationRequest`.

## 4. Assurance findings

### 4.1 Assertion-order-dependent first error

The reviewed basis checks raised while traversing the caller-supplied assertion tuple. A policy
containing both a generation basis conflict and a storage basis conflict refused in both orders, but
moving the storage group earlier changed the first error from the generation-family message to the
storage-family message.

The same exact JSON remains deterministic and the refusal is stable across `PYTHONHASHSEED`; the
D3B charter's specific enum-order requirement applies to material-disposition mismatch selection.
Nevertheless the remediation record claimed one deterministic error surface. The successor must
collect facts first and validate them in declared family order and sorted identity order, or narrow
that claim explicitly. The preferred correction is deterministic validation because it makes
multi-defect diagnostics reproducible.

### 4.2 Missing isolated electrical-basis regression

The implementation compared both electrical and capacity basis correctly, but the durable tests
varied `capacity_basis` alone or varied both axes together. They did not independently prove that an
electrical-only disagreement triggers refusal.

The assurance reviewer kept both capacity bases at `net`, changed one otherwise valid generation
route from `not_applicable`/`MW` to `ac`/`MWac`, and observed refusal at both roots. The successor
must retain that as a standalone-first, nested-second regression. Storage has no analogous
individually valid alternative electrical basis in D3B v1 because DC storage is already refused by
the individual assertion contract.

## 5. What the candidate proved

The veto does not erase accepted evidence. At exact `b2854c0…`:

- redundant wind net-versus-gross, net totals versus nameplate turbine count, and BESS
  usable-versus-gross contradictions refused at both roots;
- an independent electrical-only generation contradiction refused at both roots;
- coherent five-route nameplate wind, wind-only, solar DC in `MWdc`, solar DC in `MWp`, hybrid and
  storage-only positives accepted at both roots;
- separate wind and solar assets could retain different coherent bases;
- both Draft 2020-12 schema modes were valid and accepted valid serialized policies;
- strict Python ingress, JSON round-trip, extra-field refusal, frozen assignment and tuple-backed
  assertion containment behaved as declared;
- focused D3B-0, D3A, D2 and complete contract suites passed at `136`, `330`, `298` and `792` tests;
- Ruff, formatters, mypy, compile, forbidden-import and excluded-surface checks passed; and
- governed Python `3.12.13` and all `73` canonical GWTF rules were active.

## 6. Required successor shape

The next candidate must invoke one complete policy-internal graph helper from
`V14BindingPolicy`. In deterministic family and identity order it must:

1. close technology assertions by unique physical asset ownership and consistent binding identity;
2. bind every generation/storage capacity assertion to the matching technology owner, class,
   authored kind and technology key;
3. retain one common electrical/capacity basis per physical asset;
4. require policy-complete generation and storage capacity routes;
5. keep repeated jurisdiction bindings identity-consistent across authored domains;
6. make the price assertion singular and reconcile cost price-basis/currency identities to it; and
7. remove duplicate policy-owned implementations from the outer request helper.

The containing request remains responsible for external comparisons only: exact ProjectCase
references; scope/base subject and technology coverage; retained authored domains and authority
routes; scope price axes, valuation date and nominality; and later live-ProjectCase/config values.

Every migrated negative must validate the standalone policy first and the containing request
second. Positives must retain consistent multi-domain jurisdiction routing and legitimate separate
wind, solar and storage assets. The successor must replay the complete local gate and receive fresh
independent dispositions on its new exact SHA.

## 7. Process and authority boundary

The candidate was committed and pushed before independent review, varying from the D3B charter's
preferred precommit review order. The user explicitly required durable origin checkpoints after a
real restart, and the PR remained draft and blocked. Both reviewers accepted this as a disclosed,
bounded `PERSIST-01` measure rather than review authority; neither issued a separate veto for the
ordering.

Neither reviewer changed a file, Git ref, PR, issue, grade, release state or `HOLD`. This record does
not reopen D3A, implement live ProjectCase/config comparison, touch evaluation or finance, assemble
D2/D3C, or confer any lender, Board, release, deployment or issue `#1110` authority.
