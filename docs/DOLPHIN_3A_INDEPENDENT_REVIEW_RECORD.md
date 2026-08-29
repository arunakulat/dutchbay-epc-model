# Dolphin 3A independent specialist review record

**Record status:** blocking domain-review checkpoint under PERSIST-01
**Reviewed candidate:** `efba1e79c1ce400fed13e6fd90a9d31be5a77bbd`
**Reviewed base parent:** `0e63f7adacd47953f5eb6d555ad4d63c1d8dc212`
**Pull request:** `#1191`, retained as a draft after rejection
**Review role:** renewable-project domain specialist
**Authority boundary:** this is a specialist AI review of Dolphin 3A's proposed global
`ProjectCase` contract. It is not statutory assurance, external audit, engineering certification,
lender acceptance, verified human professional sign-off, achieved-grade authority, package
approval, package-release authority, or a decision to lift any `HOLD`.

## 1. Exact protected state at review

The reviewer independently verified all of the following before returning the disposition:

- local `HEAD`, the local remote-tracking topic ref, and the live remote topic branch all identified
  `efba1e79c1ce400fed13e6fd90a9d31be5a77bbd`;
- live `origin/main` identified `0e63f7adacd47953f5eb6d555ad4d63c1d8dc212`;
- PR `#1191` was open, draft, and pointed to that exact candidate;
- the D3A worktree was clean; and
- the reviewer made no file, Git-ref, GitHub, issue, audit-ledger, or release-state mutation.

The rejected candidate's five reviewed files had these SHA-256 fingerprints:

```text
ecd6f256be1db96f331a1b4876f1cd2d6fd458aa1b7eea1af047bd3cd87377ed  analytics/feasibility_report_contract/project_case.py
ec4a47eedf93408c44921404005978fae3d37cd3fb1877c4d2df48b5eaa30a8c  analytics/feasibility_report_contract/__init__.py
c1c3c43a26a9d6aad05d17dc6ddd72063fbf327fa9a8d05cb732a437c98d5145  tests/contracts/test_project_case_contract.py
06739a088cbdb98c502d610966022a9bf627aa55434a33e2a21bb7c93a42e638  changelog.d/project-case-v1.added.md
aecbae47a988055c80597771f2d31dfe4923479c6979ff89600ec077c61866ac  docs/SESSION_HANDOVER_2026-08-29_2.md
```

After this exact review, `origin/main` advanced to
`782c9588ef2685fcf0608d48f7745493aaa15b78` through the disjoint NSO merge. The topic branch was
merged forward without rebasing or rewriting the reviewed candidate. At synchronized topic commit
`44f64a2f03f1caac00a75be1c6823c231bfe8810`, all five fingerprints above remained identical and
the focused 81-test gate still passed. The rejection below remains bound to `efba1e79`; the later
merge commit is continuity evidence, not a substitute reviewed candidate.

## 2. Domain disposition

**DOMAIN REJECTED.** The candidate has strong foundations: strict frozen models, explicit physical
asset identity, discriminated generation/storage/shared-infrastructure types, absence of a Sri
Lankan fallback, explicit missing-input records, closed source and assumption registers for the
numeric fields they cover, pure import direction, and an honest raw-JSON/FastAPI transport seam.

Those foundations do not clear the gate. Independent hostile probes proved that the exact candidate
both accepted semantically impossible project cases and rejected ordinary globally relevant
renewable-project cases. The focused 81-test suite was green while these counterexamples remained,
so implementer-authored green tests were not an independent domain oracle.

## 3. Blocking findings

### D3A-DOM-01 — Hybrid and storage topology is incomplete and not globally valid

The candidate checked `charges_from` only when a link happened to exist. It did not require every
storage asset to declare a charging source. It also treated the identity of any
`SharedInfrastructureAsset` as a possible `shared_interconnection_asset_id` without checking that
the asset had an electrical or grid-interconnection role. Conversely, it forced every hybrid to
declare shared interconnection infrastructure and every non-shared asset to use some shared
facility, excluding valid projects with dedicated or separate electrical connections.

Independent counterexamples:

- removing the only storage `charges_from` link was accepted;
- changing the declared shared interconnection's type from `grid-interconnection` to `access-road`
  was accepted; and
- a wind-plus-BESS project with valid dedicated/separate connections and no shared facility was
  rejected solely because no shared interconnection was declared.

Required repair:

- introduce a typed electrical/interconnection role rather than treating any shared facility as an
  electrical interconnection;
- require every storage asset to declare a charging-source disposition: a generation asset, a typed
  grid/interconnection asset, another governed source, or an explicit unresolved/missing source;
- validate that a declared common interconnection is the governed electrical path it claims to be;
- represent shared versus dedicated facilities explicitly and accept valid dedicated hybrids; and
- add negative controls for a missing charge source, the wrong facility role, and a false common
  path, plus a positive dedicated-hybrid fixture.

Controlling D0 references include
`docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md` sections around lines 365, 412, and 638.

### D3A-DOM-02 — Capacity semantics exclude ordinary solar PV and erase storage bases

Aggregate and unitized generation capacities required the literal unit `MW`. A normal PV value such
as `100 MWdc` was rejected; relabelling it `MW` made it acceptable only by erasing whether the value
was DC nameplate, AC inverter capacity, or export capacity. Storage exposed only bare `power_mw`,
`energy_mwh`, and `duration_hours`. It could therefore reconcile incompatible propositions such as
nameplate-DC energy divided by usable-AC power.

Required repair:

- add typed capacity basis and dimension semantics for open generation technologies, including AC,
  DC, nameplate, usable, gross/net, and export where applicable;
- preserve explicit PV units such as `MWdc`, `MWac`, or `MWp`, or an equivalent dimension-plus-basis
  value object;
- require storage power, energy, and duration to declare compatible bases before reconciliation;
  and
- add positive solar and basis-consistent storage cases with negative mixed-basis controls.

D0 explicitly requires nameplate and usable storage capacity to remain distinct near line 638 of
the global master template.

### D3A-DOM-03 — Material price bases have no provenance binding

`PriceBasis` carried a valuation date, price level, nominality, reporting currency, and free text,
but no source or assumption reference. The root provenance walk covered `ResolvedValue`,
`ResolvedCount`, and `MissingValue`, leaving this material nonnumeric basis outside the closed
provenance graph.

An arbitrary future nominal basis dated `2099-12-31` was accepted after the conversion date was
made to match, without adding or changing any source or assumption record.

Required repair:

- bind every price basis to one or more exact source or assumption records;
- treat valuation date, nominality, price level, and reporting-currency basis as one controlled
  material proposition;
- validate its jurisdiction and technology/cost scope; and
- add negative controls for unbound and wrong-scope bases.

This traces to D0 cost-basis controls near lines 1081 and 1100 and D1 provenance requirements near
lines 328 and 420 of `docs/FEASIBILITY_REPORT_CONTRACT.md`.

### D3A-DOM-04 — Binary floats and one relative tolerance lose financial input identity

Every material numeric input used Python `float`, while one `1e-9` relative/absolute tolerance pair
was reused for capacity, allocation, FX, and money. Independent probes showed:

- exact JSON integer `9007199254740993` was accepted but serialized as
  `9007199254740992.0`; and
- a cost line whose exact multiplication was USD 1,000,000,000,000 accepted a declared amount that
  was USD 999 higher because the discrepancy fell within the scale-relative tolerance.

Required repair:

- use a precision-preserving strict `Decimal` representation with an explicit lexical/scale policy,
  or the D2 lexical numeric representation;
- define separate documented tolerances for engineering capacity, dimensionless shares, FX rates,
  and money;
- reconcile money according to currency minor units or explicitly declared quote precision, never
  a magnitude-relative binary-float tolerance; and
- add exact-identity and large-value negative controls.

D1 requires sufficient unrounded canonical precision near line 174 of the feasibility report
contract.

### D3A-DOM-05 — Some explicit missing states can never become valid

Validation returned early when a unit count or generation capacity operand was missing, and it
checked allocation totals only when every share was resolved. It did not reject already
contradictory partial states.

Independent counterexamples:

- resolved unit capacity `5`, resolved total capacity `11`, and an explicitly missing positive
  integer unit count were accepted even though no integer count can reconcile the operands; and
- one resolved allocation share of `1.0` plus a second explicitly missing, necessarily positive
  share was accepted even though the final total must exceed one.

Required repair:

- validate every constraint inferable from resolved operands;
- when only count is missing, require `total / unit_capacity` to admit a positive integer within the
  engineering tolerance;
- when shares are partially missing, require the resolved sum to be strictly below one and the
  unresolved remainder to be feasible; and
- preserve both exact counterexamples as durable negative controls.

## 4. High-severity findings

### D3A-DOM-06 — Multi-jurisdiction assets lack corresponding site identity

The root contained only one `ProjectLocation`, while assets named jurisdiction codes without a
site, coordinates, or boundary reference. Adding a second `SITE` jurisdiction binding was enough to
accept a BESS physically assigned to Sri Lanka while the only location and geometry remained in
Fictionland.

Required repair must choose one honest v1 boundary:

1. constrain v1 to one site and reject additional site jurisdictions/assets outside that location;
   or
2. add stable `ProjectSite`/boundary records and require every physical asset to reference exact
   site identities.

The present middle state must not claim multi-jurisdiction capability while omitting the additional
physical locations.

### D3A-DOM-07 — The versioned JSON contract silently accepts unversioned payloads

`schema_id` and `contract_version` had defaults, so neither appeared in the generated JSON Schema's
required root fields. Removing both from raw JSON was accepted and silently reinterpreted as
`dutchbay.project_case.v1` version `1.0.0`.

Required repair:

- make both fields mandatory at the transport/domain seam;
- add negative controls for missing, unknown, and future identifiers/versions; and
- leave any future endpoint-supplied versioning to an explicit versioned adapter operation rather
  than an invisible domain default.

This traces to the deliberate reader/version compatibility requirements near line 595 of D1.

## 5. Medium-severity findings

### D3A-DOM-08 — `contract_reviewed` is unprovable in the machine graph

The prose honestly said that this vocabulary was not engineering assurance, lender acceptance,
grade, or release. Nevertheless, any caller could mark an arbitrary pack ID/version
`contract_reviewed` without a reciprocal review identity, reviewer, scope, date, or effective
period.

Required repair: either rename the value to a neutral declared state that makes no review claim, or
require a contract-scope review reference bound to the exact pack, version, and scope. The explicit
prohibition against treating it as engineering, statutory, lender, grade, or release assurance must
remain.

### D3A-DOM-09 — Boundary status omits common controlled states

`BoundaryStatus` admitted only `indicative`, `contractual`, and `surveyed`, so a disputed cadastral
boundary or derived geospatial boundary had to be falsely labelled or rejected. D0 also names
registered, derived, and disputed states.

Required repair: add at least registered, derived, and disputed status, or separate legal/evidence
status from geometric derivation status. Add a disputed-boundary fixture and prove that it cannot
be represented as surveyed or contractual.

## 6. Focused-test confidence gap

The rejected candidate's 81 focused tests all passed, but omitted the independent counterexamples
above. In particular, they did not prove:

- mandatory charging-source disposition, typed electrical interconnection, or valid dedicated
  hybrids;
- solar AC/DC and storage basis compatibility;
- price-basis provenance;
- precision-preserving numeric identity or magnitude-independent monetary reconciliation;
- feasibility of partially missing unit counts and allocations;
- honest physical-site identity for multiple jurisdictions;
- mandatory schema/version fields;
- reciprocal evidence for a claimed reviewed state; or
- the disputed/derived/registered boundary vocabulary.

Each admitted counterexample must become a durable negative control that first reproduces the
candidate's defect and then passes only after the intended invariant is implemented. Positive
controls are also required for ordinary globally relevant configurations that the rejected model
could not express.

## 7. Non-blocking evolution notes

These observations were accepted and are not reasons for the veto:

- raw JSON can enter through `ProjectCase.model_validate_json()` and the handover correctly states
  that already parsed FastAPI/Pydantic payloads require explicit normalization or a raw-body adapter;
- the Draft 2020-12 schema is structurally valid;
- import direction is pure: no finance, evaluation, app, API, persistence, or renderer dependency;
- project ID, case ID, technology type, and physical asset-instance ID are separated;
- unknown and unsupported jurisdiction/technology bindings fail without a Sri Lankan fallback;
- source, assumption, and missing-input references are strongly closed for the numeric fields they
  currently cover;
- D2 source metadata, per-section result mapping, engine binding, grade/release policy, canonical
  hashing, delivery adapters, and report assembly remain legitimately outside D3A; and
- `ProjectCase` carries no grade, run-mode, lender, review-acceptance, package-release, or `HOLD`
  authority.

## 8. Independent command receipt

The reviewer re-entered the governed environment and recorded:

```text
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV
-> Python 3.12.13

DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv \
  PYTHONDONTWRITEBYTECODE=1 ./check_venv.sh --no-bootstrap
-> PASS; active checkout and import path were the D3A worktree; foreign_checkout_paths=[]

DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py
-> 72 rules; active=72

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python \
  -m pytest -p no:cacheprovider tests/contracts/test_project_case_contract.py -q
-> 81 passed; one pre-existing Hypothesis collection warning; zero failures

ruff check on project_case.py, package __init__.py, and the focused test
-> PASS

Draft202012Validator.check_schema(ProjectCase.model_json_schema())
-> PASS; required root fields omitted schema_id and contract_version

git diff --check origin/main...HEAD
-> PASS
```

The independent hostile-probe outputs were:

```text
storage_without_charge_source                         ACCEPTED
road_declared_as_shared_interconnection               ACCEPTED
unbound_future_price_basis                            ACCEPTED
impossible_partial_allocation_1_plus_positive_missing ACCEPTED
missing_integer_count_with_impossible_11_div_5_ratio  ACCEPTED
cost_arithmetic_999_usd_gap                           ACCEPTED
exact integer 9007199254740993                         ACCEPTED as 9007199254740992.0
solar aggregate capacity in MWdc                      REJECTED
hybrid with valid dedicated/no-shared interconnection REJECTED
FIC location plus LKA physical storage asset           ACCEPTED without LKA site geometry
unversioned raw JSON                                  ACCEPTED as v1.0.0
```

## 9. Controlling remediation and rereview boundary

This veto is cleared only by an independent exact-tree retest. Green implementer checks alone are
not sufficient. Before PR readiness or merge, the D3A successor must provide:

1. durable positive and negative controls for every counterexample in sections 3-5;
2. the complete focused D3A, `tests/contracts`, inherited D2, static, schema, precision, and coverage
   gates;
3. an exact-head domain rereview that returns `DOMAIN ACCEPTED`;
4. only after domain acceptance, a separate exact-head assurance review;
5. synchronization with then-live `origin/main`, preserving reviewed file fingerprints if upstream
   moves;
6. exact-head required CI; and
7. merge only when the remediated PR is current, fully green, independently accepted, and within
   the user's explicit authorization.

This record intentionally contains no assurance disposition: assurance review was not dispatched
after the domain rejection. PR `#1191` remains draft. Issue `#1110` and every project, evidence,
audit, Board, lender, grade, and package-release state remain unchanged and on `HOLD`.
