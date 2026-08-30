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

## 8. Successor review — inverse semantic aliases remain open

**Disposition:** VETO

**Reviewed successor:** `f6412fc2bfe271644ca262b731681faba751551f`

**Successor tree:** `356d30f6d50c3d1136d4cd253913579e643529c3`

Both independent reviewers verified that this successor closed every preserved `b2854c0…`
counterexample, moved the complete previously known policy-only rules to one helper, canonicalized
validation order and removed their duplicate outer-request implementations. Both reviewers then
independently constructed two inverse-identity aliases that the standalone policy still accepted.
Those false accepts keep the same public-root ownership defect open, so conventional green tests
and CI cannot authorize merge.

### 8.1 Jurisdiction semantic-identity alias

Starting from the accepted fixture, the reviewers copied the site-jurisdiction assertion and gave
the copy a new assertion ID, a new `jurisdiction_binding_id` and a distinct valid authored domain,
while retaining the same `(jurisdiction_code, subject)` identity `(FIC, site)`.

Observed result:

| Root | Result |
|---|---|
| Standalone `V14BindingPolicy` | **accepted** |
| Containing `EvaluationRequest` | refused: assertion did not match an exact scoped/base subject |
| Analogous `AssessmentScope` | refused: duplicate jurisdiction subject scope |
| Analogous D3A `ProjectCase` | refused: ambiguous duplicate jurisdiction subject binding |

The successor correctly enforced one identity for each repeated binding ID, but omitted the inverse
rule: one semantic `(jurisdiction_code, subject)` identity must map to one binding ID. The existing
positive remains valid and must be retained: one binding ID may route consistently through multiple
authored domains.

### 8.2 Technology semantic-identity alias

The reviewers added a complete second wind group with a new physical asset ID, binding ID,
technology key and coherent capacity route, but reused the same semantic identity
`(technology_id=wind, asset_class=generation)`.

Observed result:

| Root | Result |
|---|---|
| Standalone `V14BindingPolicy` | **accepted** |
| Containing `EvaluationRequest` | refused: assertion did not match an exact scoped/base technology |
| Analogous `AssessmentScope` | refused: duplicate technology scope |
| Analogous D3A `ProjectCase` binding register | refused: ambiguous duplicate technology contract binding |

The successor required unique physical asset IDs and unique binding IDs but omitted the inverse
semantic rule: one `(technology_id, asset_class)` identity must map to one binding ID.

### 8.3 Exact successor receipt

At review close:

- local `HEAD`, remote topic and PR head were
  `f6412fc2bfe271644ca262b731681faba751551f`;
- protected `main` and the PR base were
  `9e1c6fae6220551754c23535caeaa86b37422230`;
- the worktree was clean and the PR remained open, draft, mergeable and blocked; and
- issue `#1110` remained `OPEN` with its `HOLD` unchanged.

Successor fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `b8c767ac2439b87d810fe91afc7b8b3c3bee40c9c8e742ff1cdd4c05c1842b8e` |
| `tests/contracts/test_assessment_scope_contract.py` | `5ef2ebac6d41d454f6b7e42d6a25bc02e92de10bcfb14450995b76640d24fea6` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `55483b48252e9281bfe0c2825cad11819015b9e68f07fc51c56daada75659776` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `b72426b165ddee12bdd0494ea6df8a489959acecd540ffcbc8f1387a7975e1fc` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `530f738285d7aa20581fb22e2ea2095d27cd34854cf03f1ced25ba8772036773` |

Independent checks included governed Python `3.12.13`, all `73` active GWTF rules, `150` focused
D3B-0 tests, `330` D3A tests, `298` D2 tests, `806` complete contract tests, both schema modes,
strict/frozen/round-trip controls, ordering across shuffled inputs and multiple hash seeds, Ruff,
formatting, mypy, import/boundary checks and an empty excluded-surface diff. Every preserved first
VETO negative refused at both roots; wind, solar, hybrid, storage-only, coherent nameplate and
consistent cross-domain-jurisdiction positives accepted. The two inverse aliases control the VETO
regardless.

### 8.4 Required one-to-one mapping correction

The next successor must add the reverse sides of the binding maps in the same canonical policy-root
helper:

1. `(jurisdiction_code, subject) -> jurisdiction_binding_id`, allowing repeated routes only when
   both semantic identity and binding ID remain identical; and
2. `(technology_id, asset_class) -> technology_binding_id`, rejecting a second binding ID for the
   same semantic technology identity.

The new negative controls must validate the standalone policy first and the request second. The
consistent same-binding/multiple-domain jurisdiction positive and distinct technology identities
must remain accepted. Reordering the assertion tuple must not change the first error.

### 8.5 Explicit D3B-v1 multi-asset limitation

The domain reviewer separately proved that D3A may contain multiple physical assets which reuse one
registered technology binding. The successor's unique `technology_binding_id` rule is therefore a
stricter D3B-v1 execution-policy limitation, not a general D3A invariant. The current authored-target
model cannot safely express multiple physical assets under one binding without a larger aggregation
and target-ownership design.

The bounded v1 position is fail-closed: one policy-owned physical asset per technology binding, and
D3B-1 must refuse a live ProjectCase that reuses one binding across multiple physical assets. This
limitation must be stated rather than attributed to D3A or silently widened. Supporting the broader
D3A shape belongs in a separate design dolphin.

Candidate `f6412fc…` must remain unmerged. The correction creates another exact SHA and requires new
domain and assurance dispositions. This VETO changes no grade, release, deployment, lender, Board,
issue or `HOLD` state.

## 9. Successor review — jurisdiction subject/domain admissibility remains open

**Controlling disposition:** VETO

**Reviewed implementation:** `d164781354904386e81622af28462f6121fd5f1c`

**Reviewed tree:** `9a03f56daa765a848623ea6d476dd73757f0f1bd`

The independent assurance reviewer accepted this exact candidate after replaying the preserved
technology, jurisdiction-identity, capacity, route, cost/price, ordering, schema and regression
controls. The independent domain reviewer verified those same corrections, then constructed a new
standalone false accept against the module's closed jurisdiction subject/domain matrix. The domain
VETO controls: one acceptance within its tested scope cannot override a constructive semantic
counterexample outside that scope.

### 9.1 What `d164781…` closed

Both prior inverse aliases now refuse at the standalone policy first and the containing request
second:

- two jurisdiction binding IDs cannot claim one exact `(jurisdiction_code, subject)` identity; and
- two technology binding IDs cannot claim one `(technology_id, asset_class)` identity.

Distinct wind and solar identities in the same `generation` asset class remain valid, as does one
jurisdiction binding routed consistently through multiple admissible authored domains. Assertion
reordering retained the same first-error family. The D3B-v1 one-physical-asset-per-technology-
binding restriction is also correctly disclosed as a fail-closed limitation which is stricter than
valid D3A topology, not as a D3A invariant.

### 9.2 Blocking domain finding

`JurisdictionSubjectAssertion` carries both `subject` and `base_domain`, but accepted pairs which
the same module's immutable `_DOMAIN_ALLOWED_SUBJECTS` matrix and
`_DOMAINS_WITHOUT_JURISDICTION_ROUTE` set declare impossible. The containing request later refused
only because no valid base could retain such a route.

The domain reviewer exercised these exact mutations:

| Mutation | Standalone assertion | Standalone policy | Request |
|---|---|---|---|
| `tax` subject targeting `project_resource` | accepted | accepted | refused: no retained authority route |
| `site` subject targeting `tax_statutory` | accepted | accepted | refused: no retained authority route |
| `site` subject targeting project-global `run_posture` | accepted | accepted | refused: no retained authority route |
| `tax` subject targeting project-global `scenario_identity` | accepted | accepted | refused: no retained authority route |

These are not merely absent routes in the selected base. A matching `site -> tax_statutory` base
route was independently refused with `jurisdiction subject site cannot govern tax_statutory`; a
matching `site -> run_posture` route was refused because `run_posture` routes must be
project-global. No valid `BaseScenarioIdentity` can therefore satisfy the standalone policies that
were accepted.

All operands needed for the static decision already exist at the assertion root. CESSPIT requires
the refusal there; CCCDIR requires reuse of the existing closed matrix; CASPER requires the public
standalone contract to fail predictably. `EvaluationRequest` should continue to own only the
external question of whether an intrinsically valid assertion's exact authority route is retained
by the selected base.

### 9.3 Independent assurance acceptance preserved

The assurance reviewer found no blocking defect within its probe set and issued an explicit
`ACCEPT` bound only to `d164781…`. That review independently obtained:

- `153` focused D3B-0, `809` complete-contract, `330` D3A and `298` D2 passing tests;
- stable first-error families across 32 permutations per hostile family and 16 hash seeds;
- passing Draft 2020-12, strict/frozen, JSON round-trip, export, import, Ruff, format, mypy and
  excluded-surface controls; and
- green exact-head required receipts, fastlane and smoke checks.

It also replayed 21 named policy-graph negatives at both roots and independently proved the
explicit D3B-v1 shared-binding limitation. This is valid evidence for those controls, but it did not
exercise the subject/domain admissibility matrix and expressly did not replace the domain
disposition.

### 9.4 Exact review receipt

At review freeze:

- local `HEAD`, remote topic and draft-PR head were
  `d164781354904386e81622af28462f6121fd5f1c`;
- local and live protected `main` were
  `9e1c6fae6220551754c23535caeaa86b37422230`;
- the candidate was zero commits behind and five commits ahead of that base;
- the worktree and index remained clean throughout both reviews;
- the PR was open, draft, mergeable and blocked; and
- issue `#1110` and its Board/lender/release `HOLD` were unchanged.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `61cc2cc5c647207bf373b1ba377c230bf11aa02ce2182b6f26ead6dcb05e9e6f` |
| `tests/contracts/test_assessment_scope_contract.py` | `37f4ee05466e01483cdcc8637dcfac8b1ae9467ee4d59d5670270c07304b2fc9` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `6813018b3371f38b8696efb4b0c08938269e5bb54459c92329a8dbc6bffc59e4` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `00d0eaa9c4af7b08861398beb9be97d00d21ae2273769b6de5b42816b1a37364` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `b01facecba02a177b68bebe135fee7d3647c261d67e8af7221c0c0407832b3c6` |

The exact base-to-candidate binary diff SHA-256 was
`a8ee7447dc07d8a3da0d844a82e319e363660a66dba610b965f58775e741a63f`.

### 9.5 Required bounded correction

The next successor must centralize one static subject/domain admissibility helper and call it from:

1. `JurisdictionSubjectAssertion`, the lowest root owning both operands; and
2. the existing `BaseScenarioIdentity` authority-route validation.

It must reject every project-global-domain target and every pair excluded from the complete closed
matrix. Durable tests must parameterize the full matrix and validate, in order, the standalone
assertion, standalone policy and containing request. Valid site/project-resource,
site/project-location, tax/tax-statutory and same-binding/multiple-admissible-domain positives must
remain accepted.

Candidate `d164781…` must remain unmerged. Neither the VETO, the assurance acceptance, the green CI
checks nor a later correction confers grade, evidence sufficiency, audit, lender, Board, release,
deployment or `HOLD` authority.

## 10. Successor review — child-validation order bypasses canonical policy order

**Controlling disposition:** VETO

**Reviewed implementation:** `d7eb1358f767e9101f83f3c2ffded08e5e9b41ce`

**Reviewed tree:** `79041c0cafefad8970dcc46cafdc9dd4a88c5095`

The independent domain reviewer issued `ACCEPT`: an independently hardcoded 15-by-9 oracle proved
that all 28 admissible jurisdiction subject/domain pairs accepted at assertion, base, policy and
fully reconciled request roots, while all 107 impossible pairs refused at all four roots. Every
prior VETO counterexample and required positive was also replayed successfully.

The independent assurance reviewer accepted the matrix and ownership correction, then found a
canonical-error regression. Because Pydantic validates discriminated-union children in caller tuple
order, two invalid `JurisdictionSubjectAssertion` children fail before the policy's canonical sorter
can run. The assurance VETO controls.

### 10.1 Minimal simultaneous-error counterexample

Starting from the accepted request, the assurance reviewer made only these two changes:

```text
assertion:site-jurisdiction.base_domain = tax_statutory
assertion:tax-jurisdiction.base_domain  = project_resource
```

Both relations are intrinsically impossible. The complete error set was stable, but first error and
location followed caller order:

| Assertion tuple | First standalone-policy error |
|---|---|
| authored | `assertions[2]: jurisdiction subject site cannot govern tax_statutory` |
| reversed | `assertions[6]: jurisdiction subject tax cannot govern project_resource` |

The containing request showed the same reversal below `binding_policy.assertions`. Across 32
shuffles the first message had two possible values; one exact payload remained stable across 16
hash seeds. This is caller-order dependence, not hash nondeterminism.

The earlier successor correctly canonicalized policy-graph errors by material-category declaration
order and assertion ID. The new assertion-level validator necessarily runs before that after-model
graph helper, so the 107 single-defect matrix tests could not expose the simultaneous-child case.

### 10.2 Accepted evidence preserved

The VETO does not reopen the subject/domain matrix or its ownership:

- the shared static helper remains the single semantic implementation;
- `JurisdictionSubjectAssertion` is the lowest public owner of its two operands;
- `BaseScenarioIdentity` reuses the helper for selected authority routes;
- every project-global and matrix-excluded pair refuses at all requested roots;
- valid-but-unretained `site -> project_lifecycle_timeline` remains accepted by assertion/policy and
  refused only by the request's external route-existence check;
- the inverse binding corrections and all prior basis/ownership/route/cost-price negatives remain
  closed; and
- the D3B-v1 shared-technology-binding limitation remains explicit and accurately distinguished
  from valid D3A topology.

The domain review obtained `163` targeted, `288` focused, `944` complete-contract, `330` D3A and
`298` D2 passing tests. The assurance review independently confirmed the same complete gates,
`94.56%` package coverage, `96.70%` modified-module coverage, both Draft schemas, strict/frozen and
round-trip controls, static/type/import/excluded-surface gates, and green exact-head required CI.

### 10.3 Required bounded correction

The next successor must retain the standalone assertion validator and must not reimplement the
subject/domain matrix in a raw parent preflight. Instead, collection-level validation must delegate
each child to the existing compatibility-assertion type in canonical
`(ProjectCaseMaterialCategory declaration order, assertion_id)` order, while successful validation
must preserve and serialize the original authored assertion tuple unchanged.

Durable controls must exercise authored, reversed, rotated and shuffled versions of the two-error
payload at both policy and request roots, repeat under multiple hash seeds, and assert one stable
first message/location family. A valid policy must prove exact authored-order round trip.

### 10.4 Exact review receipt

At review close, local `HEAD`, remote topic and draft-PR head were all `d7eb135…`; local/live
protected `main` and the PR base were `9e1c6fae6220551754c23535caeaa86b37422230`;
the topic was zero behind and seven commits ahead; the worktree was clean; the PR was open, draft,
mergeable and blocked; and required receipts, fastlane and smoke checks were green. Issue `#1110`
and its `HOLD` were unchanged.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `496ac4c0d867bc47600ed256f730aca3a45bfceff5c61d0aa4b94fedf465f7fa` |
| `tests/contracts/test_assessment_scope_contract.py` | `b5734ff8681177310f3b4b03d8de65a87c881aa49bdbcfbd78dae8f6ba5071b4` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `897c92c61d76050e1a4192ec2a864307b28d6898d42aa7d2b398ba4c31590527` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `d77109a76e1820e5beeea4be7debaede7daba99fbf1ecac56ab1fbc21c220a67` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `f6dca926ce325c05eae03883f31c54175880af373253fd9b201ab7337405e7cf` |

The protected-base-to-candidate binary diff SHA-256 was
`0067df8900eff23914e76fa1e4b6d392d48e5c2146164dd65afaa22805cbf197`.

Candidate `d7eb135…` must remain unmerged. The domain acceptance remains valid for the matrix and
ownership probes it covered; the assurance VETO remains controlling for delivery. Neither
disposition changes grade, evidence, lender, Board, release, deployment, issue or `HOLD` authority.

## 11. Successor review — duplicate assertion IDs collide on the canonical key

**Controlling disposition:** VETO

**Reviewed implementation:** `2b97743db4459116f5ae118a95ce09c4528dcfe3`

**Reviewed tree:** `35216e4172f23c8285cd692e56b59f5bc85d6943`

The independent domain reviewer issued `ACCEPT` for the bounded semantic scope. A hardcoded oracle
proved all 28 admissible and 107 impossible jurisdiction subject/domain pairs at the assertion,
base, policy and request roots; 75 distinct valid and invalid caller orders preserved the accepted
matrix, external route boundary, successful wire order and byte-stable round trip. No earlier
policy-ownership counterexample reopened.

The independent assurance reviewer proved that the correction closed Section 10's named
distinct-ID counterexample across 76 orders, JSON and normalized Python modes, both public roots,
ten hash-seed processes and 152 valid round trips. The reviewer then found a narrower collision in
the canonical raw key. The assurance VETO controls.

### 11.1 Minimal canonical-key collision

Starting from the accepted fixture, the reviewer made only three content changes:

```text
site.base_domain = tax_statutory
tax.base_domain = project_resource
tax.assertion_id = site.assertion_id
```

Exchanging only the two jurisdiction children changed the complete error order:

| Caller order | Canonical index 2 | Canonical index 3 |
|---|---|---|
| site, tax | `site cannot govern tax_statutory` | `tax cannot govern project_resource` |
| tax, site | `tax cannot govern project_resource` | `site cannot govern tax_statutory` |

The containing request showed the same reversal below `binding_policy.assertions`. JSON and
normalized strict-Python ingress reproduced it at both roots, and eight independent hash-seed
processes proved that each caller order was internally stable but the two orders were unequal.

The collection key was `(material-category declaration order, assertion_id, kind,
authored_index)`. Once category, ID and kind collide, authored index is still the caller's position.
The later unique-`assertion_id` check cannot be treated as a precondition because child semantic
validation fails before the after-model policy validator runs. Both payloads refuse, but the first
message and its claimed canonical index remain caller-controlled.

### 11.2 Accepted evidence preserved

This VETO does not reopen the complete matrix, semantic ownership or the original correction:

- `JurisdictionSubjectAssertion` remains the lowest public owner of its subject/domain relation;
- the collection validator delegates through the existing discriminated `CompatibilityAssertion`
  type in JSON and Python modes and does not duplicate the matrix;
- all prior basis, inverse-identity, route-completeness, class/key/kind, cost/price and external-route
  controls remain closed;
- strict Python list/non-collection/malformed-child refusals remain intact;
- successful policies preserve exact authored tuple and serialization order; and
- D3B's shared-technology-binding restriction remains accurately described as a v1 execution
  limitation, not a D3A invariant.

The domain review obtained `166` targeted, `291` focused, `947` complete-contract, `330` D3A and
`298` D2 passing tests. Both reviews confirmed the governed environment, 73 active rules, schema,
round-trip, import, static, formatting, typing, excluded-surface and diff controls. Assurance
confirmed `94.63%` package branch coverage and `96.88%` modified-module coverage. Required receipts,
fastlane and smoke checks passed on the exact reviewed head, but neither CI nor the domain ACCEPT
overrides the assurance VETO.

### 11.3 Required bounded correction

The next successor must make child diagnostic ordering total when the declared category, assertion
ID and kind collide. Authored index may remain only as the restoration address after successful
validation; it must not be the semantic error-order tie-breaker.

The correction must continue to validate each child through `CompatibilityAssertion`. A bounded
implementation may collect independent child outcomes, then sort the bundles by the declared key
plus a deterministic validation-outcome signature: validated children can use their deterministic
serialized model representation, while invalid children can use a bounded tuple of error type,
inner location and message. It must not duplicate the subject/domain matrix.

Durable controls must retain the distinct-ID permutation/hash-seed corpus and add this duplicate-ID
simultaneous-defect case in both orders, at both public roots, in JSON and normalized Python modes,
with complete error-set equality across multiple fresh hash-seed processes. Successful authored
order and strict ingress behavior must remain unchanged.

### 11.4 Exact review receipt

At review close, local `HEAD`, upstream, live remote topic and draft-PR head were all `2b97743…`;
the tree was `35216e4172f23c8285cd692e56b59f5bc85d6943`; protected/live `origin/main` and the
PR base were `9e1c6fae6220551754c23535caeaa86b37422230`; the topic was zero behind and nine
commits ahead; the worktree was clean; and the PR was open, draft, mergeable and blocked. Issue
`#1110` and its `HOLD` were unchanged.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `cd231135d4b818e5e70aa787ef2021531d316f11abdf2dc1ee3e2f84edfd928b` |
| `tests/contracts/test_assessment_scope_contract.py` | `ad452f5faf383d1a492ea5afa14064741063f39ec185e9dd1a36993e43222cf1` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `dec143e5355c70210bda3a4a4e07fbfa9355588a24d0fa50ab0b7cda34408a78` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `d1b762c6cafe65368e0e80e4dc974781f598bc44eda7208df35ad5562804a241` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `bbf6aa2bfa16de7cb220d0a2909264e43dc8fb3506577e966a56d39e69dcbfa6` |

The protected-base-to-candidate binary diff SHA-256 was
`c10472a76e89069230c467aa666add68746e626a448b9a050deecb0d41884028`.

Candidate `2b97743…` must remain unmerged. Domain acceptance remains valid for its bounded semantic
scope; assurance VETO remains controlling for delivery. Neither result changes grade, evidence,
lender, Board, release, deployment, issue or `HOLD` authority.

## 12. Successor review — the projected outcome key omits emitted error input

**Controlling disposition:** VETO

**Reviewed implementation:** `d1d86028da255f92052a53bdbecef740bd44c3a5`

**Reviewed tree:** `c8f784c3b68a4631bb36518ce9a4120ba2891d5a`

The independent domain reviewer issued `ACCEPT` for the bounded semantic scope and independently
reproduced the assurance blocker. The independent assurance reviewer issued the controlling VETO.
The named Section 11 duplicate-ID defect is closed, but the public Pydantic error surface remains
caller-ordered when two invalid children collide on both the declared key and the projected
type/location/message outcome key.

### 12.1 Minimal observable-outcome collision

Starting from the accepted fixture, the reviewer replaced only the assertion collection:

```text
assertions = [1, 2]
assertions = [2, 1]
```

For both scalar children the declared sort key is `(15, "", "", "")`. Each child also produces
the same projected outcome signature: `model_attributes_type`, empty inner location, and
`Input should be a valid dictionary or object to extract fields from`. Stable sorting therefore
retains caller order for the fully tied bundles.

The reconstructed errors copy the complete original child error, including `input`. The standalone
policy consequently reports inputs `[1, 2]` for the first payload and `[2, 1]` for the second at
canonical indexes zero and one. The containing request behaves identically below
`binding_policy.assertions`. This reproduced under JSON and normalized strict-Python ingress.
The complete default `errors(include_url=False)` payload, `str(exc)` and
`exc.json(include_url=False)` differ, even though their type/location/message projections match.
Sixteen fresh hash-seed processes showed that each order is internally stable but the two caller
orders remain observably unequal.

Both payloads refuse. The VETO is for the deterministic bounded diagnostic contract, not a false
accept. The successor tests compare only the selected type/location/message projection and thus
cannot detect the retained caller-ordered input.

### 12.2 Accepted evidence preserved

This VETO does not reopen the Section 11 correction or the domain-semantic boundary:

- the duplicate-ID site/tax case now produces the same complete type/location/message sequence in
  both orders, both modes, both public roots and across fresh hash-seed processes;
- the distinct-ID corpus remains stable over authored, reversed, rotated and shuffled orders while
  successful models preserve exact authored tuple and JSON order;
- the independently hardcoded 28-admissible/107-impossible subject-domain oracle passes at the
  assertion, base, policy and request roots with no false accept;
- the static matrix and shared semantic helper remain single-owned at their lowest public types;
- the collection wrapper delegates every child through `CompatibilityAssertion` and does not
  duplicate the subject/domain matrix;
- all prior basis, inverse-identity, ownership, route, class/key/kind, capacity/electrical-basis and
  cost/price controls remain closed; and
- the D3B-v1 shared-technology-binding restriction remains an execution limitation, not a D3A
  topology invariant.

Both reviewers obtained `293` focused D3B, `949` complete-contract, `330` D3A and `298` D2 passing
tests. Assurance measured `94.65%` package branch coverage and `96.93%` modified-module coverage.
Both Draft schemas, successful round trips, strict/frozen controls, formatting, static typing,
compilation, import boundaries, excluded-surface diff and `git diff --check` passed. Exact-head CI
was green, but neither CI nor the bounded domain acceptance overrides the assurance VETO.

### 12.3 Required bounded correction

The next successor must make fully tied invalid bundles indistinguishable over every error field it
actually emits. It must retain delegation through `CompatibilityAssertion`, keep authored position
only as the restoration address after successful validation, and must not reimplement the domain
matrix.

The smallest safe correction is to sanitize the reconstructed invalid-child `input` to a stable,
bounded contract token before calling `ValidationError.from_exception_data`. A general
`repr(input)` sort key is not acceptable because hostile Python objects may be unbounded,
stateful, identity-bearing or cyclic. The durable regression must compare `[1, 2]` with `[2, 1]`
at both public roots and in both ingress modes using the complete default error payload, string and
JSON representations, then repeat in fresh hash-seed processes. All earlier duplicate-ID,
distinct-ID, strictness, ownership, matrix and successful authored-order controls remain mandatory.

### 12.4 Exact review receipt

At review close, local `HEAD`, upstream, live remote topic and draft-PR head were all `d1d86028…`;
the tree was `c8f784c3b68a4631bb36518ce9a4120ba2891d5a`; protected/live `origin/main` and the
PR base were `9e1c6fae6220551754c23535caeaa86b37422230`; the topic was zero behind and eleven
commits ahead; the worktree was clean; and the PR was open, draft, mergeable and conflict-free.
Required exact-head checks were green. Issue `#1110` remained `OPEN`; its `HOLD` was unchanged.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `1b044704ea87541e0650a0b80c2eb8aa936c5f0af199b61f6540a5884d4bbc73` |
| `tests/contracts/test_assessment_scope_contract.py` | `c8dd04c9fc20714443f894c84f6d435c1f07ec52437db51d7ae4a37324c1bf80` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `3c47046173d2955d5178e88bbecca468a61ea399ccbda211a9f0b2258dd8d8ed` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `5fd3e789930f83aa4049e66cf29f383f5420654d498fb43b2a83b7247bbfe47e` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `f161b137122b9603be8fa5713d707fb3f5526eb078afae7edbada8b329d62388` |

The protected-base-to-candidate binary diff SHA-256 was
`6589facb4a59e37dd1254c10a2cc25ade815e4def12db21230aed4bf2a21143a`.

Candidate `d1d86028…` must remain unmerged. Domain acceptance remains valid for the semantic scope
it covered; assurance VETO remains controlling for delivery. Neither result changes grade,
evidence, lender, Board, release, deployment, issue or `HOLD` authority.

## 13. Successor review — raw-key extraction dispatches to caller code

**Controlling disposition:** VETO

**Reviewed implementation:** `865805284332300920ad6c2114624ced7ca23069`

**Reviewed tree:** `594c2e9c3f11f6c6a92fee8f3848754c62041387`

Both independent reviewers issued `VETO`. They accepted the inherited domain-semantic corpus and
proved that Section 12's raw-input ordering leak is closed. They then independently found that the
raw declared-key extractor invokes overridable `dict.get()` methods before the bounded child-error
projection can run. A strict-Python dictionary subclass can therefore execute caller behavior
inside the collection wrapper.

### 13.1 Minimal dispatch failures

Two bounded counterexamples control:

1. A dictionary subclass whose `get()` raises causes its exception to escape at both the standalone
   policy and containing-request roots. The same malformed child is normally refused by
   `CompatibilityAssertion`; the unbounded exception is introduced only by the wrapper's later
   raw-key extraction.
2. A stateful dictionary subclass returns different category values on successive `get()` calls.
   Revalidating the same exact Python object changes which of two malformed children is reported
   first at both public roots.

There is no false accept, but the public validation boundary promises bounded `ValidationError`
refusal and deterministic diagnostics. An escaped caller exception and a repeated-validation order
change each independently violate that boundary. Catching only the demonstrated exception would
not close equivalent dispatch through another overridden mapping method.

### 13.2 Accepted evidence preserved

The VETO does not reopen the bounded error projection or domain model:

- `[1, 2]` and `[2, 1]` now produce identical complete public errors within every JSON/Python and
  policy/request combination, including URL-enabled and URL-disabled structured errors, string and
  JSON forms, across fresh hash-seed processes;
- the bounded errors carry the constant `<invalid compatibility assertion>` input and omit raw
  child context;
- all 28 admissible and all 107 impossible subject/domain pairs behave correctly at assertion,
  base, policy and request roots with no false accept;
- the complete predecessor negative corpus and seven constructive positive policy families pass;
- 75 valid assertion orders preserve exact authored storage, serialization, schemas and wire shape;
- distinct-ID and duplicate-ID invalid receipts remain canonical across order, mode and root;
- D3A shared-binding topology remains valid while D3B-v1 continues to fail closed under its
  documented stricter execution limitation; and
- semantic ownership, external route layering and import boundaries remain unchanged.

The focused D3B, complete-contract, D3A and D2 suites passed `295`, `951`, `330` and `298` tests.
Governed Python `3.12.13`, 73 active rules, format, lint, typing, compilation, schema, public import,
excluded-surface and diff gates all passed. These receipts do not override either VETO.

The custom-error projection intentionally no longer exposes Pydantic's standard documentation URL
for nested child errors. Assurance recorded this as a secondary metadata observation, not a
controlling defect; the stable type, message and canonical location remain preserved.

### 13.3 Required bounded correction

The next successor must perform no caller-dispatched mapping operation while building a raw sort
key. It must extract category, assertion ID and kind only from exact built-in dictionaries using
non-overridable access. Dictionary subclasses and other mapping-like Python objects must be treated
as opaque for raw ordering and allowed to reach the existing child validator, whose bounded error
is then sanitized. The extractor must not call caller-controlled `get`, iteration, indexing or
`repr`.

Durable controls must prove that a raising dictionary subclass cannot escape as an arbitrary
exception and that a stateful subclass cannot change the complete receipt across repeated
validation of the same object, at both policy and request roots. Section 12 scalar controls,
duplicate-ID and distinct-ID order/hash controls, successful authored-order round trips,
strictness, ownership and the complete domain matrix remain mandatory.

### 13.4 Exact review receipt

At review close, local `HEAD`, upstream, live remote topic and draft-PR head were all `8658052…`;
the tree was `594c2e9c3f11f6c6a92fee8f3848754c62041387`; protected/live `origin/main` and the
PR base were `9e1c6fae6220551754c23535caeaa86b37422230`; the topic was zero behind and thirteen
commits ahead; and the worktree was clean. The PR remained open and draft. Issue `#1110` remained
`OPEN`; its `HOLD` was unchanged.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `74485d4f2e704387aa8e1b8d036692f99ce8bd218bc40c2723fb9429060b4435` |
| `tests/contracts/test_assessment_scope_contract.py` | `3631d35c74f4d3dbbcb6f38fe1f82979be58767adc9044543c71e6e45256d1ea` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `6f3e88f61789e46920cc2097bef15ba6e0dc830a9ed258be9d6ddf260c07ddba` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `c96e33a30eb7cf1cb8797afd0edacff93828a40c2c4c9aa7848dba287f005678` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `02af83813a317d0d8407231151a624c3f927e1861c4e73b3d24cd462529ad8d1` |

The protected-base-to-candidate binary diff SHA-256 was
`b79d339c3ea661ab6b3af11fd667c6d0e8ea9bf1717541a922ec0e6e7b69a439`.

Candidate `8658052…` must remain unmerged. Both VETOs control delivery. No result changes grade,
evidence, lender, Board, release, deployment, issue or `HOLD` authority.

## 14. Successor review — trusted-type membership still uses rich equality

**Controlling disposition:** VETO

**Reviewed implementation:** `e1e3c01a0d11694d51130f5d5d115008c971500a`

**Reviewed tree:** `4006f1d0787d68da0695ffe48e78e90dba494210`

Both independent reviewers issued `VETO`. They proved that Section 13's dictionary-subclass defect
is closed and accepted the complete inherited domain-semantic, error-order, schema and successful
wire corpus. They then found one remaining caller-dispatch path: tuple membership is used to decide
whether the exact child type is one of the eight trusted compatibility-assertion model classes.
Tuple membership performs rich equality, not identity-only comparison.

### 14.1 Minimal type-membership failure

An otherwise opaque malformed child can have a class whose metaclass defines equality behavior.
The raw-key extractor obtains that class safely with `type()`, but testing whether it is `in` the
trusted type tuple calls the untrusted equality behavior. A raised caller exception consequently
escapes at both standalone-policy and containing-request roots before the bounded child-error
projection runs. The existing `CompatibilityAssertion` validator normally refuses the same child;
the escape is introduced only by the wrapper's membership test.

There is no false accept. The VETO is for executing caller code and escaping the bounded validation
surface. A trusted type allowlist must use object identity, never caller-defined equality or hash.

### 14.2 Accepted evidence preserved

- exact built-in dictionaries and exact compatibility models retain canonical ordering;
- raising and stateful dictionary subclasses are opaque, their overridden `get()` methods are not
  called, and repeated complete policy/request receipts are stable;
- the Section 12 scalar and earlier duplicate/distinct-ID ordering defects remain closed;
- all 28 admissible and 107 impossible subject/domain pairs behave correctly at all four roots;
- all 17 predecessor negative families and seven constructive positive families behave correctly;
- D3A shared-binding topology and the candid stricter D3B-v1 limitation remain distinct;
- successful schemas, wire shape and exact authored assertion order remain unchanged; and
- semantic ownership, external route layering and excluded imports remain intact.

The focused D3B, complete-contract, D3A and D2 suites passed `296`, `952`, `330` and `298` tests.
Governed Python `3.12.13`, 73 active rules, import/changelog, format, lint, typing, compilation,
schema, excluded-surface and diff checks passed. Green gates do not override the dual VETO.

### 14.3 Required bounded correction

The next successor must compare the actual child type with every trusted model type using explicit
object identity only. It must not use tuple/set membership, equality or hashing. A durable control
must prove that a child class's equality hook is never invoked at either public root and that
repeated validation yields the same bounded receipt. All dictionary-subclass, scalar,
duplicate/distinct-ID, matrix, schema and successful authored-order controls remain mandatory.

### 14.4 Exact review receipt

At review close, local `HEAD`, upstream, live remote topic and draft-PR head were all `e1e3c01…`;
the tree was `4006f1d0787d68da0695ffe48e78e90dba494210`; protected/live `origin/main` and the
PR base were `9e1c6fae6220551754c23535caeaa86b37422230`; the topic was zero behind and fifteen
commits ahead; and the worktree was clean. The PR remained open and draft. No issue or `HOLD` state
changed.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `c3169a6475ae01fb790a8cc04e82a814d976f486dafb106a05e56aea69f8d8f4` |
| `tests/contracts/test_assessment_scope_contract.py` | `2c8ed82916da081e84be6a7040085d750bdb9cfc6cbdc69a2adc6602e2a77bc9` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `4d29aea049ac7c0801b2204869abc3bf46b5e9449b360172960542dfbc525223` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `de4e2b3813b010ad52fd1c026e3a7c22d152a978a78fd4269399258f7ce99df1` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `e7e40d315bcfcbcb4734cd22ad3c26eb4746d32f1f8f0b65ee62377ef2fcd4d6` |

The protected-base-to-candidate binary diff SHA-256 was
`8b8c7ce3974ead8f1593ad6e959fba762c2305ed199781a387ae33c96d1bec82`.

Candidate `e1e3c01…` must remain unmerged. Both VETOs control delivery. No result changes grade,
evidence, lender, Board, release, deployment, issue or `HOLD` authority.
