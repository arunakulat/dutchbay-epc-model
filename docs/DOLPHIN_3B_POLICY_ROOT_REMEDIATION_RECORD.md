# Dolphin 3B-0 standalone-policy basis-coherence remediation record

**Status:** successor implementation candidate; fresh domain and assurance dispositions pending

**Base:** protected `main` at `9e1c6fae6220551754c23535caeaa86b37422230`

**Affected contract:** `dutchbay.v14_binding_policy.v1` / `1.0.0`

**Authority:** correctness remediation only; no grade, review, release, deployment or `HOLD`
authority

## 1. Why this remediation exists

Dolphin 3B-0 was squash-merged through PR `#1198` and received two later review records through
PRs `#1200` and `#1201`. Both reviews accepted the merged contract within their stated scope. A
fresh local reconciliation against protected `main` recovered one counterexample that neither
merged review exercised.

`V14BindingPolicy` is separately versioned, publicly exported and directly constructible. It owns
the complete tuple of compatibility assertions. The merged implementation enforced one
electrical/capacity basis per ProjectCase asset only in the outer
`EvaluationRequest._require_internal_request_graph` path. Therefore the outer request rejected an
internally contradictory policy while the standalone policy accepted the same object.

The historical reviews remain evidence of what they actually tested. This record does not rewrite
their dispositions or pretend the missed counterexample was part of them.

## 2. Exact pre-remediation counterexamples

All three probes ran on clean protected `main` at `9e1c6fae…`, against
`analytics/feasibility_report_contract/assessment_scope.py` SHA-256
`56c118e3334e981ef45b69b1540469a7d709f1cf2a16a7dd7fb76020a14f960a`.

| Policy mutation | Standalone `V14BindingPolicy` | Full `EvaluationRequest` |
|---|---|---|
| Same wind asset and `total_power_capacity`: `net` on one redundant target, `gross` on another | **ACCEPTED** | refused |
| Same unitized wind asset: net project/technology totals plus nameplate turbine count | **ACCEPTED** | refused |
| Same BESS: usable power/duration plus gross energy | **ACCEPTED** | refused |

These are not missing live-ProjectCase comparisons. They are contradictions wholly visible inside
the policy's own assertion graph. D3A gives one generation-capacity object a single
`electrical_basis` and `capacity_basis`; its storage contract likewise requires power, energy and
duration for one asset to share both bases.

## 3. Bounded correction

The per-asset generation and storage basis maps now live in
`V14BindingPolicy._policy_covers_every_material_category`, the lowest public root that owns every
required input. The duplicate implementation is removed from the outer request graph. Consequently:

- standalone and nested validation use one rule and one deterministic error surface;
- every generation assertion for one `asset_id` must share one
  `(electrical_basis, capacity_basis)` tuple across project, technology and unitized selectors;
- every storage assertion for one `asset_id` must share one tuple across power, energy and duration;
- a coherent five-route nameplate wind policy remains valid; and
- no ProjectCase, v14 evaluation, finance, D2 package, web/API, grade, release or `HOLD` surface is
  changed.

The focused controls validate the standalone `V14BindingPolicy` first and the containing
`EvaluationRequest` second. This prevents a future outer-model validator from masking a regression
in the public policy root.

## 4. Review and delivery gate

This record is not a self-acceptance. Before merge, two independent reviewers must bind their
domain and assurance dispositions to the exact candidate commit and replay:

1. the three standalone counterexamples above;
2. the coherent five-route nameplate wind positive;
3. wind, solar DC, storage-only and hybrid request positives;
4. both Draft 2020-12 schema modes and the D3B lexical/determinism controls; and
5. the D3A and D2 contract regressions.

The pull request may merge under `MERGE-01` only when those dispositions are durable, the topic is
current and conflict-free, and every required exact-head CI check is successful. That delivery
authority cannot lift issue `#1110`, whose Board/lender/release `HOLD` remains outside this change.

## 5. First-candidate local pre-review receipt

Candidate `b2854c0530e4c58413896ac306a41bd624f6d559` was tested from the governed Python
3.12 environment with the active worktree first on `PYTHONPATH`. No finance, application, API or D2
implementation file differed from the protected-main base.

| Control | Result |
|---|---|
| Direct standalone-policy counterexamples and coherent positive | `5 passed, 131 deselected` |
| Complete D3B-0 assessment-scope contract | `136 passed` |
| Complete contract suite | `792 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.18%` total; modified assessment-scope module `95.03%` |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Draft 2020-12 validation and serialization schemas | valid |
| In-memory compilation, forbidden-import AST scan and `git diff --check` | passed |

These were local implementation controls, not independent acceptance and not a substitute for the
exact-head required GitHub checks. Both independent reviewers later vetoed this candidate; see
`DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md`.

## 6. Veto and complete-graph successor

The independent reviews bound to `b2854c0…` proved that moving only the basis maps did not close the
public-root ownership defect. Nine additional contradictions wholly visible inside the policy tuple
could still be accepted standalone and refused only by the containing request. The immutable VETO,
exact fingerprints and counterexamples are preserved in the independent review record rather than
rewritten here.

The successor candidate invokes one policy-internal graph control from `V14BindingPolicy`. In a
canonical category/assertion order and sorted physical-asset order it now:

- requires unique technology physical owners and binding IDs;
- requires a one-to-one identity in both directions: one exact technology ID/class pair per
  technology binding ID, and one exact jurisdiction code/subject pair per jurisdiction binding ID;
- requires every generation/storage capacity assertion to name the same-asset technology owner,
  class, authored kind and technology-level config key;
- retains one electrical/capacity basis tuple per physical asset;
- requires every generation technology to have a technology capacity route and every storage
  technology to carry exact power, energy and duration routes;
- allows one jurisdiction binding to route across authored domains only while its jurisdiction code
  and subject remain identical;
- requires exactly one price-basis assertion and reconciles every cost assertion's price-basis and
  reporting-currency identities to it; and
- removes the duplicate policy-owned checks from the outer request graph, which retains only
  scope/base/domain/authority comparisons.

The durable successor tests validate every migrated negative at the standalone policy first and the
containing request second. They add the assurance review's isolated electrical-basis case and prove
that reordering one simultaneous generation/storage conflict cannot change its first-error family.
Consistent cross-domain jurisdiction routing, wind-only, solar DC, hybrid and storage-only positives
remain accepted.

D3B v1 deliberately permits only one policy-owned physical asset per technology binding ID. D3A's
structural contract can validly reuse one technology binding across multiple physical assets; D3B
does not reinterpret that predecessor rule. Instead, this first execution slice fails closed until a
later design explicitly authors allocation and result-lineage semantics for shared bindings. A live
ProjectCase requiring that topology is therefore outside D3B v1, not silently collapsed to one
asset.

This successor is not self-accepted. It requires a new immutable commit, fresh independent domain
and assurance review against that exact SHA, exact-head required CI, current protected-main ancestry
and a conflict-free PR before `MERGE-01` can apply. No finding in either review, and no later green
check or merge, can lift issue `#1110` or confer grade, lender, Board, release or deployment
authority.

## 7. Successor local pre-review receipt

The uncommitted successor tree was tested from the governed Python 3.12 environment with the active
worktree first on `PYTHONPATH`:

| Control | Result |
|---|---|
| Complete D3B-0 assessment-scope contract | `153 passed` |
| Complete contract suite | `809 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.55%` total; modified assessment-scope module `96.67%` |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Both Draft 2020-12 schema modes, strict/frozen ingress and public exports | passed in the focused suite |
| Forbidden-import/excluded-surface controls and `git diff --check` | passed |

The complete suite emitted only the repository's pre-existing Hypothesis `norecursedirs` warning.
These are local controls on a moving implementation tree. They do not replace the required fresh
independent dispositions, the immutable candidate rebind or exact-head GitHub checks.

## 8. Jurisdiction subject/domain successor correction

Independent review of `d164781354904386e81622af28462f6121fd5f1c` produced a split disposition.
Assurance accepted every replayed prior counterexample and the new one-to-one binding controls. The
domain reviewer then proved that a standalone jurisdiction assertion could still pair a subject
with an intrinsically impossible authored domain and be refused only by the containing request.
Both exact dispositions and the four constructive probes are preserved in the independent review
record; the domain VETO controls.

The bounded successor centralizes one static jurisdiction subject/domain admissibility helper and
reuses it at both owners:

- `JurisdictionSubjectAssertion` now refuses project-global domains and every subject/domain pair
  excluded by the immutable authored-domain matrix; and
- `BaseScenarioIdentity` calls the same helper when validating the subject authority selected by a
  retained domain route.

The containing request still owns the genuinely external question: whether an intrinsically valid
assertion's exact binding/domain authority route is retained by the selected base. Its durable
outer-route negative now uses the valid `site -> project_lifecycle_timeline` pair against an absent
domain, so lower validation does not mask that external control.

The test oracle independently enumerates the closed contract matrix: all `28` admissible pairs
accept at the standalone assertion root, while all `107` impossible pairs refuse at the standalone
assertion, standalone policy and containing request. The production immutable maps must equal that
independent expected matrix exactly. Existing site/project-resource, site/project-location,
tax/tax-statutory and consistent same-binding/multiple-domain positives remain valid.

### 8.1 Local successor receipt

| Control | Result |
|---|---|
| Complete D3B-0 assessment-scope contract | `288 passed` |
| Complete contract suite | `944 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.56%` total; modified assessment-scope module `96.70%` |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Both Draft 2020-12 schema modes, strict/frozen ingress and public exports | passed in the focused suite |
| Canonical governance bootstrap | `73` rules; `73` active |
| Forbidden-import/excluded-surface controls and `git diff --check` | passed |

The test suites emitted only the repository's pre-existing Hypothesis `norecursedirs` warning;
mypy emitted only its pre-existing unused-configuration-section warning. These local receipts are
not self-acceptance. A new immutable implementation SHA still requires fresh independent domain and
assurance dispositions, current protected-main ancestry, a conflict-free PR and exact-head required
CI before `MERGE-01` can apply.

## 9. Canonical child-validation-order successor correction

Independent review of `d7eb1358f767e9101f83f3c2ffded08e5e9b41ce` accepted the complete
jurisdiction subject/domain matrix and its lowest-owner placement, then found a distinct assurance
defect. Two intrinsically impossible jurisdiction children were validated in caller tuple order
before the policy's after-model canonical graph traversal could run. Reversing the authored tuple
therefore reversed the first error and its index. The exact controlling VETO and counterexample are
preserved in the independent review record.

The bounded successor keeps `JurisdictionSubjectAssertion` as the standalone semantic owner and
does not duplicate its matrix in a raw parent preflight. Instead, the `assertions` collection wrap
validator:

- orders raw children by immutable `ProjectCaseMaterialCategory` declaration order and exact
  `assertion_id`;
- delegates every child to the existing discriminated `CompatibilityAssertion` type in the
  caller's JSON or Python validation mode;
- aggregates the complete child error set with canonical collection indexes; and
- after successful validation only, restores the exact authored assertion tuple before the policy
  graph runs and before serialization.

Consequently, authored, reversed, rotated and deterministically shuffled versions of the
simultaneous site/tax counterexample now produce one first message and location family at both the
standalone policy and containing-request roots. Eight separate `PYTHONHASHSEED` processes produce
the same receipt. Valid versions of all four orders retain their exact assertion-ID sequence through
both roots and JSON serialization. Additional controls prove that normalized Python tuples and
already-validated children remain accepted while raw Python lists, non-collections, malformed child
categories and scalar children remain refused under the existing strict contract.

### 9.1 Local successor receipt

| Control | Result |
|---|---|
| Complete D3B-0 assessment-scope contract | `291 passed` |
| Complete contract suite | `947 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.63%` total; modified assessment-scope module `96.88%` |
| Authored/reversed/rotated/shuffled and eight-hash-seed error controls | passed at policy and request roots |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Both Draft 2020-12 schema modes, strict/frozen ingress and public exports | passed in the focused suite |
| Forbidden-import/excluded-surface controls, in-memory compilation and `git diff --check` | passed |

The test suites emitted only the repository's pre-existing Hypothesis `norecursedirs` warning;
mypy emitted only its pre-existing unused-configuration-section warning. This correction changes
validation order only: it does not change the accepted subject/domain matrix, accepted wire shape,
authored serialization order, ProjectCase semantics, evaluation, finance, application, grade,
release or `HOLD` authority. The successor remains a local implementation receipt until a new
immutable SHA receives fresh independent domain and assurance dispositions and exact-head required
CI is green.

## 10. Total child-outcome-order successor correction

Independent review of `2b97743db4459116f5ae118a95ce09c4528dcfe3` produced another split
disposition. Domain review accepted the complete matrix, ownership boundary, successful wire order
and D3A limitation. Assurance then proved that two child-invalid jurisdiction assertions which also
reuse one `assertion_id` collide on `(category, assertion_id, kind)`. The candidate used authored
index as its last key, so exchanging those children exchanged the first error even though both
payloads refused. The exact domain ACCEPT, controlling assurance VETO and three-field
counterexample are preserved in the independent review record.

The bounded successor now treats authored position only as a successful-order restoration address:

- every raw child is independently delegated to the existing discriminated
  `CompatibilityAssertion` type in the caller's JSON or Python validation mode;
- one immutable bundle retains the authored address, declared category/ID/kind key, validated child
  or complete error tuple, and a deterministic validation-outcome signature;
- invalid-child errors are internally ordered by type, inner location and message;
- all bundles are ordered by declared identity plus outcome signature before canonical collection
  indexes are assigned; and
- only an error-free authored bundle sequence is passed back through the collection handler, so
  successful policy storage and serialization preserve exact caller order.

The subject/domain matrix remains solely in the standalone semantic helper. The collection
validator does not inspect subjects or domains and does not reproduce their admissibility policy.

The durable duplicate-ID control exchanges the two child-invalid assertions and compares the
complete type/location/message error sequence at standalone policy and containing request roots, in
JSON and normalized strict-Python modes. Both orders now produce site/tax-statutory at canonical
index 2 followed by tax/project-resource at canonical index 3. Eight fresh hash-seed processes
produce one complete receipt. The distinct-ID authored/reversed/rotated/shuffled corpus, valid
authored-order round trips and strict list/non-collection/malformed-child refusals remain unchanged.

### 10.1 Local successor receipt

| Control | Result |
|---|---|
| Complete D3B-0 assessment-scope contract | `293 passed` |
| Complete contract suite | `949 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.65%` total; modified assessment-scope module `96.93%` |
| Duplicate-ID both-order/both-root/JSON/Python/eight-hash-seed complete-error controls | passed |
| Existing distinct-ID permutation/hash-seed and successful authored-order controls | passed |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Both Draft 2020-12 schema modes, strict/frozen ingress and public exports | passed in the focused suite |
| Forbidden-import/excluded-surface controls, in-memory compilation and `git diff --check` | passed |

The test suites emitted only the repository's pre-existing Hypothesis `norecursedirs` warning;
mypy emitted only its pre-existing unused-configuration-section warning. This remains a local
implementation receipt, not self-acceptance. A new immutable SHA requires fresh domain and
assurance review, current protected-main ancestry, a conflict-free PR and exact-head required CI.
No outcome can lift issue `#1110` or confer grade, evidence, lender, Board, release or deployment
authority.

## 11. Bounded emitted-child-error successor correction

Independent review of `d1d86028da255f92052a53bdbecef740bd44c3a5` accepted the bounded
domain semantics but found another assurance defect. The candidate ordered invalid children by a
declared category/identity key plus error type, inner location and message. Two scalar children
`[1, 2]` and `[2, 1]` collide on both keys, while the reconstructed Pydantic errors retained each
raw child as public `input`. Exchanging the children therefore exchanged the complete public error
objects even though both payloads refused. The exact domain ACCEPT, controlling assurance VETO and
counterexample are preserved in the independent review record.

The bounded successor makes fully tied diagnostic bundles observably identical:

- child validation and semantic ordering remain delegated to `CompatibilityAssertion`;
- the declared key and bounded type/location/message outcome signature remain unchanged;
- each reconstructed invalid-child error uses a `PydanticCustomError` carrying the original stable
  error type and message;
- the public raw child and potentially identity-bearing error context are omitted and replaced by
  the constant input token `<invalid compatibility assertion>`;
- canonical collection locations remain assigned after semantic sorting; and
- authored position remains solely the restoration address for completely successful validation.

The correction deliberately does not sort on `repr(input)`: hostile Python objects can be
unbounded, stateful, identity-bearing or cyclic. It also does not duplicate the jurisdiction matrix
or change any successful wire payload.

Durable controls compare `[1, 2]` with `[2, 1]` at standalone policy and containing request roots,
in JSON and normalized strict-Python modes. They require equality of the complete default
`errors(include_url=False)` payload, `str(exc)` and `exc.json(include_url=False)`, assert the bounded
input token and absence of raw `ctx`, and repeat the complete receipt in eight fresh hash-seed
processes. The duplicate-ID, distinct-ID, successful authored-order, strictness, ownership and
matrix controls remain mandatory.

This changes only the bounded child-error projection. It does not change accepted domain semantics,
ProjectCase topology, evaluation, finance, application, grade, release or `HOLD` authority. This is
a local successor design until the implementation passes the governed gates and receives fresh
independent review on one immutable SHA.

### 11.1 Local successor receipt

| Control | Result |
|---|---|
| Complete D3B-0 assessment-scope contract | `295 passed` |
| Complete contract suite | `951 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.65%` total; modified assessment-scope module `96.93%` |
| Scalar both-order/both-root/JSON/Python complete public-error controls | passed |
| Eight-process scalar hash-seed complete public-error control | passed |
| Duplicate-ID full-error, distinct-ID permutation and authored-order controls | passed |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Both Draft 2020-12 schema modes, strict/frozen ingress and public exports | passed in the focused suite |
| Import/changelog tests and in-memory compilation | `17 passed`; compilation passed |
| Forbidden-import/excluded-surface controls and `git diff --check` | passed |
| Governed environment and canonical bootstrap | Python `3.12.13`; `73` of `73` rules active |

The test suites emitted only the repository's pre-existing Hypothesis `norecursedirs` warning;
mypy emitted only its pre-existing unused-configuration-section warning. These local receipts are
not self-acceptance. A new immutable SHA still requires fresh independent domain and assurance
dispositions, current protected-main ancestry, a conflict-free PR and exact-head required CI before
`MERGE-01` can apply.

## 12. Non-dispatching raw-key successor correction

Independent review of `865805284332300920ad6c2114624ced7ca23069` proved that Section 12's
scalar error-input leak was closed, but both reviewers found a new strict-Python boundary defect.
The raw ordering helper accepted dictionary subclasses through `isinstance(..., dict)` and then
called their overridable `get()` method. A raising implementation escaped the bounded validation
surface; a stateful implementation changed public error order across repeated validation of the
same object. The exact dual VETO and counterexamples are preserved in the independent review record.

The bounded successor performs no caller-dispatched operation while deriving a raw key:

- only exact built-in dictionaries expose raw category, assertion ID and kind;
- those fields are read through the built-in `dict.get` descriptor;
- only the eight exact compatibility-assertion model classes expose their already-validated fields,
  read from the model's built-in field dictionary without dynamic attribute access;
- dictionary subclasses, other mappings and other Python objects are opaque to raw ordering and
  proceed to the existing `CompatibilityAssertion` validator; and
- only exact built-in strings and the exact material-category enum contribute key tokens.

The wrapper therefore does not call caller-controlled `get`, iteration, indexing, attribute access,
string conversion or representation. The existing bounded child-error projection sanitizes the
resulting refusal. JSON-decoded built-in dictionaries and every successful accepted model retain
their prior declared ordering and exact authored wire order.

The durable hostile-Python control uses one raising and one stateful dictionary subclass. It
validates the same exact objects twice at standalone policy and containing request roots, requires
identical complete URL-enabled error, string and JSON receipts, and proves that neither overridden
`get()` method was called. All scalar, duplicate-ID, distinct-ID, strictness, ownership, matrix and
successful authored-order controls remain mandatory.

This correction changes only raw diagnostic-key extraction. It does not change accepted domain
semantics, ProjectCase topology, evaluation, finance, application, grade, release or `HOLD`
authority. It remains a local successor until all governed gates and fresh exact-SHA independent
reviews pass.

### 12.1 Local successor receipt

| Control | Result |
|---|---|
| Complete D3B-0 assessment-scope contract | `296 passed` |
| Complete contract suite | `952 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.66%` total; modified assessment-scope module `96.94%` |
| Raising/stateful subclass repeated-validation complete-error controls | passed at both public roots |
| Existing scalar, duplicate-ID, distinct-ID and authored-order controls | passed |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Both Draft 2020-12 schema modes, strict/frozen ingress and public exports | passed in the focused suite |
| Import/changelog tests and in-memory compilation | `17 passed`; compilation passed |
| Forbidden-import/excluded-surface controls and `git diff --check` | passed |

The test suites emitted only the repository's pre-existing Hypothesis `norecursedirs` warning;
mypy emitted only its pre-existing unused-configuration-section warning. This remains a local
receipt, not self-acceptance. A new immutable SHA requires fresh independent domain and assurance
dispositions, current protected-main ancestry, a conflict-free PR and exact-head required CI.
