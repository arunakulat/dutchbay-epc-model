# Dolphin 3A independent assurance review record

**Record status:** predecessor and recovered-successor vetoes plus final exact-head
**ASSURANCE ACCEPTED** disposition under PERSIST-01

**Predecessor reviewed pushed head:** `722845742f7123af3d637373c1996a82e357347a`

**Predecessor reviewed production/test candidate:** `2a3831542a3160f6d02cb2f592c4487981647f19`

**Reviewed base/live main:** `782c9588ef2685fcf0608d48f7745493aaa15b78`

**Recovered successor head:** `836502a607fbce479f8e0412e2c63cb8659fafcd`

**Final accepted pushed head:** `77db342342e5ef62c922ac328d73a0b2e3e407d3`

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

## 9. Restart recovery and successor exact-head binding

The local macOS host restarted after the bounded ASR worker candidate had been committed and pushed.
The recovered reviewer did not infer continuity from chat state. It reran the handover bootstrap,
verified governed Python 3.12.13, passed `check_venv.sh --no-bootstrap`, and reloaded all 72 active
GWTF rules from the canonical CSV before examining the successor.

A read-only fetch and independent live-remote queries established:

```text
local HEAD:                              836502a607fbce479f8e0412e2c63cb8659fafcd
local upstream topic:                    836502a607fbce479f8e0412e2c63cb8659fafcd
live remote topic:                       836502a607fbce479f8e0412e2c63cb8659fafcd
PR #1191 head:                           836502a607fbce479f8e0412e2c63cb8659fafcd
local/live origin/main and PR base:      782c9588ef2685fcf0608d48f7745493aaa15b78
topic relation to origin/main:           0 behind; 16 ahead; main is an ancestor
protected primary main:                  clean; 0 behind; 0 ahead of origin/main
PR state:                                OPEN; DRAFT; MERGEABLE; CLEAN
```

The exact successor candidate fingerprints before this documentation-only append were:

```text
04f5f110f419e57e21b8583285a9a994a9bc29b65b2998d1b92e1d514db8533a  analytics/feasibility_report_contract/project_case.py
291a823d75338b4d5360525d35bed60f7851ddabd4f16c30d816368fb4eb7bf9  analytics/feasibility_report_contract/__init__.py
99c40b6a66d28f170519fdfa830e24ecbb6fe5e34e73bede24b056c0d5a79d15  tests/contracts/test_project_case_contract.py
6e736691da24b0fb3a29f0303ebd3533e46f8e5637b5a310cfea91e8ec9aa027  changelog.d/project-case-v1.added.md
38d2831175bcf7d7567afb190fc32a2822da9a739c0454ff205127ca6828b9aa  docs/DOLPHIN_3A_ASSURANCE_REVIEW_RECORD.md
6e48509e8e7d7a14e095e552d64ce46f22c4a1fc3f73a4e6d95beb495bb5a9e0  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
779331e7dbe61d127ce2876b7e811f1108a6d774cccb251fdfdf6a33b9ddd96e  docs/SESSION_HANDOVER_2026-08-29_2.md
```

Exact-head GitHub CI had recovered to eighteen successful jobs, three expected skips, and no failed
or pending job. All four required checks passed. Issue `#1110` remained `OPEN`, with 0 checked and
23 unchecked controls and its explicit Board/lender `HOLD` unchanged. Green CI and mergeability are
delivery evidence only; neither can supersede the independent contract finding below.

## 10. Successor disposition for D3A-ASR-01

**D3A-ASR-01 ACCEPTED at the successor.** The repair uses one exact, non-normalizing ASCII stable-
identifier type. Its runtime validator and validation- and serialization-mode Draft 2020-12 schemas
share the same absolute-end grammar and the 1-160 character bound. It does not strip identity before
reciprocal asset, link, allocation, binding or provenance checks.

An independent full-root matrix exercised all thirteen identifier roles: project, case, asset, link,
cost, allocation, jurisdiction binding, technology binding, source, assumption, missing input,
price basis and conversion. It covered leading and trailing space, tab, LF, CR, CRLF, U+2028,
U+2029, non-ASCII letters and digits, the exact 160/161-character boundary, normalized Python mode,
and the former normalization-created asset reciprocity counterexample.

```text
independent runtime/Draft checks:              455
mismatches:                                      0
Python-mode padded identity:              refused
hostile asset normalization/reciprocity:   refused
```

This acceptance closes only D3A-ASR-01. It does not grant adapter, release or grade authority.

## 11. Successor disposition for D3A-ASR-02

**D3A-ASR-02 ACCEPTED at the successor.** D3A now uses a local exact ASCII SemVer grammar, leaving
the inherited D2 vocabulary unchanged. Core and numeric prerelease identifiers reject leading
zeroes; prerelease and build grammar is complete; the pattern uses neither Unicode-dependent `\d`
nor `$`; and the same pattern appears in both binding fields and both generated schema modes.

The independent matrix used ten valid release/prerelease/build forms and twenty invalid Unicode-
digit, leading-zero, empty-component, whitespace and terminal-line-separator forms against both
binding registers. Runtime and Draft 2020-12 agreed. The extracted generated pattern was also run by
an actual Node/ECMAScript `RegExp` implementation.

```text
independent runtime/Draft checks:               90
ECMAScript matrix:                 10 valid / 20 invalid
runtime/Draft/ECMAScript mismatches:             0
shared D2 SemanticVersion change:             none
```

This acceptance closes only D3A-ASR-02.

## 12. D3A-ASR-03 successor false rejection and schema truth

**D3A-ASR-03 REMAINS OPEN; the successor is rejected.** The bounded repair correctly refuses the
original `USD`, `km`, `item` and `MWh` non-power examples at runtime and continues to accept `MW`,
`MWac` and `MVA`. It nevertheless treats `electrical_collection` as if it could only be stated on
an AC/apparent grid basis. That is too narrow for the global solar boundary already represented by
D3A generation capacity, where DC capacity explicitly uses `MWdc` or `MWp`.

Independent full-root probes used a solar-generation plus storage case, an explicit DC generation
basis, a valid dedicated one-user collection topology, reciprocal links and complete provenance.
Both a resolved collection value and an explicit missing-input record at `/assets/2/capacity` were
tested for each DC unit:

```text
role                       state       unit   runtime result
electrical_collection      resolved    MWdc   REJECT - false rejection
electrical_collection      missing     MWdc   REJECT - false rejection
electrical_collection      resolved    MWp    REJECT - false rejection
electrical_collection      missing     MWp    REJECT - false rejection
grid_interconnection       resolved    MWdc   REJECT - intended
grid_interconnection       missing     MWdc   REJECT - intended
grid_interconnection       resolved    MWp    REJECT - intended
grid_interconnection       missing     MWp    REJECT - intended
```

The grid results preserve the correct AC/apparent point-of-interconnection rule. The collection
results prevent an otherwise valid solar project from crossing the supposedly global v1 contract.
The existing focused tests do not expose this because their electrical-collection positives contain
only `MW`, `MWac` and `MVA`.

The role-dependent unit rule is a Pydantic field validator and is not encoded in the generated
Draft schema. Draft 2020-12 accepted all eight DC-unit probes and also accepts the original
electrical-collection `USD` payload that runtime now refuses. That does not by itself require D3A to
duplicate every semantic root invariant in JSON Schema, but it makes the handover claim that the
electrical-collection counterexample is refused by an applicable generated schema false. The next
checkpoint must either encode that conditional schema behavior or state candidly that role/unit
dimension is runtime-only and that a web adapter must invoke the domain validator.

Required bounded remediation:

1. admit the electrical power-capacity units needed by v1 collection systems, at minimum `MW`,
   `MWac`, `MWdc`, `MWp` and `MVA`, for resolved and explicit-missing values;
2. keep `grid_interconnection` at `MW`, `MWac` or `MVA`, including resolved and missing controls;
3. preserve rejection of non-power dimensions and the open units for the three non-electrical
   infrastructure roles;
4. add full-root solar positives for resolved and missing `MWdc` and `MWp`, plus grid negatives for
   both DC units; and
5. correct the changelog and handover, including the runtime-versus-Draft boundary.

If a future version needs technology- or electrical-basis-specific collection semantics, it should
add that typed basis explicitly rather than infer it from a free technology identifier.

## 13. Recovered successor gate receipt

The false rejection is not a general regression. The exact pushed successor independently passed:

```text
ProjectCase focused gate:                       297 passed; one pre-existing warning
Complete tests/contracts gate:                  623 passed; one pre-existing warning
Inherited D2 import/taxonomy gate:               386 passed; one pre-existing warning
In-memory D2 plus ProjectCase coverage:          595 passed; 95.99% package total
ProjectCase module coverage:                     95.48%
Targeted FX/topology/provenance replay:            55 passed
ASR-01 independent matrix:                       455 checks; 0 mismatches
ASR-02 runtime/Draft checks:                      90 checks; 0 mismatches
ASR-02 Node/ECMAScript matrix:                    30 cases; 0 mismatches
Solar collection/grid resolved-missing matrix:     8 cases; 4 intended / 4 false rejects
Ruff check and format:                           passed
Black check:                                     passed
isort check:                                     passed
mypy --no-incremental:                           passed
in-memory compile and AST direct-import scan:    passed
validation/serialization Draft schemas:          valid; 47 definitions each
frozen object and extra-field refusal:            passed
public exports:                                   63; all 59 ProjectCase exports present
`connected_to` runtime/schema absence:            passed
D3A excluded execution-surface diff:              empty
git diff --check and pre-document status:          passed; clean
exact-head GitHub jobs:                           18 successful; 3 expected skipped
exact-head required GitHub checks:                4/4 passed
```

The warning is the pre-existing Hypothesis `norecursedirs` warning. Coverage ran entirely in memory
with no `.coverage` artifact. The production module's direct imports remain limited to the standard
library, Pydantic and `.vocabulary`; no finance, evaluation, app, API, persistence, orchestration,
grade, release or Sri Lankan fallback surface changed. The accepted R1-R10 FX, topology,
provenance, Decimal/count and authority boundaries remain intact.

## 14. Controlling recovered assurance disposition

**ASSURANCE REJECTED** for exact pushed head
`836502a607fbce479f8e0412e2c63cb8659fafcd`.

D3A-ASR-01 and D3A-ASR-02 are accepted and must not be reopened without new evidence. The sole
remaining production blocker is the bounded D3A-ASR-03 electrical-collection false rejection;
truthful runtime/schema wording is part of that same remediation. A green exact-head CI run does
not close it.

PR `#1191` must remain draft. No merge, grade, lender, Board, statutory, report-package, release,
deployment or `HOLD` authority follows from this review. Issue `#1110` remains `OPEN` and its
Board/lender circulation state remains `HOLD`.

## 15. Final exact-head assurance binding

The bounded D3A-ASR-03 repair was committed and pushed as
`77db342342e5ef62c922ac328d73a0b2e3e407d3`. A separate senior Python/Pydantic and web/API
assurance reviewer ingressed this complete record, both domain review records, and the current
handover before independently reviewing the exact pushed tree. A fresh read-only fetch established:

```text
local HEAD:                              77db342342e5ef62c922ac328d73a0b2e3e407d3
local upstream topic:                    77db342342e5ef62c922ac328d73a0b2e3e407d3
live remote topic:                       77db342342e5ef62c922ac328d73a0b2e3e407d3
PR #1191 head:                           77db342342e5ef62c922ac328d73a0b2e3e407d3
local/live origin/main and PR base:      782c9588ef2685fcf0608d48f7745493aaa15b78
topic relation to origin/main:           0 behind; 18 ahead; main is an ancestor
worktree, index and untracked set:       clean
PR state:                                OPEN; DRAFT; MERGEABLE; CLEAN
exact-head GitHub jobs:                  18 successful; 3 expected skipped; 0 failed/pending
exact-head required GitHub checks:       4/4 passed
```

The expected skips were Grid Study, Report Qualification, and Stochastic Qualification. Test
Summary, Verification receipts (`VERIFY-01`), fastlane, and smoke all passed. The reviewer made no
file, index, commit, push, PR, issue, release-state, or `HOLD` mutation.

The accepted exact-head fingerprints before this documentation-only append were:

```text
6d1ea97befe758a3c9f34bb74eee84b65b3650f621ac6f379f3c0dbeafcd6e7e  analytics/feasibility_report_contract/project_case.py
291a823d75338b4d5360525d35bed60f7851ddabd4f16c30d816368fb4eb7bf9  analytics/feasibility_report_contract/__init__.py
ca4ee993f6ea7077a26410b41de7e6a057319e6de8b4c8bec8bef04af5fb5d1b  tests/contracts/test_project_case_contract.py
8cfac7f0b98d740a17e5e9f9dd562a63becfb00cc7dcbd18d634a6bd2412dd92  changelog.d/project-case-v1.added.md
d3968bc1428224160f8638c43c365304ab0904c23c61103e2cb08a0e6474b133  docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md
b0ff7444ecb118f02f1d38e23369f4224082baee542454a0108a39aa56ed020c  docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md
82b30d2b34f00287b637a57fc209fdf07360a80003cccfc0ae0ff4b1f1c1d558  docs/DOLPHIN_3A_ASSURANCE_REVIEW_RECORD.md
a9596bbc9ab809617ece96c08e28b2dd7c3b89f5f8165b366a53d85f4d0f9cb0  docs/SESSION_HANDOVER_2026-08-29_2.md
```

## 16. Final D3A assurance closure

**ASSURANCE ACCEPTED** at exact pushed SHA
`77db342342e5ef62c922ac328d73a0b2e3e407d3`. No blocking, high, medium, or low D3A assurance
finding remained at that exact SHA.

D3A-ASR-01 remained closed. The reviewer exercised all 13 stable-identifier roles against 16
hostile forms: runtime refused all 208 and each generated Draft schema mode refused all 208. The
160-character boundary accepted, 161 characters refused, and Python-mode input was never
normalized.

D3A-ASR-02 remained closed. Sixty full-root runtime checks, 120 Draft checks, and 30 actual
Node/ECMAScript checks completed with zero mismatch. The inherited Dolphin 2 `SemanticVersion`
type remained unchanged.

D3A-ASR-03 closed. An independent 90-case role/unit/state matrix produced 70 intended acceptances,
20 intended refusals, and zero mismatches:

- resolved and explicit-missing `electrical_collection` accepted `MW`, `MWac`, `MWdc`, `MWp`, and
  `MVA`;
- `grid_interconnection` accepted `MW`, `MWac`, and `MVA`, while refusing `MWdc` and `MWp`;
- both electrical roles refused `USD`, `km`, `item`, and `MWh`;
- access-road, operations-facility, and other shared-facility roles retained their open unit
  boundary; and
- missing collection capacity closed through `/assets/2/capacity` with the matching identifier and
  expected unit.

Both Draft schemas structurally accepted all 90 role/unit/state cases. This independently confirms
the documented boundary: the conditional is runtime semantic validation and schema-only acceptance
is insufficient. A future web/API adapter must invoke `ProjectCase` domain validation.

Frozen object graphs, strict extra-field refusal, union discriminators, mandatory exact schema and
contract versions, sole-string Decimal/count JSON transport, native Decimal/integer normalized
Python mode, deterministic serialization under hostile Decimal contexts, and dump/schema/re-ingress
all passed. Validation- and serialization-mode Draft schemas were structurally valid and retained
47 definitions each.

## 17. Final independent assurance gate receipt

The reviewer independently obtained:

```text
targeted ASR, FX, topology and provenance:     130 passed
ProjectCase focused gate:                     330 passed
complete tests/contracts gate:                656 passed
inherited Dolphin 2 gate:                     386 passed
D2 plus ProjectCase coverage gate:            628 passed; 96.02% package total
ProjectCase module coverage:                  95.57%
validation/serialization Draft schemas:       valid; 47 definitions each
public package exports:                       63
Ruff check and format:                        passed
Black check:                                  passed
isort check:                                  passed
mypy --no-incremental:                        passed
compilation and import direction:             passed
packaging inclusion:                         passed
exact cumulative changed-file set:            passed; eight D3A files
excluded execution and authority surfaces:    empty
production jurisdiction-fallback scan:        passed; no Sri Lankan/LKA fallback
`connected_to` absence:                       passed
git diff --check:                             passed
final pre-record worktree/index/untracked:     clean
```

The contract remains a pure domain surface. Direct production imports are limited to the standard
library, Pydantic, and `.vocabulary`; no finance, evaluation, app, API, persistence, renderer,
engine, grade, release, or other execution dependency entered D3A.

## 18. Controlling final assurance boundary

The final production/test candidate is **ASSURANCE ACCEPTED** only at exact pushed SHA
`77db342342e5ef62c922ac328d73a0b2e3e407d3`. This disposition closes D3A-ASR-01 through -03 while
preserving the predecessor vetoes and evidence in sections 1-14.

Future web-adapter responsibilities remain explicit exclusions: duplicate-key refusal, parsed-
request normalization, structured transport-error mapping, request and collection limits,
serialization-schema publication, resource/indexing policy, and lightweight package topology. D3A
does not implement an endpoint or adapter. The acceptance is not professional or statutory
engineering assurance, external audit, lender or Board acceptance, achieved-grade authority,
package approval, release or deployment authorization, or `HOLD`-lifting authority.

Issue `#1110` remains `OPEN`, with 0 checked and 23 unchecked controls and its retained `HOLD`
language intact. This PERSIST-01 append changes documentation and therefore cannot itself inherit
the exact-SHA acceptance above. After the three authorized records are checkpointed as one
documentation-only commit, both independent reviewers must verify the new exact head, unchanged
production/export/test/changelog fingerprints, truthful documentation delta, current main
ancestry, and green CI before PR readiness.
