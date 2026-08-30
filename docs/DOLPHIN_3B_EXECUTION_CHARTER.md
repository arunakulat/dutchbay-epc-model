# Dolphin 3B assessment and v14-binding execution charter

**Document status:** non-normative implementation charter, restart aid, and independent-review brief
**D3B-0 contracts:** `dutchbay.assessment_scope.v1`, `dutchbay.evaluation_request.v1`,
`dutchbay.base_scenario_identity.v1`, and `dutchbay.v14_binding_policy.v1`
**Initial base:** `cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce` on
`codex/d3b-v14-binding-facade`
**Normative authority:** D0 master template, DBAY-FRC-001 v1.0.0, the accepted D2 machine
contract, the accepted D3A `ProjectCase` v1 contract, and the canonical GWTF ruleset
**Release authority:** none

## 1. Mission and authority boundary

Dolphin 3B introduces the explicit assessment-intent and authored-scenario binding boundary between
one exact D3A `ProjectCase` revision and the existing v14 evaluation gateway. It is an additive
facade programme, not a rewrite of the evaluation engine. The D3B-0 slice defines pure input and
compatibility-policy contracts. The later D3B-1 slice may execute only a fully preflighted,
hash-bound, pre-authored v14 scenario through the one public gateway.

This charter cannot amend the controlling contracts or create assessment, professional, statutory,
lender, Board, release, deployment, or distribution authority. A requested target grade is an
assessment intention, never an achieved grade. A calculation, green test suite, successful engine
run, or `RunMode` never promotes D3A's neutral `declared` status to D2 `supported` or `assured` and
never lifts a `HOLD`.

The implementation is deliberately split:

1. **D3B-0:** strict transport-neutral assessment, authored-base identity, validation-receipt, and
   closed compatibility-policy contracts;
2. **D3B-1:** a separately reviewed executor/result seam with exactly one public v14 gateway call;
   and
3. **D3C:** package assembly only after D3B is independently accepted, merged, and protected `main`
   is resynchronized.

## 2. Governed startup and canonical frameworks

The work began from clean `origin/main` at
`cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce` in the dedicated worktree
`/Users/aruna/Downloads/dutchbay-wt-d3b-v14-binding-facade`. The governed runtime is the persistent
Python 3.12 environment at `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`; no worktree-local,
temporary, system, or alternate-project environment is permitted.

The canonical `go_with_the_flow_rules_v3_0_clean.csv` contained 72 active rules at dispatch and had
SHA-256 `3832a07d8adecb5692b871ac67b4b1d056f8d33b1c4a18669eb8d3e1767aa44f`. The ruleset, not this
charter, remains normative. The specialist pod was trained on the exact canonical meanings:

- **CASPER — Clear API Surfaces with Predictable Error Responses.** Optional capability failures
  remain call-time, bounded, and actionable. In the renewable-pipeline reading, CASPER also means a
  Contract-Assured Scenario Pipeline for Energy & Renewables: explicit contracts and predictable
  outcomes at every orchestration boundary. D3B must not convert an exception or malformed gateway
  payload into a success-like object.
- **CESSPIT — Config Explicit, Schema Strict, Pre-flight Integrity Tests.** Critical inputs,
  authorities, units, bases, dates, currencies, scenario identities, and unresolved states are
  explicit. No Sri Lankan, technology, economic, financial, or release default may silently fill a
  missing proposition. Structural JSON Schema validation does not replace relational runtime
  validation.
- **CCCDIR — Contracts Centralized, Compliance Documented, Import Relationships explicit.**
  Canonical v14 result contracts belong on `analytics.contracts_v14`; evaluation runs only through
  `analytics.evaluation_v14.evaluate_with_overrides`; import direction is tested and documented.
  The pure feasibility-contract package must not import the evaluator, finance, application,
  renderer, persistence, or web stacks.

The pod also operates under `WORKTREE-01`, `GOV-02`, `R23`, `R25`, `DELIVERY-01`, `DATA-01`,
`PERSIST-01`, `TEST-01`, and `THREAD-01`: one isolated writer, small reversible checkpoints,
protected-main delivery through a reviewed PR, independent oracles, durable handovers, and exact
governed-runtime selection.

## 3. Recruitment, roles, and additional training

### 3.1 D3B implementation lead

The implementation profile is a **principal Python/Pydantic and v14 integration engineer with
renewable-project and web-domain competence**. Required capabilities include:

- Pydantic v2 strict/frozen graph design, discriminated unions, exact non-normalizing lexical
  validators, validation-versus-serialization Draft 2020-12 schemas, deterministic JSON ingress,
  and hostile schema/runtime parity testing;
- renewable wind, solar, BESS, and hybrid capacity semantics, including AC/DC/apparent-power,
  nameplate/net/usable/export bases, storage MW/MWh/duration reconciliation, common/dedicated
  topology, cost periodicity, currency direction, price basis, and multi-subject jurisdiction
  routing;
- the existing v14 authored-scenario loader, schema guard, run manifest, result contracts, and sole
  public `evaluate_with_overrides` gateway;
- web/API boundary knowledge: exact wire identities, immutable request graphs, response-schema mode,
  deterministic bounded error contracts, cold-import safety, and a candid separation between domain
  validation and future HTTP concerns such as raw duplicate-key rejection, body limits, auth,
  persistence, rate limiting, and HTTP error mapping; and
- evidence-first delivery: no inference of support, assurance, grade, reliance, or release from
  computation or validation.

The additional training package emphasized import-cycle analysis, function-local public gateway
imports, one-call/zero-call spies, cause-preserving bounded execution failures, mutable legacy result
containment, exact Decimal-to-binary64 disclosure, authored-config reconciliation, hostile lexical
inputs, mutation/noninterference controls, and linear bounded register processing.

One root coordinator is the sole writer for the stable D3B-0 checkpoint. The implementation worker
does not self-approve. A renewable/hybrid feasibility-domain reviewer and a separate contract/web
assurance reviewer remain read-only until the tree is frozen, then independently bind their
dispositions to an exact candidate SHA.

#### D3B writer incident and corrected writer-lease protocol

The first delegated D3B writer failed twice to produce the checkpoint it had announced, then wrote
again after the root coordinator had taken over the lane. The failure was procedural rather than a
runtime or model-capability failure:

- progress commentary described an intended patch before `apply_patch` had actually completed; two
  interrupted turns therefore left no durable checkpoint;
- too much design was accumulated before the first small, verifiable write;
- the original authorization was treated as surviving an interruption, rather than as a revoked
  single-writer lease;
- after takeover, the worker correctly observed changed target hashes and a failed patch context,
  but attempted to reconcile the other writer's tree instead of stopping; and
- reviewer status traffic briefly resumed the interrupted worker because writer ownership was not
  encoded as a hard state machine.

The corrected protocol is mandatory for the remainder of D3B and for D3C:

```text
READ_ONLY
  -> explicit SHA-bound writer lease
  -> immediate branch/status/target-hash preflight
  -> one bounded allowlisted patch
  -> diff and focused verification
  -> verified durable checkpoint receipt
  -> WAIT_FOR_REVIEW

interruption | target drift | patch-context failure | unexpected writer activity
  -> READ_ONLY
  -> do not reconcile or continue
  -> require a fresh explicit writer lease
```

Every lease names one worker, worktree, branch, base SHA, phase, and exact file allowlist. An
interruption revokes continuity. Commentary must distinguish *preparing*, *patch applied*, and
*on-disk checkpoint verified*. A handoff must state HEAD, dirty paths, hashes, checks, concurrent
drift, and exact staged/committed/pushed state. Reviewers never write, and a coordinator takeover
requires an explicit stop plus worker acknowledgement before the coordinator mutates the tree.

### 3.2 D3C recruit held in reserve

The recruited D3C profile is a **principal Feasibility Package Orchestration and Report-Contract
Engineer**. It combines senior typed-Python/Pydantic practice with wind, solar, BESS and hybrid
domain knowledge; multi-jurisdiction subject routing; evidence/provenance and human-authority
boundaries; the controlled 20-section taxonomy; deterministic reconciliation; and web/report
delivery awareness.

D3C's later mission is narrowly held: consume exactly one D3A `ProjectCase`, one accepted D3B
scope/request, and one accepted D3B execution outcome; translate the existing v14 result into D2
section, capability, input/output/source, limitation, error, and reconciliation records; preserve
`None`, warnings, degradation, missing, unsupported, deferred, failed, and not-applicable states;
and emit an **ungraded, held** package. D3C may not rerun the engine, invent evidence, infer grade or
release, implement D4 canonical hashing/migrations, render a report, add an API, change finance, or
touch issue `#1110` or any `HOLD`.

D3C receives no writing worktree until D3B is merged and protected `main` is synchronized. It will
have its own sole writer plus independent domain and assurance reviewers. Before that lease is
issued, the D3C candidate must re-ingress this incident record, restate the state machine, and pass
a read-only collision drill covering an interruption, an unexpected target-hash change, a failed
patch context, and a coordinator takeover. The only passing response in every case is to stop,
return to read-only, preserve the observed tree, and request a fresh SHA-bound lease. A worker that
tries to merge or reconcile either tree does not receive the reins.

## 4. Background corpus and ingress order

Every D3B worker received the same source hierarchy, with later executable truth checked against
earlier normative intent:

1. canonical GWTF CSV and the pinned, unabridged CASPER/CESSPIT/CCCDIR definitions;
2. [`GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md`](GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md)
   (D0 controlled human projection);
3. [`FEASIBILITY_REPORT_CONTRACT.md`](FEASIBILITY_REPORT_CONTRACT.md) and
   [`FEASIBILITY_REPORT_CONTRACT_SOURCES.md`](FEASIBILITY_REPORT_CONTRACT_SOURCES.md) (D1);
4. the D2 charter, immutable veto history, remediation/rereview record, public vocabulary, records,
   package contract, exports, and hostile tests;
5. the D3A `ProjectCase` implementation, hostile tests, changelog, domain and assurance review
   chain, and latest D3A PERSIST handover;
6. the refreshed D0-D3A lineage note, which treats every prior assistant or memory statement as a
   claim to verify rather than an authority;
7. current `analytics.contracts_v14`, `analytics.evaluation_v14`, the authored-scenario loader,
   pipeline, schema guard, run manifest, app/web input seams, representative wind/hybrid/BESS
   scenarios, and their tests; and
8. repository `AGENTS.md`, the newest applicable session handover, and live branch/PR/issue state.

The D3C recruit receives this same corpus plus the final accepted D3B contracts, executor, result
surface, review records, exact-head CI receipt, and merged-main identity. It does not train from an
unaccepted D3B working tree.

## 5. D3B-0 contract boundary

### 5.1 `AssessmentScope`

`AssessmentScope` is strict, frozen, extra-forbid, versioned, and bound to one exact
`ProjectCaseReference` (`schema_id`, `contract_version`, `project_id`, `case_id`, and positive
revision). It keeps the following mandatory concepts distinct:

- exact scope identity and project boundary;
- exact technology bindings and jurisdiction-subject bindings, including exactly one site subject
  without treating it as a blanket tax, tariff, grid, accounting, or contract jurisdiction;
- project stage, intended audiences, intended uses, exact decision question and owner role;
- existing `RunMode` posture and a separately named requested target grade;
- evidence cutoff and valuation date, with no invented ordering rule;
- reporting currency, price nominality, price-basis identity and description;
- explicit exclusions; and
- an explicit materiality rule.

Identity-critical IDs, jurisdiction codes, currency codes, unit selectors, and SemVer tokens use
exact ASCII grammars with absolute ends and do not strip or Unicode-normalize input. Human
statements use a bounded, explicit cross-runtime blank/control-codepoint policy rather than
dialect-dependent `\s`; ordinary whitespace and accepted code points remain evidentially visible.
The 4,096-code-point boundary is tested with astral Unicode as well as ASCII. Runtime, both Draft
2020-12 modes, and an actual ECMAScript implementation agree on the hostile lexical matrix. JSON
transport is strict; normalized Python-mode dumps may be reingressed without claiming raw-body
duplicate-key protection.

### 5.2 Authored base and validation receipt

`BaseScenarioIdentity` binds an authored config ID/version, source-file SHA-256, resolved-config
SHA-256, declared authority, exact subject authorities, technology authorities, a complete
disposition for every closed authored domain (including lifecycle/timeline and COD ownership), and
a versioned `AuthoredScenarioValidationReceipt`. Each retained domain has typed subject/technology
authority routes; absent and refuse-if-present domains cannot carry routes. Dangling IDs, unrelated
authority sources, duplicate semantic domain/subject/technology routes, invalid subject/domain
pairs, unused subject or technology authorities, and missing domain dispositions fail inside the
base identity itself. Route uniqueness is independent of source ID, so two sources cannot become
indistinguishable owners. Each technology authority also declares one closed authored capability
(`wind_turbine`, `solar_pv`, `generic_generation`, or `storage`) without inferring it from a
free-form technology ID. The receipt
carries exact validator/control identities, requested validation modules, an explicit `pass`
assertion, and the public schema-guard and gateway identities. It is a caller-declared validation
statement, not independent assurance.

The resolved digest helper first proves that the root and every nested value use exact JSON-native
types. It refuses subclasses/enums, Decimal, tuple, `Path`, custom objects, non-string or subclass
keys, NaN, infinity, shared-container aliases, cycles, excessive depth, excessive containers or
scalars, excessive encoded text/numeric volume, and oversized integers before delegating to public
`analytics.run_manifest.config_sha256`. Traversal is canonical by exact key/index order and every
refusal carries a deterministic RFC 6901 path; insertion order cannot select a different first
error. Encoder failures become controlled validation failures, never raw recursion or
integer-conversion exceptions. The source-file digest, resolved-config
digest, and any later gateway run-manifest digest are different identities and are not D4 canonical
report hashes.

### 5.3 Closed compatibility policy and request

`V14BindingPolicy` contains only typed, discriminated compatibility assertions for scenario
identity, location, jurisdiction subjects, technology bindings, generation/storage capacity, cost,
and price basis. Callers cannot provide arbitrary dotted paths, reflection rules, model dumps,
generic overrides, or opaque deep merges. Every material `ProjectCase` category has exactly one
closed disposition: assert exact base compatibility, refuse before the gateway, or remain explicitly
outside v1 with no fallback. ProjectCase material cannot be labelled `retain_base_authority`; base
ownership is expressed only by the separate authored-domain register, so it cannot bypass a required
compatibility assertion. Assertion presence and dispositions must agree in enum declaration order,
yielding a deterministic first error. Within the request, every scoped jurisdiction subject and
technology binding has exact
base authority, retained-domain, and compatibility-assertion coverage; every generation technology
has a per-technology capacity route; every storage technology has power, energy, and duration
routes. D3B-1 must compare those declared element sets to the live exact ProjectCase and refuse any
unlisted live element before the gateway.

Capacity assertions name exact assets, selectors, units, electrical bases, capacity bases, and the
same authored capability as their technology authority. Their dimension matrix is closed. Project
and per-technology `_mw` selectors never accept a DC proposition. Wind turbine count/rating/total
selectors require `wind_turbine` and nameplate basis. A solar-PV DC nameplate in `MWdc` or `MWp`
binds only to the separately authored `resource.solar.dc_capacity_mw` selector; it never silently
becomes AC project/per-technology capacity. Storage power, energy, and duration map only to declared
AC MW/MWac, MWh/MWhac, and hour counterparts; a DC storage basis is refused until an authored
conversion basis exists. Costs name
non-overlapping complete line-ID sets, price-basis identity, exact USD reporting currency, and exact
one-time CAPEX or annual OPEX periodicity. Assertions are valid only when their corresponding
authored domains are retained. This declares a compatibility plan only; D3B-0 does not inspect a
live `ProjectCase` or scenario and does not execute it.

`EvaluationRequest` binds the exact same `ProjectCaseReference` across scope and policy, requires
cashflow and debt validation modules, and requires the request module set to equal the authored
validation receipt. It carries no achieved grade, evidence status, review, release, deployment,
distribution, or `HOLD` field.

## 6. D3B-1 held executor design

D3B-1 is not authorized by D3B-0 acceptance alone. Its implementation begins only after the
D3B-0 exact tree is independently accepted. The controlling design is conservative:

- accept a governed authored scenario identity/path under a closed authority mechanism, verify its
  file-byte digest, then call the public authored-scenario loader so its AEP, provenance, FX, and
  other authored-config guards run;
- independently bind the loaded finite JSON-native mapping to the declared resolved digest and
  compatibility policy;
- treat D3A technical, physical, cost, tariff, tax, FX, grid, accounting, financing, identity, and
  location values as exact compatibility assertions only. D3B-1 v1 does not rewrite them;
- never aggregate mixed MWdc/MWp/MWac/MW/MVA/storage values, derive AEP/capacity factor, reverse a
  currency quote, annualize periodic costs, choose BESS revenue from charging topology, or invent
  tariff, tax, debt, life, COD, depreciation, or evidence;
- permit at most the canonical scope-owned `run.mode` addition when absent. An existing canonical
  mode must match exactly; a top-level legacy `run_mode`, conflicting aliases, or unknown run keys
  is a zero-call refusal;
- require all redundant authored capacity, AEP, turbine, cost, and FX bases touched by the binding
  to reconcile. An unsupported redundancy is refused rather than partially overridden;
- make every preflight refusal a typed zero-call result; and
- make exactly one syntactic and runtime call to public
  `analytics.evaluation_v14.evaluate_with_overrides`, with the loaded raw config, the closed empty or
  run-mode-only overrides, explicit validation modules, and `return_full_result=True`.

Canonical D3B result types must live in, or be identity-preservingly exported by,
`analytics.contracts_v14`. Success and degraded success preserve the actual v14 result, warnings,
FX degradation, `None` values, and run manifest. Config and engine/protocol failures preserve a
bounded typed record and the real exception cause without leaking arbitrary config or exception
text. The existing mutable legacy `ScenarioResult` containment and exact authored-path authority
mechanism remain explicit D3B-1 design gates; this charter does not pretend they are solved by
D3B-0.

The executor remains outside the pure feasibility-contract package. Function-local public imports
and fresh-interpreter cold-import tests must preserve the existing source direction
`evaluation_v14 -> contracts_v14 -> feasibility_report_contract` without a partial-initialization
cycle. The repository's pre-existing `analytics.__init__` may still eagerly load evaluator/pipeline
modules during an ordinary package import; D3B records that inherited process-level limitation and
does not falsely claim that its direct pure module graph removes it.

## 7. Independent hostile-review model

The domain reviewer independently challenges:

- valid wind-only, storage-only, and common-POI wind+BESS compatibility without false rejection;
- fictional and multi-subject jurisdictions without Sri Lankan fallback;
- AC/DC/apparent-power, generation/storage, nameplate/net/usable/export, unitized/aggregate, and
  redundant-capacity mismatches;
- exact line-ID, cost periodicity, price basis, reporting currency, FX direction/date/precision, and
  incomplete/missing-input refusal;
- no charging-topology-to-revenue inference and no fabricated engine input; and
- no `declared` promotion, achieved grade, release, or `HOLD` implication.

The assurance reviewer independently challenges:

- raw JSON and strict Python ingress, exact identifiers/jurisdiction/unit/SemVer/date/currency
  tokens, unknown fields, both Draft 2020-12 modes, and deep immutability;
- closed assertion selectors, complete material dispositions, hash drift, invalid JSON-native
  values, mutation, global-state, resource, and noninterference seams;
- zero/one-call behavior, the sole public gateway import/call, exception cause preservation,
  malformed results, and import cycles;
- validation-schema versus serialization-schema truth, and the fact that raw duplicate keys,
  content type, request/body limits, authentication, persistence, HTTP mapping, and OpenAPI remain
  future adapter duties; and
- wheel/package inclusion and absence of finance, renderer, app, API, persistence, or private
  evaluation imports.

No reviewer may approve a moving tree. Each final disposition binds exact source/test fingerprints,
commit SHA, remote PR head, current base ancestry, worktree cleanliness, and exact-head CI.

### 7.1 Preserved precommit veto history

The first uncommitted D3B-0 freeze was rejected despite 81 focused tests passing. Its bounded
findings were a dialect-dependent human-text grammar, non-exact and resource-unbounded resolved
config hashing, an internally open authority/request graph, and dimensionally false capacity
selectors. The second freeze closed those families and passed 116 focused tests, but both
independent reviewers still vetoed it. Their controlling counterexamples were:

- ProjectCase material could change from exact assertion to `retain_base_authority`, including when
  the corresponding authored domain was declared absent;
- solar DC capacity could be accepted only by erasing `MWdc`/`MWp` to generic `MW`, while solar was
  also allowed to target wind-turbine fields;
- one semantic domain/subject/technology route could have two owners when only the source ID varied;
- material-category error selection varied by `PYTHONHASHSEED`;
- resolved-config error selection varied by dictionary insertion order and carried no field path;
  and
- live mutable module dictionaries/sets could change generated schemas or semantic policy after
  import.

The third candidate removed, rather than documented around, each second-freeze escape. Its focused
hostile suite reached 130 tests, including actual fresh-process hash-seed replay, both Draft 2020-12
modes, exact MWdc/MWp solar positives, every solar-to-turbine negative, semantic-owner duplication,
canonical pointer errors, and local mutation resistance. Both reviewers nevertheless vetoed that
exact freeze on two independent bounded defects:

- assertions for one generation asset could declare different electrical/capacity bases across
  redundant targets, including net totals paired with a nameplate turbine count; storage power,
  energy, and duration for one BESS could likewise disagree; and
- D3B request fields reused D3A `StableIdentifier` and `ProjectCaseSemanticVersion` aliases whose
  `WithJsonSchema` metadata retained mutable D3A dictionaries, so process-global mutation could
  change D3B's validation and serialization schemas without changing runtime acceptance.

The fourth candidate groups every generation assertion by ProjectCase asset ID and requires one
common electrical/capacity basis across totals and unitized selectors. It applies the same rule to
all storage power, energy, and duration assertions for one asset. D3B also defines private exact
identifier and SemVer aliases with immutable metadata that emits fresh schema dictionaries; D3A's
accepted public aliases and implementation remain unchanged. A fresh-process hostile test proves
that deliberately mutating both D3A metadata dictionaries changes D3A's own type-adapter schemas
but cannot alter either D3B schema mode. The focused suite is 136 tests, including the three exact
false accepts and a coherent five-route nameplate-wind positive. Green local gates remain supporting
evidence only; the fourth tree must receive fresh independent domain and assurance dispositions
before any commit, including replay of the complete D3A regression surface.

## 8. Delivery gates and persistence

D3B-0 must pass focused hostile tests, D3A and D2 contract regressions, complete contract tests,
Ruff check/format, Black, isort, mypy without incremental cache, compile/import checks, both Draft
2020-12 schema modes, public-export identity, cold imports, excluded-surface diffs, whitespace and
untracked-file controls. Both reviewers first inspect the frozen uncommitted five-file tree and
return a bounded no-blocker or veto handback. Only a no-blocker tree is staged and committed as one
checkpoint; both reviewers then rebind their final disposition to that immutable exact SHA before
D3B-1 begins.

D3B-1 receives a separate commit boundary and another complete independent domain and assurance
review. Only then may the topic be pushed, opened as a draft PR, synchronized with current
`origin/main`, and monitored to exact-head green CI. On 29 August 2026 the user explicitly removed
the former standing merge freeze. Therefore, after independent exact-head acceptance, a current
mergeable PR, and all required exact-head checks are green, the coordinator is authorized to squash
merge through the protected-branch workflow without asking for another merge go-ahead. After the
merge, remote and local `main`, protected checks, worktree cleanliness, and issue/HOLD state must be
independently reverified before the retrained D3C writer can receive a lease.

Durable checkpoints record exact hashes, tests, limitations, and live refs without retaining
high-volume runtime logs. Existing D0-D3A originals and veto history are never rewritten. Issue
`#1110` remained open with its 23 controls unchecked at D3B dispatch; its Board/lender/release HOLD
is outside this work and remains controlling.

## 9. Restart bootstrap

Resume only from the dedicated D3B worktree and governed persistent runtime:

```bash
set -eu
d3b_worktree="/Users/aruna/Downloads/dutchbay-wt-d3b-v14-binding-facade"
cd "$d3b_worktree"
test "$(pwd -P)" = "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
test "$(git branch --show-current)" = "codex/d3b-v14-binding-facade"

export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
test -x "$DUTCHBAY_VENV/bin/python"
"$DUTCHBAY_VENV/bin/python" -VV

git status --short --branch
git worktree list
DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
```

If the tree is dirty, inventory and preserve the exact files before any fetch, merge, staging, or
review. Never reset, stash, clean, or absorb unrelated work. Before a commit, re-fetch `origin/main`,
prove the topic's current base/ancestry, and reconcile any concurrent mainline merges under
`WORKTREE-01`; do not merge over an uncommitted checkpoint. The D3C hold remains in force after a
restart.

## 10. Explicit exclusions

D3B does not assemble the D2 20-section package, implement grade aggregation, render HTML/PDF/XLSX,
add FastAPI or another HTTP endpoint, publish OpenAPI, reject raw duplicate JSON keys, implement
auth/accounts/persistence, change finance or evaluation mathematics, create jurisdiction or
technology assurance packs, define D4 canonical report hashing/migrations, alter version/release
policy, modify issue `#1110`, or lift any audit, lender, Board, deployment, distribution, or release
`HOLD`.

Until exact-head independent acceptance and protected-branch delivery complete, D3B is an
implementation candidate only. Until the separately authorized merge completes, D3C remains a
trained recruit with no writing authority.
