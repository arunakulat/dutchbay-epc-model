# Dolphin 3A independent assurance review record

**Record status:** blocking exact-head assurance checkpoint under PERSIST-01

**Reviewed pushed head:** `722845742f7123af3d637373c1996a82e357347a`

**Reviewed production/test candidate:** `2a3831542a3160f6d02cb2f592c4487981647f19`

**Reviewed base/live main:** `782c9588ef2685fcf0608d48f7745493aaa15b78`

**Pull request:** `#1191`, open and draft at the reviewed head

**Review role:** independent senior Python/Pydantic and web/API assurance specialist

**Authority boundary:** this is a specialist AI assurance review of the narrow Dolphin 3A
`ProjectCase` contract. It is not statutory assurance, external audit, engineering certification,
lender or Board acceptance, verified human professional sign-off, achieved-grade authority,
package approval, release or deployment authorization, or authority to alter any project,
evidence, F5, audit, lender, Board, package-release, or other `HOLD` state.

## 1. Exact review binding and independence

Before any review probe, the reviewer independently verified:

- local `HEAD`, the local upstream topic ref, the live remote topic ref, and PR `#1191` head all
  identified `722845742f7123af3d637373c1996a82e357347a`;
- live `origin/main` and the PR base identified
  `782c9588ef2685fcf0608d48f7745493aaa15b78`, which was an ancestor of the topic;
- the topic was mergeable, the PR was open and draft, and the worktree/index were clean;
- the only delta from the domain-accepted candidate
  `2a3831542a3160f6d02cb2f592c4487981647f19` to the reviewed pushed head was the two-file
  documentation-only domain-acceptance checkpoint; and
- issue `#1110` remained `OPEN`, with 0 checked and 23 unchecked controls and its live `HOLD`
  language unchanged.

The reviewer did not change production, tests, exports, changelog, Git refs, GitHub, the pull
request, issue `#1110`, an audit ledger, release state, or a `HOLD` while establishing the
disposition. This record and the companion handover update were written only after the exact-head
disposition was final, under the controlling parent task's explicit PERSIST-01 instruction. They
are review documentation, not part of the reviewed candidate.

The reviewed candidate fingerprints were:

```text
1e9d6fefaf1697710068d9d4886ffaa29a10f00e4d0b658aada268503d19534f  analytics/feasibility_report_contract/project_case.py
c47038ff13e6135a9f8fe33c57ef0aacc424d8eab233e6f880c5d796b7ba8f5d  analytics/feasibility_report_contract/__init__.py
86827cd5a29c708b73f027c31c27b7f0a5492f86aae8e222977874efbd8d105e  tests/contracts/test_project_case_contract.py
2868899396d7f0cbd5cb2b8cc2d1ce282698623676edda3001a7f93e087a84e2  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
6e48509e8e7d7a14e095e552d64ce46f22c4a1fc3f73a4e6d95beb495bb5a9e0  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
a401099ae02f4eea2632f5e81ff9715941a2bb4db9987402405526eef029b247  docs/SESSION_HANDOVER_2026-08-29_2.md
```

The normative D0-D2 chain was re-ingressed at the fingerprints already recorded in the sixth
domain disposition. The governed Python was 3.12.13, `check_venv.sh --no-bootstrap` passed with the
D3A worktree selected for imports, and the canonical bootstrap reported all 72 GWTF rules active.

## 2. Assurance disposition

**ASSURANCE REJECTED.** The exact candidate retains substantial accepted behavior: strict frozen
object graphs, explicit discriminators, mandatory schema/version constants, sole-string material
Decimal/count JSON transport, deterministic scalar serialization, exact bounded Decimal arithmetic,
one-variable shared-FX closure, reciprocal topology and provenance registers, R10 dedicated-path
closure, a pure direct source import graph, and a candid separation from adapters, finance,
orchestration, grading, release, and every `HOLD` authority.

Those controls do not clear assurance. Independent full-root hostile probes exposed two web/
evolution contract failures and one typed physical-dimension failure. Each accepted payload can
cross the v1 boundary as a semantically or lexically false contract state while all 241 focused
tests, all 567 contract tests, the inherited 386-test D2 gate, and static checks remain green.

## 3. D3A-ASR-01 - stable identifiers are silently rewritten and disagree with schema

**Severity: blocking/high.** The new `StableIdentifier` applies
`StringConstraints(strip_whitespace=True, ...)` and terminates its pattern with `$`. Pydantic strips
the raw string before applying the pattern, while Draft 2020-12 validates the unmodified JSON
string. The v1 domain boundary therefore changes identity-bearing user input and does not agree
with its generated validation schema.

Independent full-ProjectCase results were:

```text
raw JSON mutation                                      runtime result                     Draft 2020-12
project_id = " project:fictional-hybrid "              ACCEPT -> "project:fictional-hybrid" REJECT
assets[0].asset_id = " asset:wind-block-01 "           ACCEPT -> "asset:wind-block-01"      REJECT
costs.lines[0].line_id = "cost:capex:plant\n"          ACCEPT -> "cost:capex:plant"         ACCEPT
```

The asset mutation is material: its links and allocations retained the canonical unpadded ID, and
runtime normalization silently made the lexically different asset identifier match those records.
The terminal-LF form also demonstrates why `$` is not an absolute-end assertion in the generated
schema. This conflicts with stable identity, strict transport, predictable cross-validator
behavior, and the explicit no-silent-coercion boundary. Canonical output being clean does not repair
the fact that a different raw identifier was admitted.

Required bounded remediation:

1. make every D3A `StableIdentifier` exact and non-normalizing in JSON and normalized Python mode;
2. replace `$` with an absolute-end formulation that runtime and Draft 2020-12 implement
   identically;
3. add full-root positives and negatives for leading/trailing ASCII space and tab, LF, CR, CRLF,
   U+2028 and U+2029 on project, case, asset, link, cost, allocation, binding, source, assumption,
   missing-input, price-basis and conversion identifiers; and
4. prove that a hostile asset identifier cannot become reciprocal with canonical links or
   allocations through normalization.

This repair must not weaken the already accepted Decimal/count sole-string rules or normalize
identity in a future adapter without an explicit, versioned operation.

## 4. D3A-ASR-02 - contract-pack versions are not exact portable semantic versions

**Severity: blocking/high.** `JurisdictionBinding.contract_pack_version` and
`TechnologyBinding.contract_pack_version` use the shared `SemanticVersion` pattern
`^\d+\.\d+\.\d+...$`. The pattern is not the SemVer numeric grammar promised by D1 and the type
name, uses Unicode-dependent `\d`, permits leading zeroes in major/minor/patch identifiers, and
uses the same non-absolute `$` terminator.

Independent full-root results were:

```text
contract_pack_version = "١.٠.٠"    runtime ACCEPT; Python Draft validator ACCEPT
contract_pack_version = "01.0.0"   runtime ACCEPT; Python Draft validator ACCEPT
contract_pack_version = "1.0.0\n"  runtime REJECT; Python Draft validator ACCEPT
```

SemVer numeric identifiers use ASCII `0-9` and do not permit leading zeroes. In addition, an
ECMAScript/browser validator interprets `\d` as ASCII while the Python runtime path admitted the
Unicode-digit value, so the generated contract is not portable across the web validation domain it
is intended eventually to serve. The exact root `contract_version` literal remains sound; this
finding concerns the two versioned pack-binding fields.

Required bounded remediation:

1. use one exact ASCII semantic-version grammar with the correct no-leading-zero rule and absolute
   end semantics for D3A pack bindings, or explicitly rename and version a deliberately looser
   token if semantic versioning is not intended;
2. replay shared D2 regressions if the common vocabulary is tightened, or introduce a D3A-local
   exact type without silently changing the accepted D2 contract;
3. test valid release, prerelease and build forms plus Unicode digits, leading zeroes, empty/double
   prerelease components, whitespace and terminal line separators; and
4. check runtime, Draft 2020-12, and an ECMAScript-compatible interpretation against the same
   matrix.

## 5. D3A-ASR-03 - electrical collection admits a non-electrical capacity unit

**Severity: blocking/medium.** `SharedInfrastructureAsset` restricts a
`grid_interconnection` capacity to `MW`, `MWac`, or `MVA`, but applies no corresponding dimension
rule to `electrical_collection` even though R10 treats both roles as governed electrical paths.

The independent mutation changed the canonical shared asset to a one-user dedicated
`electrical_collection`, retained a valid reciprocal topology, and set:

```text
capacity.value = "10"
capacity.unit  = "USD"
result         = ACCEPTED
```

The payload is structurally closed but calls a currency amount the capacity of a typed electrical
facility. An arbitrary `UnitToken` is appropriate for genuinely open other-facility roles, but it
does not preserve the dimension of a role whose electrical meaning drives a root invariant.

Required bounded remediation:

1. give `electrical_collection` a typed electrical capacity dimension or an explicit admissible
   unit rule appropriate to v1;
2. reject the exact `USD` counterexample and other non-electrical dimensions at the capacity field;
3. preserve valid `MW`/`MWac`/`MVA` cases and the open, explicit dimensions required by access-road,
   operations-facility and other shared-facility roles; and
4. keep R10's shared-versus-dedicated topology behavior unchanged.

## 6. Accepted independent replay

The rejection is bounded. It does not reopen the accepted original D3A-DOM-01 through -09 or
R1-R10 arithmetic/topology repairs. The assurance reviewer independently obtained:

```text
ProjectCase focused gate:                    241 passed; one pre-existing warning
Complete tests/contracts gate:               567 passed; one pre-existing warning
Inherited D2 import/taxonomy gate:            386 passed; one pre-existing warning
Independent shared-FX brute-force oracle:     288 schedules; 0 mismatches
Independent arrangement/role/user matrix:      30 cases; 0 mismatches
R10 / `connected_to` runtime/schema probe:      passed; relationship absent/refused
Decimal/count full-root lexical matrix:        14 cases; 0 mismatches
Native positive-exponent dump/schema/reingress: passed
Validation Draft 2020-12 schema:               valid; 47 definitions
Serialization Draft 2020-12 schema:            valid; 47 definitions
Canonical dump against both schemas:           passed
Public exports:                                62; all 58 ProjectCase exports present
Ruff check and format:                         passed
Black check:                                   passed
isort check:                                   passed
mypy --no-incremental:                         passed
in-memory compile and AST import scan:          passed
D3A excluded execution-surface diff:            empty
Exact-head GitHub CI:                          18 successful; 3 expected skipped; 0 failed/pending
Exact-head required checks:                    4/4 passed
git diff --check and pre-record status:          passed; clean
```

The warning was the pre-existing Hypothesis warning that repository `norecursedirs` suppresses
`.hypothesis` collection. Coverage was not rerun by the read-only reviewer because the normal
command creates a `.coverage` artifact; the sixth domain record preserves the exact-candidate
95.92% package / 95.29% module receipt, and GitHub remains the delivery authority.
The fully green exact-head CI is supplementary delivery evidence; it does not resolve any of
D3A-ASR-01 through -03 and therefore does not alter the assurance rejection.

Exact Decimal and count strings agreed between runtime and Draft 2020-12 at the 36-digit/
36-place boundaries; raw JSON numeric tokens, leading-zero counts, Unicode digits, exponent
strings, excessive scale and terminal LF were refused. Native `Decimal('1E+3')` serialized as
`"1000"`, passed the validation schema and re-ingressed identically. Both validation and
serialization schemas were structurally valid, and the canonical dump satisfied both.

The direct `project_case.py` AST imports only the standard library, Pydantic, and
`.vocabulary`. A normal public import still eagerly loaded eighteen pre-existing `analytics`
finance/evaluation/core/FX modules through `analytics/__init__.py`; D3A did not add those edges and
the handover states that limitation candidly.
The runtime `AssetLinkKind`, validation schema, serialization schema and hostile full-root link
probe also confirmed that `connected_to` is absent rather than retained as an unvalidated escape.

## 7. Non-blocking web and evolution notes

These observations do not add another remediation class to the three findings above:

- Draft 2020-12 treats JSON `1.0` as an integer, while strict Pydantic runtime rejects it for small
  control fields such as `revision`, `quote_precision`, and minor-unit places. Material count uses
  the intentional exact string representation and has no such ambiguity. A future adapter must not
  treat schema-only acceptance as domain acceptance.
- Pydantic's raw JSON parser accepts duplicate object keys using last-value-wins behavior. D3A
  defines no endpoint or canonical byte representation, so the future raw-body adapter must reject
  duplicate keys before domain validation rather than claim that `model_validate_json()` alone
  preserves an unambiguous submitted document.
- Cross-record provenance and missing-input failures currently have a root Pydantic location `()`
  and carry the exact JSON-pointer-shaped field path in the message. That is candidly documented,
  but a future adapter should map it into a structured, versioned transport error rather than ask a
  client to parse prose.
- Pydantic's serialization-mode schema advertises material Decimal/count outputs only as strings,
  without the validation schema's exact pattern. Actual output is deterministic and passes the
  stricter validation schema; a response/OpenAPI adapter should preserve those constraints if it
  publishes a separate output schema.
- Collections are intentionally unbounded and provenance scope resolution can become quadratic in
  the number of cost lines/allocations. No endpoint exists, and the handover already excludes
  request-size/resource policy. A web adapter must impose a measured body/collection bound before
  validation; indexing repeated scope lookups should be considered before large portfolio inputs.
- The public package import retains the pre-existing eager parent-package dependency surface. A
  future lightweight web worker must either package the governed full dependency closure or expose
  a genuinely isolated contract import path before claiming lightweight startup.

These are forward adapter/deployment duties, not grade, release, or scope expansion for the bounded
D3A repair.

## 8. Controlling remediation and rereview boundary

The next candidate is limited to D3A-ASR-01 through -03 and truthful changelog/handover wording. It
must preserve all domain-accepted production behavior and tests, direct import direction,
single-site boundary, R8/R9/R10 controls, exclusions, and every authority separation.

After remediation, rerun the focused, inherited D2, complete contract, coverage, Ruff, Ruff Format,
Black, isort, mypy, validation/serialization schema, cross-runtime lexical, import/exclusion and
diff gates. Commit and push one new exact head only under the controlling parent's delivery
authority. Then obtain a fresh exact-head domain delta confirmation for any production/type change
and a fresh independent assurance review. Existing domain acceptance does not supersede this
assurance rejection, and a documentation-only commit cannot clear it.

PR `#1191` must remain draft and must not merge while this **ASSURANCE REJECTED** disposition is
controlling. Issue `#1110` and every project, evidence, audit, lender, Board, grade, F5, package and
release state remain unchanged and on `HOLD`.
