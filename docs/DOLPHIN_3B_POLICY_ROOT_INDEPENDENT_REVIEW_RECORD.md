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

## 15. Successor review — raw collection and accepted subclass dispatch remain

**Controlling disposition:** VETO

**Reviewed implementation:** `b035ae0a920f447e3316882b0f5744112532dd51`

**Reviewed tree:** `6ec5d6a3e80a073e8662a850f66ba52453ad3dfe`

Two fresh context-clean independent reviewers issued `VETO`. They proved that Section 14's
identity-only trusted-type correction is sound and accepted every preserved semantic, diagnostic,
schema and successful-wire control. They then identified remaining caller-dispatch paths at the raw
collection boundary and after the child adapter accepts a trusted-model subclass.

### 15.1 Remaining dispatch paths

Three related cases control:

1. The collection wrapper tests raw collection shape with `isinstance`. A noncollection object's
   dynamic class behavior can therefore raise before the strict tuple handler receives it. Direct
   strict Pydantic tuple validation refuses the same value with a bounded `ValidationError` and no
   hook call.
2. A tuple subclass passes the wrapper's `isinstance` check and is then iterated by the wrapper. An
   overridden iterator can execute and escape at both public roots.
3. The discriminated child adapter can return a subclass instance of a trusted compatibility model.
   The outcome sorter then calls its dynamically dispatched `model_dump_json()` method. An
   overridden method can execute and escape at both public roots.

There is no false accept. These are bounded-error and caller-code-execution defects introduced by
the wrapper around otherwise strict validation. The exact child-type `is` chain itself calls no
class equality and remains accepted.

### 15.2 Accepted evidence preserved

- the Section 14 equality ledger remains empty and repeated policy/request receipts are stable;
- dictionary subclasses remain opaque and their overridden `get()` methods are not called;
- scalar, duplicate-ID and distinct-ID complete diagnostic receipts remain canonical;
- all 28 admissible and 107 impossible subject/domain pairs behave correctly at assertion, base,
  policy and request roots;
- all inherited negative and constructive positive policy families behave correctly;
- D3A shared-binding topology remains valid and distinct from D3B-v1's documented limitation;
- successful validation/serialization schemas, wire shape and exact authored order remain intact;
- semantic ownership, external-route layering and import boundaries remain unchanged; and
- exact-head required CI and all six test shards were green.

The focused D3B, complete-contract, D3A and D2 suites passed `297`, `953`, `330` and `298` tests.
Package/module branch coverage was `94.66%`/`96.94%`. Governed Python `3.12.13`, 73 active rules,
format, lint, typing, import/changelog, compilation, excluded-surface and diff checks passed. Green
gates do not override the dual VETO.

### 15.3 Required bounded correction

The next successor must decide raw collection shape using built-in `type()` and exact object
identity only. Exact JSON lists and exact Python tuples may enter canonical child processing; every
other value must receive one constant-input bounded collection error without caller-dispatched
class, iteration, indexing or representation behavior.

After child delegation, only exact instances of the eight trusted compatibility model classes may
be treated as successful children or serialized for an outcome key. A model subclass returned by
the adapter must be converted to a bounded invalid-child receipt before any overridable model method
is invoked.

Durable controls must cover a dynamic-class noncollection, a tuple subclass with an overridden
iterator, and a trusted-model subclass with an overridden serialization method at both public roots,
with repeated complete structured/text/JSON receipt equality and zero hook calls. All Sections
1–14 controls remain mandatory.

### 15.4 Exact review receipt

At review close, local `HEAD`, upstream, live remote topic, pull ref and draft-PR head were all
`b035ae0…`; the tree was `6ec5d6a3e80a073e8662a850f66ba52453ad3dfe`; protected/live
`origin/main` and the PR base were `9e1c6fae6220551754c23535caeaa86b37422230`; the topic was
zero behind and seventeen commits ahead; and the worktree was clean. The PR was open, draft,
mergeable and clean. Issue `#1110` remained `OPEN`; no `HOLD` changed.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `e0bbfa22e989b35df31cf1961bfae5d82b7261d0e50997a14ff3910ce4ec622a` |
| `tests/contracts/test_assessment_scope_contract.py` | `254cb3a3407be1ced48d8457b9dd930a82a2ffa3c5a9c283d9e47cbf5feb9ddf` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `7483086ba7cf7c6cd4d61d444195460e88cc266a083f8b4bd8647760731080fb` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `c770dd14d5e63102832b3bf506492d4ffdac8fec361fe02b7dd265a90f00f63c` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `2ca24dfe26048cad468a6d3661c6febd91c5f0155ccb0d71b82cdc29674e70aa` |

The protected-base-to-candidate binary diff SHA-256 was
`34146ac17d943229c6001e80963616dafe265b5c3e09732e4411871661b6bfff`.

Candidate `b035ae0…` must remain unmerged. Both VETOs control delivery. No result changes grade,
evidence, lender, Board, release, deployment, issue or `HOLD` authority.

## 16. Successor review — exact trusted instance can still dispatch serialization

**Controlling disposition:** VETO

**Reviewed implementation:** `0b92cdf447bfe52a50d413f2c84589308004d6eb`

**Reviewed tree:** `795d74af2f10578710d7915087bad2662d12ed2e`

Fresh context-clean domain and assurance reviewers independently issued `VETO`. They proved that
the Section 15 correction closes exact collection shape, dynamic-class collection input,
tuple-subclass iteration and trusted-model-subclass serialization. They then found that exact
runtime model identity alone does not make dynamic instance-method lookup non-dispatching.

### 16.1 Remaining exact-instance dispatch

The successful-child outcome key still calls `validated_child.model_dump_json()` dynamically.
Pydantic's public unvalidated model-copy/update path can produce an exact
`ScenarioIdentityAssertion` instance with unchanged declared fields and an instance attribute that
shadows `model_dump_json`. The discriminated child adapter returns that same exact object, so the
identity-only trusted-type check passes. The later outcome-key call then executes the caller value.

Each reviewer reproduced raw caller `RuntimeError` escape twice at the standalone
`V14BindingPolicy` root and twice at the containing `EvaluationRequest` root. The hook ran on every
attempt and no bounded `ValidationError` existed from which to construct stable structured, text or
JSON receipts. This is the same accepted-model serialization defect class preserved in Section 15;
the subclass instance named there is closed, but exact-class instance state still reaches dynamic
serialization.

### 16.2 Accepted evidence preserved

- exact JSON lists and exact Python tuples validate while non-exact collection shapes receive
  bounded constant-input errors without caller class or iterator hooks;
- a trusted-model subclass is refused before its overridden serializer can execute;
- dictionary subclasses remain opaque, class rich-equality hooks remain unused, and scalar raw
  input/context remain absent from bounded errors;
- duplicate-ID, distinct-ID and fully tied malformed-child receipts remain deterministic across
  root, mode, order and fresh hash-seed processes;
- all 28 admissible and 107 impossible jurisdiction subject/domain cells retain correct behavior at
  assertion, base, policy and request roots;
- external-route layering, ownership, capacity/basis, technology, jurisdiction, cost/price and
  successful authored-order semantics remain correct;
- D3A's valid shared-technology topology remains distinct from D3B-v1's documented narrower
  physical-owner limitation; and
- the D3A, D2, schema, strictness, frozen, public-export and excluded-surface boundaries remain
  unchanged.

The focused D3B, complete-contract, D3A and D2 suites passed `299`, `955`, `330` and `298` tests.
Package/module branch coverage was `94.67%`/`96.96%`. Governed Python `3.12.13`, 73 active rules,
both Draft 2020-12 modes, Ruff, Black, isort, mypy without incremental cache, compilation,
import/changelog, cold-import, forbidden-import, excluded-surface and diff checks passed. The full
exact-head GitHub rollup completed with nineteen successful jobs, three governed skips and no
failure or pending job. Green gates do not override the dual VETO.

### 16.3 Required bounded correction

The next successor must normalize or revalidate exact model-instance children through
non-dispatching declared-field extraction and derive the successful-child outcome key without any
instance-resolved method call. Non-field instance state cannot participate in acceptance,
serialization or ordering.

A durable control must use an exact trusted model carrying an instance-level serializer shadow,
validate it twice at both public roots, require zero hook calls, require bounded constant-input
`ValidationError` receipts, and compare the complete structured, text and JSON forms. The accepted
exact-model Python ingress and successful authored order must remain unchanged, together with every
Section 1–15 control.

### 16.4 Exact review receipt

At review close, local `HEAD`, upstream, live topic, pull ref and draft-PR head were all
`0b92cdf…`; the tree was `795d74af2f10578710d7915087bad2662d12ed2e`; protected/live
`origin/main` and the PR base were `9e1c6fae6220551754c23535caeaa86b37422230`; the topic was
zero behind and nineteen commits ahead; and the worktree was clean. The PR was open, draft,
mergeable and clean. All four required checks and the complete exact-head rollup were green. Issue
`#1110` remained `OPEN`; no `HOLD` changed.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `b5da1ff33482ea36b5c8435143d14d887c2f2a481ada02e246faa37911b8cc35` |
| `tests/contracts/test_assessment_scope_contract.py` | `dcb0d57c38762596489723f456c31d899e5c96c38d472c59735d40d74de613fa` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `602c948d102678f70ffc7d6a177bebcbc782e80d7a89fafe05304794c4098584` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `403ec1168459d69e1295d0bcf15863a487e49843705037439a1f84cec3302964` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `23e7f2de4c4be142d5c657d20350bb353c76a2de39a8d03064121bccd356c6a4` |

The protected-base-to-candidate binary diff SHA-256 was
`77e35d7a39307102d37288b6e73504557e15f2d16a72c5f9b55dc31d287a46d4`.

Candidate `0b92cdf…` must remain unmerged. Both VETOs control delivery. No result changes grade,
evidence, lender, Board, release, deployment, issue or `HOLD` authority.

## 17. Successor review — rejected exact-model state still dispatches during raw ordering

**Controlling disposition:** DOMAIN VETO

**Reviewed implementation:** `3c016fef0aa93d1cfbb523f48f2c4c48dd29a71c`

**Reviewed tree:** `719c05027bf958cc605c04b36f56da110e8286f0`

**Reviewers:** Hubble, independent domain review (`/root/d3b_final_domain_review`); Turing,
independent assurance review (`/root/d3b_final_assurance_review`)

The assurance reviewer issued `ACCEPT` for this exact candidate and found Section 16's
serializer-shadow defect closed within the assurance lens. The domain reviewer accepted the same
correction and inherited semantic corpus, then found a remaining caller-dispatch path while ordering
an exact trusted instance whose state had already been rejected. The domain `VETO` controls
delivery. Green tests, security checks and the bounded assurance acceptance cannot override it.

### 17.1 Controlling exact-instance counterexample

Using only Pydantic's public `model_construct` and `model_copy(update=...)` operations, the domain
reviewer created an exact trusted assertion with unchanged field count, one declared field absent,
and that field represented by a hash-colliding `str`-subclass key. The exact-instance state detector
correctly classified the object as invalid. `_raw_policy_assertion_sort_key` then independently
reread the rejected object's original `__dict__` through `dict.get` while constructing the
diagnostic-order key.

The built-in lookup invoked the caller key's rich equality and produced these exact outcomes:

| Public root | Attempts | Result |
|---|---:|---|
| Standalone `V14BindingPolicy` | 2 | raw caller `RuntimeError` twice |
| Containing `EvaluationRequest` | 2 | raw caller `RuntimeError` twice |

Equality hooks ran in all `4` of `4` attempts, and no bounded `ValidationError` receipt existed.
This is not a semantic false accept. It is a CASPER bounded-error and caller-dispatch defect: state
already rejected by the contract must be opaque to diagnostic ordering.

### 17.2 Exact assurance acceptance preserved

Turing's `ACCEPT` remains valid only for `3c016fe…` and only within its stated assurance scope. The
reviewer established that all eight trusted field-name tuples matched live Pydantic declarations;
clean public constructs were freshly revalidated rather than identity-retained; missing, additional,
replaced and semantically invalid state was refused; and serializer shadows on every trusted class,
twice at both public roots, produced stable complete structured, text and JSON errors with zero
shadow hooks. Instrumentation showed the class-owned serializer called once per validation and was
restored. The inherited collection, tuple-subclass, model-subclass, dictionary-subclass,
rich-equality, scalar, duplicate/distinct ordering, schema and successful-wire controls passed.

Hubble independently preserved those accepted facts and extended them: all eight class field maps
were exact; clean constructs accepted `16/16` across classes and roots; invalid declared fields
revalidated and refused `16/16`; missing and additional state each produced bounded state errors
`16/16`; tuple/date subclass hooks remained zero; and a non-exact instance dictionary was refused
without mapping hooks. The independently hardcoded jurisdiction matrix remained `28` accepts and
`107` refusals at each root. External-route layering, ownership, identity, capacity/basis,
route-completeness, cost/price, D3A shared-binding distinction, D2 boundary, both schema modes,
strict Python ingress, JSON round trip and four ten-assertion authored-order permutations all
remained correct.

### 17.3 Required bounded correction

The successor must derive exact-model diagnostic ordering only from the fresh, sanitized
declared-field payload. Invalid exact-model state receives one constant deterministic raw ordering
key and the original `__dict__` is never read again. A public construct/copy regression must replay
the hash-colliding key twice at both public roots and require stable complete constant-input
`compatibility_assertion_state` receipts with zero caller equality hooks.

The equivalent exact built-in dictionary path must also fail closed: a non-exact dictionary key
must not reach raw ordering or the child adapter, and inspection must not invoke caller equality,
hashing, representation or method dispatch. Dictionary subclasses remain opaque under the already
accepted Section 13 boundary.

### 17.4 Exact review receipt

At review close, local `HEAD`, upstream, live topic, pull ref and draft-PR head were all
`3c016fef0aa93d1cfbb523f48f2c4c48dd29a71c`; the tree was
`719c05027bf958cc605c04b36f56da110e8286f0`; protected/live `origin/main` and the PR base were
`9e1c6fae6220551754c23535caeaa86b37422230`; the topic was zero behind and twenty commits ahead;
and the worktree was clean. PR `#1204` was open, draft, mergeable and clean. All four required checks
and the complete exact-head rollup were green, including all six test shards, coverage, Code
Quality, Security Scan, CodeQL, smoke, fastlane and verification receipts. Issue `#1110` remained
`OPEN`; no `HOLD` changed.

Shared local gates passed `300` focused D3B tests, `956` complete-contract tests, `330` D3A tests
and `298` D2 tests. In-memory branch coverage was `94.69%` for the package and `96.90%` for the
modified module. Ruff check/format, Black, isort, mypy `--no-incremental`, in-memory compilation,
forbidden-import AST, excluded-surface and `git diff --check` passed. The local
import/changelog/cold-import group passed `33` controls and had two timing-only failures at about
`2.35`–`2.38` seconds against a `2.0`-second threshold; protected-base and candidate medians were
`2.404` and `2.386` seconds respectively, and exact-head CI was green. Both reviewers disclosed the
environmental, non-regressive timing limitation and did not treat it as controlling.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `9f2cc0774a2ee700cab955490d81f926b62f90c089d6329039ac6cc8b35a6f20` |
| `tests/contracts/test_assessment_scope_contract.py` | `5b83d5b27f1b201e74f7ebc347bf55cf21ccca94876b3b9ae029e70e62263392` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `b625fc84975efb3dbe11fba5ca9632f84a566c74051796e18f9638c3d987b2b5` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `2c3adbdc4b9fcc02c7c96459dc92c1a802280f13991909e36093fde124479cc6` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `4929267cac5d617e8d9a17cbba5010c3d4e5bfafe5f33ef52c351b39c5b72d04` |

The protected-base-to-candidate binary diff SHA-256 was
`682565a8b0e14fc658b8ad7515618580a721974f3ea5e69dcf0037061fd5f434`.

Candidate `3c016fe…` must remain unmerged. The assurance `ACCEPT` remains exact-SHA evidence for its
tested scope; the domain `VETO` controls delivery. Neither disposition changes grade, evidence,
lender, Board, release, deployment, issue or `HOLD` authority.

## 18. Frozen-candidate review — non-built-in mappings and hostile discriminators dispatch

**Controlling disposition:** ASSURANCE VETO

**Exact-SHA domain disposition:** DOMAIN ACCEPT

**Reviewed implementation:** `6d4b788f0c37249c75026c6449fde37a08f6dc7f`

**Reviewed tree:** `e37d54300673e313ba7618bd162685c13fb29611`

**Protected/current base:** `9e1c6fae6220551754c23535caeaa86b37422230`

**Reviewers:** Hubble, independent domain review (`/root/d3b_final_domain_review`); resumed
independent assurance review (`/root/d3b_restart_assurance`)

Hubble issued `DOMAIN ACCEPT` for this exact candidate after independently replaying the Section 17
counterexample and the inherited semantic corpus. The resumed assurance reviewer then found a
separate raw-Python ingress boundary that Hubble's domain lens did not close and issued
`ASSURANCE VETO`. The assurance VETO controls delivery. Hubble's acceptance remains preserved as
exact-SHA evidence only; neither disposition applies to any successor SHA.

### 18.1 Exact domain acceptance preserved

Hubble established that the Section 17 exact-model and exact-dictionary counterexamples each
produced deterministic bounded `compatibility_assertion_state` or
`compatibility_assertion_key` errors, twice at the standalone `V14BindingPolicy` root and twice at
the containing `EvaluationRequest` root. Every error carried the constant invalid-assertion input,
and both equality and hash ledgers remained empty.

The reviewer also established all of the following for `6d4b788…`:

- all eight trusted-class field maps matched the live Pydantic declarations;
- the ten fixture assertions behaved correctly as clean instances and under missing, additional or
  semantically invalid state;
- an independently hardcoded 9-by-15 jurisdiction matrix produced 28 accepts and 107 refusals at
  each of the assertion, base, policy and request roots: 540 decisions with zero mismatch;
- external-route layering remained correct;
- 18 independent ownership, basis, route, price, currency and duplicate negative cases were refused
  at both public roots, while five constructive wind, BESS and solar cases were accepted;
- four authored orders were preserved through JSON ingress, normalized Python ingress,
  serialization and round trip, with deterministic distinct-ID, duplicate-ID and fully tied
  diagnostics;
- five public instances passed both schema modes, for ten schema validations;
- the valid D3A shared-binding topology remained accepted while D3B-v1's documented narrower
  physical-owner limit remained refused; and
- D2, D3A, the complete contracts, evaluator, finance, app, API, `VERSION` and release surfaces
  remained outside the change.

The local domain receipt passed the Section 17 control, `301` D3B tests, `957` complete-contract
tests, `330` D3A tests, `298` D2 tests and `35` import/changelog/cold-import controls. Ruff, Black,
isort, mypy without incremental cache, compilation, forbidden-import, excluded-surface and diff
checks passed. Governed Python was `3.12.13`; environment verification passed; all 73 canonical
rules were active; and exact-head required and full CI were green.

Hubble retained the existing residuals: D3B-0 remains a declaration only and does not load
ProjectCase/configuration data, call the gateway or assemble a D2 package; shared-binding allocation
requires a later design; evidence and valuation dates remain D3B-1 work; and transport,
authentication and OpenAPI remain adapter-owned.

### 18.2 Controlling strict-Python mapping counterexamples

The resumed assurance reviewer supplied a child implementing `collections.abc.Mapping` but not the
exact built-in `dict`. The collection wrapper passed that object to the discriminated-union adapter,
which called the caller's `get("kind")`. A raising implementation escaped raw
`RuntimeError("mapping get must be bounded")` twice at each public root. Exactly one `get:kind`
call occurred per attempt, and no bounded `ValidationError` existed from which structured, text or
JSON receipts could be made.

An implementation inheriting `Mapping.get` reproduced the same result through its raising
`__getitem__("kind")`, twice at each public root. A benign mapping was refused but still executed
one caller `get`. A stateful mapping alternated between `model_type` and `union_tag_invalid`, so its
complete receipts changed at both public roots. A stable-get control did not execute `items`,
iteration, equality, hashing or representation; the demonstrated dispatch was bounded to caller
`get` or inherited `get` followed by caller `__getitem__`.

This is not a semantic false accept and it is not a cybersecurity finding. It is a strict typed
application-contract robustness defect: an inadmissible Python child can execute caller behavior
before the contract returns its promised bounded, deterministic refusal.

### 18.3 Hostile discriminator reachability

The assurance review also established that a non-exact `kind` discriminator could reach hashing,
equality, string conversion or representation inside the delegated union path. An exact built-in
dictionary carrying a non-exact `kind` value was sufficient to reach that behavior, including
failed-representation diagnostics, before a bounded error was eventually attempted. The same
boundary must therefore be closed for both exact dictionaries and declared-field payloads extracted
from exact trusted models.

### 18.4 Required bounded correction

Before union delegation in strict Python mode, a successor must admit only:

1. an exact built-in dictionary after the existing exact-key copy; or
2. one exact trusted model after the existing sanitized declared-field extraction.

Every other Python child, including any non-built-in `Mapping`, must immediately receive one
constant-input bounded child-type error and a fallback diagnostic-order key, without adapter or
object-method dispatch. Before either sanitized payload reaches the union adapter, `kind` must be an
exact built-in string equal to one of the eight closed assertion tags. Missing, non-exact and unknown
tags must each receive one constant-input bounded discriminator error without caller hashing,
equality, string conversion or representation.

Durable regressions must cover a raising custom `Mapping.get`, inherited `Mapping.get` reaching a
raising `__getitem__`, a stateful mapping, an exact dictionary with non-exact `kind`, and an exact
trusted model with non-exact `kind` state. Every object must run twice at both public roots with
identical complete structured, text and JSON receipts, constant invalid input and empty
`get`/`getitem`/iteration/`items`/equality/hash/string/representation ledgers. Existing accepted
exact dictionary/model behavior, authored order, Section 17 controls and all prior negatives must
remain unchanged.

### 18.5 Exact review receipt

At both review closes, local `HEAD`, upstream, live topic, pull ref and draft-PR head were all
`6d4b788f0c37249c75026c6449fde37a08f6dc7f`; the tree was
`e37d54300673e313ba7618bd162685c13fb29611`; protected/live `origin/main` and the PR base were
`9e1c6fae6220551754c23535caeaa86b37422230`; the topic was zero behind and 21 commits ahead; and
the worktree was clean. PR `#1204` was open, draft, mergeable and clean. Exact-head required and full
CI were green. Both reviews were read-only.

Candidate fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `eab858281bc6a855a3fe2bf4873f97df3de0adc3b74566ce3a2d13e14a38ebaa` |
| `tests/contracts/test_assessment_scope_contract.py` | `4ee479518d6fb7c6011e503338cf04156f1fd1dbb0e863d1b0c354effc76a37f` |
| `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `c6eb1bb51d108041e14e32aa17218296c67096a72162ed916fdb5968d5df26c8` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `455fdaa3d1c8d15ce35e1cc93dacf143eb777438cc41b2b10314632b1be39f42` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `73dd7a22e0ec33bae60384c6dfa9a2f8aec0b31299ee251f031f305a61eb7c0c` |

The protected-base-to-candidate binary diff SHA-256 was
`60610c54582091d31e9a027c5938581a70a3fa10b467ae977c1a8530eafe6be2`; the
predecessor-to-candidate binary diff SHA-256 was
`df510a4325bdb303bb6374b3557e293b0ea3cc9bb758d0d44e01d5e79351e4b0`.

Issue `#1110` remained `OPEN` with 23 unchecked items, and every release/lender/Board/evidence
`HOLD` remained unchanged. Candidate `6d4b788…` must not merge. The controlling assurance VETO can
be closed only by a new immutable successor, fresh exact-SHA domain and assurance review, and
exact-head required CI.

## 19. Final implementation review — dual acceptance on the strict-Python successor

**Domain disposition:** DOMAIN ACCEPT

**Assurance disposition:** ASSURANCE ACCEPT

**Reviewed implementation candidate:** `52974fcfa484fa30ac76037ef129a536bb7816be`

**Reviewed tree:** `acb1d41ea389cca01de3eef3a9e954092a9a4022`

**Protected/current base:** `9e1c6fae6220551754c23535caeaa86b37422230`

**Reviewers:** independent domain review (`/root/d3b_52974_domain_review`); independent assurance
review (`/root/d3b_52974_assurance_review`)

Both reviewers worked read-only and independently accepted the same exact implementation candidate,
tree and base. These dispositions bind only to `52974fc…` / `acb1d41…` / `9e1c6fa…`. They do not
prospectively accept this appended record or any later commit.

### 19.1 Independent domain acceptance

The domain reviewer issued `DOMAIN ACCEPT` with no blocker after re-ingressing the controlling
corpus and replaying the new strict-Python mapping/discriminator controls. The two new controls
passed, while accepted exact-dictionary and exact-model behavior, successful authored order and the
inherited policy semantics remained unchanged.

The independently hardcoded 9-by-15 jurisdiction subject/domain matrix produced 28 accepts and 107
refusals at each of four roots: 540 decisions with zero mismatch. External-route layering remained
correct. Eighteen independent ownership, basis, route, price, currency and duplicate negative cases
were refused at both public policy roots, for 36 refusals. Six constructive wind, BESS and solar
positives were accepted. Four authored orders remained stable through validation, serialization and
round trip.

The reviewer preserved the D3A shared-binding distinction: D3A's valid shared technology-binding
topology remained accepted, while D3B-v1's documented narrower physical-owner execution limit
remained refused. The complete local receipt passed `303` D3B tests, `959` contract tests, `330` D3A
tests, `298` D2 tests and the eight-test schema/strictness/frozen/export selection. Ruff, formatting,
typing, compilation, forbidden-import, excluded-surface and whitespace controls were green.

The exact-head GitHub rollup contained 19 successful jobs, three governed skips, no failure and no
pending job. The reviewer retained the controlling residual: D3B-0 remains an input declaration and
policy contract only. It does not load ProjectCase/configuration data, call the evaluation gateway
or assemble the D2 report package.

### 19.2 Independent assurance acceptance

The assurance reviewer issued `ASSURANCE ACCEPT` with no blocker after independently exercising
eight hostile input objects at two public roots and two attempts per root. All 32 attempts returned
deterministic bounded refusals with identical complete structured, text and JSON receipts per root,
the constant invalid-assertion input, and zero caller calls across `get`, `__getitem__`, iteration,
`items`, length, equality, hashing, string conversion and representation ledgers. The independent
receipt SHA-256 was
`20be0a4d85ea165b2f961a8516742d9c9feccc7137f9f3def2a8bcc4cc517d8d`.

An independent adapter spy supplied 22 invalid child cases and observed zero adapter calls for all
of them. Exact built-in dictionary and exact trusted-model positives each delegated exactly once.
Six valid variants and their round trips preserved all ten assertions and their authored order. The
valid-variant receipt SHA-256 was
`140fd345cb63a2efafb1a196f8d8be66edc6c1da130d01fa4ac7992dce378d91`.

The assurance reviewer independently preserved the same `303` D3B, `959` contract, `330` D3A,
`298` D2 and eight selected schema/strictness/frozen/export passes, together with `35` successful
import/changelog/cold/gateway-import controls. Static, typing, compilation, forbidden-import,
excluded-surface and whitespace gates were green. Exact-head required checks and the full GitHub
rollup were green.

### 19.3 Exact reviewed-candidate receipt

At both review closes, local `HEAD`, upstream, live topic, pull ref and PR head were exactly
`52974fcfa484fa30ac76037ef129a536bb7816be`; the tree was
`acb1d41ea389cca01de3eef3a9e954092a9a4022`; protected/live `origin/main` and the PR base were
`9e1c6fae6220551754c23535caeaa86b37422230`; and the worktree was clean. PR `#1204` was `OPEN`,
draft, mergeable and clean. Every required check and the complete exact-head rollup were green.
Issue `#1110` remained `OPEN` with zero of 23 controls checked, and its `HOLD` remained unchanged.

Reviewed-candidate fingerprints:

| File or diff | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `707a1e5d22d9b831e65e42d87690e6b951d77cceab172c43c1f7909c3c4e36a6` |
| `tests/contracts/test_assessment_scope_contract.py` | `70220e8bf210da7dd23e383cbe3190073d3cb5936619a9d85ac71a1109cfd4a9` |
| pre-append `docs/DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md` | `eac73b38de9b3b05a56dcf1d62c9cb520cbf530a44a89467bf7c1441345ddb68` |
| `docs/DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md` | `532e28b9810fc2446aa517ef81479ab1c02b4e7c8216110fc22f2aa7d72053f1` |
| `changelog.d/d3b-policy-basis-coherence.fixed.md` | `4696181879e807015b68cc0be9dbbf21f2c6c7afc7b75b6f09c1c43b5b462772` |
| protected-base-to-candidate binary diff | `bb841f1bac5cf7bd02e0e5bb0e6d35d40b864bcc461934481f2d054a361b4c2b` |
| predecessor-to-candidate binary diff | `335b11d8eb9924e173eb0ebc276123612de773e72dd9d9e8c9798351804a056c` |

The only warnings were the repository's inherited Hypothesis `norecursedirs` warning and mypy's
inherited unused-configuration-section warning. Neither reviewer identified a product, contract or
delivery blocker on the reviewed implementation candidate.

### 19.4 Shared limitations and authority boundary

The dual acceptance establishes engineering domain and assurance acceptance only for the exact
reviewed implementation. It does not make D3B-0 an executor, load a ProjectCase or authored
scenario, call finance/evaluation code, assemble a D2 package, support shared-binding allocation,
complete D3B-1/D3C, or change transport/authentication/OpenAPI ownership. It confers no achieved
grade, professional review, evidence sufficiency, release, deployment, lender, Board or issue
authority and lifts no `HOLD`.

No finance, evaluation, app, API, web, `VERSION`, grade, release or issue surface changed in the
reviewed candidate. The existing later-slice and adapter-owned residuals remain explicit work rather
than inferred capability.

### 19.5 Documentation-successor rebind gate

Appending this section changes the Git commit and tree even though it changes documentation only.
The resulting successor head is therefore not `52974fc…`, and neither exact-SHA acceptance applies
to it until both reviewers independently rebind their dispositions to the new commit/tree and
exact-head required CI is green again. This record does not self-accept its own successor, mark the
PR ready, authorize merge, change issue state or lift any `HOLD`.
