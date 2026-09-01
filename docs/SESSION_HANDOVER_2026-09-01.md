# Session handover — 2026-09-01, successor 24

Durable `PERSIST-01` successor to
[`SESSION_HANDOVER_2026-08-31_2.md`](SESSION_HANDOVER_2026-08-31_2.md) (successor 23).
The predecessor chain remains authoritative for Dolphin 0 through Dolphin 3C-0, the earlier veto
history and the protected merges recorded there. This successor supersedes successor 23 where it
describes the D3C result facade as unbuilt, combines result translation with package assembly or
names a package-assembly worktree as the next writer surface.

This handover closes the thread that delivered D3C-1a, the strict result-only projection. It
records the independently accepted exact head, protected merge and post-merge state that the
implementation record could not predict. It prepares a new thread for D3C-1b only: reciprocal
ProjectCase/request/result/authority binding and candidate D2 records. D3C-2 package construction
and D3D grade/release policy remain separate later dolphins.

Nothing in this handover or the D3C-1a merge changes a finance result, achieved grade, evidence
disposition, professional conclusion, lender or Board decision, package-release state, deployment
authority, issue state or `HOLD`.

## 1. Bootstrap — run this first

Create the next task from the Codex project named `DutchBay_EPC_Model`. Do not create an unscoped
task and do not select another project. The SHA below is a dated ancestry receipt, not a substitute
for fetching and reconciling live state.

Run the identity and ownership preflight from the durable protected-main checkout:

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
dutchbay_venv=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv

cd "$expected_repo"
test "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)" = \
  "$(cd "$expected_repo" && pwd -P)"
test -x "$dutchbay_venv/bin/python"
"$dutchbay_venv/bin/python" -VV

git status --short --branch
git worktree list
git branch --all
gh pr list --state open --limit 100 \
  --json number,title,isDraft,headRefName,headRefOid,mergeStateStatus,url
gh issue view 1110 --json number,state,title,closedAt,updatedAt,url
```

Stop and reconcile any dirty tree, unfamiliar worktree, unexpected branch owner or ref movement.
Do not reset, stash, clean, delete or guess. Only from a clean protected `main` run:

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
dutchbay_venv=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv

cd "$expected_repo"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"

git fetch origin --prune
git merge-base --is-ancestor HEAD origin/main
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
git merge-base --is-ancestor 7e53b6cea00340701f01d4f4ea7bfce9134239a2 HEAD

DUTCHBAY_VENV="$dutchbay_venv" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$dutchbay_venv/bin/python" \
  dutchbay_bootstrap_rules.py

git log --oneline -10
git status --short --branch
```

The expected environment is Python `3.12.13`. The canonical rules receipt at this handover was
`73/73` active v3.0 rules, CSV SHA-256
`707ee9ba28a48536f3d145931afa87f2a053f234d6268c8cbebd5b385ead79d9`. Re-count and re-hash the
live file; do not treat those dated values as authority if the repository has coherently advanced.

Before this documentation-only handover branch, protected `main` and `origin/main` were clean and
equal at `7e53b6cea00340701f01d4f4ea7bfce9134239a2`, tree
`9686caf4ab89e397997cf2e3e5be623acf6bbd70`. That is PR `#1209`'s protected squash merge. This
handover is itself delivered through a later protected merge, so the next thread must expect live
`main` to be a descendant, not necessarily equal to that SHA.

## 2. Fresh corpus ingress before planning or writing

Read the following source documents in full from the newly synchronized checkout. Do not
substitute this handover, memory or a worker summary for them. Fresh ingress means D0, D1, D2 and
D3 every time, including the directions that a later charter cannot amend.

1. Governance, framework and continuity:
   - `AGENTS.md`;
   - the complete `go_with_the_flow_rules_v3_0_clean.csv`;
   - the unabridged canonical CASPER, CESSPIT and CCCDIR definitions loaded by the global project
     instructions;
   - this handover and its immediate predecessor; and
   - the current open-PR, worktree, branch, issue `#1110`, `VERSION` and protected-head state.
2. D0 and D1 founding contract:
   - `docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md`;
   - `docs/FEASIBILITY_REPORT_CONTRACT.md`;
   - `docs/FEASIBILITY_REPORT_CONTRACT_SOURCES.md`; and
   - the D0/D1 validation, audit and independent-review records those documents reference.
3. D2 machine contract:
   - `docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md`;
   - `analytics/feasibility_report_contract/records.py`;
   - `analytics/feasibility_report_contract/package.py`;
   - `analytics/feasibility_report_contract/vocabulary.py`;
   - `analytics/feasibility_sections.py`;
   - the D2 implementation, remediation and independent-review records; and
   - the complete D2 machine-contract, schema and coverage tests.
4. D3A project input:
   - `analytics/feasibility_report_contract/project_case.py`;
   - `tests/contracts/test_project_case_contract.py`; and
   - all final D3A implementation, independent, assurance and remediation-review records.
5. D3B scope and governed execution:
   - `docs/DOLPHIN_3B_EXECUTION_CHARTER.md`;
   - `analytics/feasibility_report_contract/assessment_scope.py`;
   - `tests/contracts/test_assessment_scope_contract.py`;
   - all final D3B-0 implementation, policy-root and independent-review records;
   - `analytics/feasibility_execution.py`;
   - `tests/contracts/test_d3b_execution_contract.py`;
   - `docs/DOLPHIN_3B1_EXECUTION_IMPLEMENTATION_RECORD.md`; and
   - `docs/DOLPHIN_3B1_INDEPENDENT_REVIEW_RECORD.md`.
6. D3C authority and result projection:
   - `docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md`;
   - `docs/DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md`;
   - `docs/DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md`;
   - `analytics/feasibility_report_contract/assembly_authority.py`;
   - `tests/contracts/test_d3c_assembly_authority_contract.py`;
   - `docs/DOLPHIN_3C0_ASSEMBLY_AUTHORITY_IMPLEMENTATION_RECORD.md`;
   - `analytics/feasibility_report_contract/taxonomy_identity.py`;
   - `analytics/feasibility_report_contract/engine_identity.py`;
   - `analytics/feasibility_report_contract/result_facade.py`;
   - `analytics/feasibility_result_projection.py`;
   - `tests/contracts/test_d3c_result_projection_contract.py`; and
   - `docs/DOLPHIN_3C1A_RESULT_PROJECTION_IMPLEMENTATION_RECORD.md`.
7. Later boundary, to prevent authority leakage into D3C-1b:
   - `docs/DOLPHIN_3D_GRADE_RELEASE_POLICY_CHARTER.md`.

Re-probe the D3A defect families in every new surface: topology and charging source,
capacity/electric basis, provenance/date binding, precision-preserving numerics, inferable
partial-state rejection, site identity, mandatory schema/version identity, provable claim states
and closed vocabulary. An implementer-authored green suite is not an independent oracle.

## 3. Live delivered state

| Increment | Protected result | Current disposition |
|---|---|---|
| D0 | `DBAY-GFR-MT-001` | Human twenty-section projection; unchanged |
| D1 | `DBAY-FRC-001` | Normative report contract; unchanged |
| D2 | `dutchbay.feasibility_report_package.v1` | Strict package, exact twenty-section topology and registers delivered |
| D3A | `dutchbay.project_case.v1` | Global ProjectCase contract delivered |
| D3B-0 | PR `#1204`, protected merge `3f83e14…` | Assessment scope and binding-policy declaration delivered |
| D3B-1 | PR `#1206`, protected merge `1d3b004…` | One preflighted public v14 execution seam delivered |
| D3C-0 | PR `#1207`, protected merge `411115c…` | Assembly-authority prerequisite delivered |
| D3C-1a | PR `#1209`, accepted head `cb9c410…`, protected merge `7e53b6c…` | Result-only projection delivered; no D2 authority |
| D3C-1b | not implemented | Next dolphin: reciprocal binding and candidate D2 records only |
| D3C-2 | not implemented | Later dolphin: ungraded held package assembly |
| D3D | charter merged in PR `#1203` | Grade/materiality/release policy remains separately unimplemented |

D3B-1 preserves one genuine `return_full_result=True` outcome containing annual rows, debt result,
metadata, warnings, degradation, `None`, exact engine manifest and legacy typed structures. D3C-1a
consumes that governed handoff without importing or calling the evaluator and without recomputing a
KPI.

D3C-0 supplies strict report/run identity, case/request/result digests, runtime receipt, D2 actors,
sources, packs, three byte-artifact metadata/digest bindings and a closed internal non-reliance
distribution profile. The bindings do not contain the governed bytes themselves. Its public
production authority catalogue remains intentionally empty. D3B-1's production
scenario-authority catalogue is also intentionally empty. Positive controlled-test authorities
prove plumbing only; they do not create production project, pack, evidence or release authority.
Any production catalogue entry is a separate reviewed dolphin.

At the cutoff used to author this handover:

- `VERSION` was `15.4.0`;
- issue `#1110` was `OPEN`, with `0` checked and `23` unchecked controls;
- its explicit Board/lender circulation `HOLD` remained intact; and
- the only open PRs were dependency PRs `#1176` and `#1178`.

Re-query all four facts. No engineering merge may derive or change them.

## 4. D3C-1a result and acceptance receipt

D3C-1a defines schema `dutchbay.section_result_facade.v1` version `1.0.0`. Its one public adapter
accepts exactly one immutable D3B `success` or `degraded_success` outcome and emits one strict,
frozen, structurally non-authoritative result projection. It does **not** accept `ProjectCase`,
`EvaluationRequest` or `AcceptedAssemblyAuthority` and cannot emit D2 package records, a package,
section completeness, evidence sufficiency, achieved grade, release, reliance or publication
authority.

The delivered boundary preserves exact origin identities, request/result/config digests, runtime
and manifest facts, ProjectCase Decimal lexemes, authored JSON-number lexemes, IEEE-754 bytes and
hex, structured FX context, warnings, degraded state, route states, all twenty taxonomy section
candidates, total upstream path disposition and bounded value-opaque unknown-key identities. It
performs no evaluator, finance, application, API, renderer, persistence, network or filesystem I/O.

Four candidate generations were independently rejected before the final acceptance. Their
failures covered incomplete origin reconciliation, invalid zero and balloon policy, dropped
numeric/FX facts, import-time I/O, manifest substitution, D3B-valid empty DSCR rejection, resource
bounds, nondeterministic hostile failures, control-bearing FX strings, serialization/schema
integer bounds and Python surrogate handling. The final exact head
`cb9c4104cd30ca8c327f155e7777204c61db7851` was accepted independently by the renewable/finance
domain challenger and the assurance/web-contract challenger with no remaining blocker.

The final fourth-correction receipts were:

| Gate | Accepted result |
|---|---:|
| Focused D3C-1a hostile/oracle suite | `126 passed` |
| Focused changed-module line/branch coverage | `100.00%` (`1020` statements, `434` branches) |
| Ruff / format / Black / isort / Bandit | pass |
| Narrow mypy over the four implementation modules | `Success: no issues found` |
| Complete `tests/contracts` gate | `1326 passed, 1 inherited warning` |
| Full governed ordinary suite | `7347 passed, 18 skipped, 23 warnings` in `718.77s` |
| Full governed coverage floor | `95.32%` (`32607` statements, `1527` missed; `>=95%` required) |

The independent hostile search exhausted all 2,048 surrogate code points across every public text
origin and observed 10,240 deterministic refusals, plus 4,096 direct-ingress refusals. It also
proved exact acceptance of every C0 control, U+D7FF, U+E000, valid non-BMP text and literal
backslash-u text. Numeric, JSON Schema, Python/JSON ingress, route, finance, determinism, I/O,
manifest and authority controls all passed at the same accepted head.

PR `#1209` became current with protected `main`, mergeable and clean. Its exact-head required
contexts passed, including `Test Summary`, `Verification receipts (VERIFY-01)`, `fastlane` and
`smoke`; all six test shards, coverage, code quality, security, CodeQL and audit-image checks also
passed. QSTS, report and stochastic qualification were correctly skipped by changed-path policy.
It squash-merged under `MERGE-01` as
`7e53b6cea00340701f01d4f4ea7bfce9134239a2` at `2026-08-31T23:55:51Z`.

The implementation record's opening “fresh exact-SHA review pending” status described its state
before those reviews and is superseded by this protected acceptance receipt. Its technical
boundary, rejected-candidate history and verification detail remain authoritative.

### 4.1 Successor-record review correction

The first frozen version of this successor record, exact SHA
`82439d38b50c589441cd4ba248f74ea0eff5d2d1`, was rejected by both independent reviewers before
push or PR. It omitted the original accepted D3B success and governed artifact bytes from D3C-1b,
despite requiring their content identities; described a caller-supplied accepted authority instead
of code-owned stable-ID selection; named a nonexistent taxonomy module; and would have left the
root `AGENTS.md` newest-handover pointer stale.

The domain reviewer proved the information-loss blocker constructively: accepted D3B successes
with different opaque metadata or annual-row `fx_rate` values can yield the same D3C-1a projection.
An equal projection cannot therefore stand in for accepted-success identity or the annual FX
predicate. This corrected successor preserves those counterexamples as mandatory D3C-1b controls,
requires in-memory artifact-byte verification, restores stable-ID authority selection, names the
live taxonomy loader and updates the root handover pointer atomically.

## 5. Next task analysis — D3C-1b only

The former combined D3C package scope is a whale. The next independently reversible Dolphin is
D3C-1b. Its exact computational inputs are one D3A `ProjectCase`, the matching accepted D3B-0
`EvaluationRequest` and one immutable accepted D3B-1 `D3BExecutionSuccess`. It must also receive:

1. one strict D3C-1a projection derived from that exact success, or a supplied projection proven
   graph-identical to a fresh call to the existing pure D3C-1a adapter on that success;
2. one stable D3C-0 authority ID resolved through the code-owned catalogue—never a caller-minted
   `AcceptedAssemblyAuthority`; and
3. one bounded in-memory byte payload for each of the three governed artifact roles: annual rows,
   debt result and FX curve.

The public production authority catalogue is intentionally empty, so production selection remains
blocked until a separately reviewed catalogue entry exists. D3C-1b may exercise a controlled
code-owned test catalogue to prove plumbing, but must not add a production authority or expose an
arbitrary-receipt injection seam.

D3C-1b first recomputes and requires exact reciprocal report, run and case identities; ProjectCase
and EvaluationRequest content digests; the canonical content digest of the exact accepted D3B
success; runtime receipt; engine manifest; and D3B/D3C origin facts. It derives or exactly
reconciles the D3C-1a projection against that same success. It hashes each supplied in-memory
artifact payload and requires the exact D3C-0 byte length, role and SHA-256 binding before emitting
any candidate. It does not follow an artifact locator or perform filesystem I/O.

No D3C-0 authority self-digest exists, and D4 package/payload hashing is deferred. D3C-1b must not
invent either. If the accepted-success digest lacks a reusable public primitive, the Dolphin must
define and independently verify a bounded, deterministic upstream-object content-identity
contract solely for the ledger's `d3b_execution_success` binding; it is not D4 package
serialization.

D3C-1b must preserve the exact directed FX quote, source/target currencies, observation date,
request price basis, source reference and conversion basis. A matching jurisdiction code, currency
pair or numeric rate is not enough.

The D3C-1a projection is intentionally lossy outside its reviewed routes. Independent review
proved that two distinct accepted D3B successes differing only in opaque `scenario_result.metadata`
can produce equal projections; the same is true when an annual-row `fx_rate` differs. The original
accepted D3B success therefore remains load-bearing. D3C-1b hostile tests must preserve both
counterexamples and prove that neither an equal projection nor matching projected identities can
substitute for exact accepted-success content identity and the ledger's annual FX predicate.

Only after every reciprocal check passes may D3C-1b emit candidate D2 records. Those candidates
must retain explicit unresolved completeness, evidence, review, professional-act and grade facts.
They are not a `FeasibilityReportPackage`, do not satisfy section completeness and confer no
release, reliance, lender, Board or publication authority.

D3C-1b must not:

- call the evaluator or finance, rerun an assessment, sum annual rows or recompute any KPI;
- create, accept or mutate a production scenario/assembly-authority catalogue entry;
- invent Sri Lankan or any other jurisdiction, tax, tariff, FX, permit or evidence defaults;
- convert engine-less sections into completed/applicable/adequately evidenced sections;
- silently discard warnings, limitations, opaque artifacts, unknown keys, unavailable routes,
  degraded state, `None`, unsupported state or deferred state;
- assemble `FeasibilityReportPackage` or its release object; or
- implement achieved grade, materiality or release policy.

### D3C-1b acceptance criteria

- Bind one and only one exact ProjectCase/request/D3B-success/projection/code-selected-authority
  set. Recompute the ProjectCase, request and accepted-success content digests; freshly derive or
  exactly reconcile the projection; and reject any reciprocal report/run/case ID, receipt, runtime,
  manifest or origin mismatch before candidate emission. Do not invent an authority self-digest.
- Accept the three governed artifact payloads as bounded in-memory bytes. Require exact role,
  byte-length and SHA-256 agreement with both D3C-0 byte bindings and D2 artifact records before
  candidate emission; never read a locator or accept metadata-only equality as byte proof.
- Resolve authority only by stable ID through the code-owned D3C-0 catalogue. Production remains
  blocked while that catalogue is empty; test-only positive plumbing must retain the same
  code-owned selection semantics and cannot become a caller-injection route.
- Apply the reviewed ProjectCase numeric table and precision policy from the D3C acceptance ledger.
  Preserve Decimal lexical identity, authored JSON lexemes and binary64 identity where the
  upstream contracts require them.
- Cover all twenty D0/D1/D2 taxonomy sections in SSOT order as candidates. Engine-less sections
  remain explicit, honest unresolved dispositions; presence of capacity, location, finance rows or
  a declared technology is not proof that their studies ran.
- Emit only the minimum candidate D2 record surface justified by reciprocal facts. Every record
  references its exact origin and cannot express package completeness, grade or release.
- Preserve structured FX direction/date/price basis/source provenance and refuse incomplete or
  reversed context. Do not convert a result statistic whose ProjectCase/request binding is absent.
- Preserve exact warnings, limitations, degraded status, opaque artifacts, unknown-key identities,
  unavailable/not-computed/not-representable route states and genuine not-applicable distinctions.
- Use strict frozen Pydantic v2 models, mandatory schema/version identity, closed vocabularies,
  bounded deterministic error codes/pointers, Draft 2020-12 validation and serialization schemas,
  Python/JSON parity, canonical dumps and exact round trips.
- Import no evaluator, finance, application, API, renderer or persistence surface. Perform no
  filesystem, environment, network or clock I/O and prove zero gateway/finance calls with spies.
- Add constructive and hostile tests, independent like-for-like finance/FX/identity oracles and
  negative controls proving each guard fires. Include same-projection/different-D3B-metadata and
  same-projection/different-annual-`fx_rate` counterexamples. An oracle copied from the
  implementation is not independent.

After D3C-1b is independently accepted and protected-main merged, start again from fresh live
`origin/main`. D3C-2 may then assemble one complete D2 `FeasibilityReportPackage` with
`achieved_grade = ungraded` and `package_release.status = hold`. D3D alone may later implement
grade ceilings, materiality and release aggregation. Do not pull either boundary forward.

## 6. Recruitment, harness and exact-SHA lease

Recruit three separated roles for D3C-1b:

- one exclusive principal/senior Python, Pydantic v2 and v14-integration writer/coordinator with
  web-contract knowledge and enough renewable/hybrid and project-finance fluency not to infer
  semantics from field names;
- one read-only renewable/hybrid feasibility-domain reviewer covering wind, solar, BESS, shared
  interfaces, resource/energy, cost, tariff, debt, FX/tax and non-financial gaps; and
- one read-only assurance/web-contract reviewer covering Python/JSON ingress, JSON Schema,
  bounded deterministic failure, alias/cycle/resource safety, reciprocal identity, provenance and
  structural no-rerun/no-import controls.

Before any writer lease, every worker freshly ingresses the corpus in section 2 and demonstrates
the complete GWTF, CASPER, CESSPIT and CCCDIR harness. The coordinator records each worker's scoped
pre-lease disposition before permitting a write. Reviewers never share the writer lease and never
edit the writer worktree.

Run the four D3C acceptance-ledger collision drills: interruption, unexpected target-hash drift,
failed patch context and coordinator takeover. The only passing response is to stop, preserve the
tree, return to read-only and request a new exact-SHA lease. A revoked writer never reconciles
another writer's work. No two live writers may hold the lease concurrently.

D3C-1a is controlling training evidence. Two writers stated progress without placing the claimed
corrections on disk; both leases were bounded, revoked and acknowledged. The coordinator then used
the documented stalled-writer takeover exception as sole writer. Four exact candidates were frozen,
reviewed and rejected before acceptance. Progress labels, chat summaries and passing tests are not
filesystem evidence: inspect paths and diff, bind every disposition to the exact SHA and preserve
rejected evidence before correction.

The first incomplete D3C-1a draft remains recoverable and must not be deleted:

- annotated tag: `recovery/d3c1a-contract-draft-2af8fee`;
- tag object: `f5fdcb7425a25867b5d6c9bc4903794605e9dd5f`;
- blob: `16bc7ae293063ba5804b13ba8af73c52f1f13010`;
- byte SHA-256: `2af8fee946e29ccd904f39d288cd05b1fb1a147fd258bb9d26238f251a17d667`;
- size: `32648` bytes.

## 7. Verification and review boundary

At minimum, record exact commands and results for:

- the persistent Python receipt and canonical `73/73` GWTF bootstrap;
- focused constructive and hostile D3C-1b tests with line and branch coverage;
- the complete current `tests/contracts` regression;
- inherited D2, D3A, D3B and D3C-0/D3C-1a gates selected by current scope;
- one genuine full-result oracle preserving annual rows, debt result, metadata, warnings, `None`,
  degradation, structured FX and the engine manifest;
- exact reciprocal ProjectCase/request/result/authority and directed-FX hostile matrices;
- zero-gateway and zero-finance-rerun execution spies and a structural forbidden-import guard;
- validation and serialization JSON Schemas, canonical dump validation and Python/JSON round trips;
- bounded depth, container, occurrence, text, integer, alias, cycle and hostile-order controls;
- Ruff check and format, Black, isort, complete governed mypy, Bandit and `git diff --check`;
- canonical-finance non-recomputation regression; and
- the complete exact-head GitHub rollup after the branch is current with protected `main`.

Read test bodies. A green count does not prove that a charter gate ran. New guards require negative
controls proving they fire. Write both independent exact-SHA review dispositions to durable
`docs/` records before merge; chat-only acceptance is insufficient for D3C-1b.

Every PR body must contain the canonical `Verification — receipts, not claims` table from
`.github/pull_request_template.md`, with exact commands/results or `not run — <reason>`.
PR `#1209`'s first VERIFY-01 run failed solely because its body omitted that table; the corrected
body passed without changing the reviewed head. Do not repeat the omission.

Under `MERGE-01`, squash-merge automatically when and only when both reviewers accept the same
exact head, the branch is current with protected `main`, GitHub reports it mergeable and clean and
every required check succeeds on that exact head with none failed, pending or unreported. After
merge, fast-forward durable `main`, prove it clean/equal to `origin/main`, verify merged bytes and
re-query issue `#1110`, `VERSION` and the `HOLD` boundary.

QSTS remains fail-closed. A D3C-1b PR unrelated to the governed grid-execution surface may have a
changed-path-policy skip; if its acceptance criteria depend on QSTS, the exact-head GitHub-hosted
`Grid Study` job must run and pass. A local or synthetic run cannot substitute.

## 8. Explicit deferrals and authority boundaries

D3C-1b does not construct `FeasibilityReportPackage`; aggregate section completeness; decide
applicability from inferred facts; implement grade ceilings, materiality or release policy; create
D4 canonical serialization or payload/section hashes; create HTML, API, PDF, DBPL or XLSX output;
replace `ReportContext` or the wizard; assure the Sri Lankan reference pack; complete Golden Path
1; add another jurisdiction/project; add accounts, persistence, downloads, portfolios or licensing;
rewrite the language/runtime or add native kernels; or implement F5-01, F5-02, P01, P02 or P03. It
changes no finance mathematics, KPI baseline, canonical scenario or `VERSION`.

The product remains a global commercial-feasibility platform. The Sri Lankan material is a
reference pack, never an inherited global jurisdiction, tax, tariff, permit, FX, accounting or
evidence default.

## 9. Worktree retirement and successor creation

After this handover is itself independently checked and protected-main merged, prove the following
worktrees clean before retiring them:

- `/Users/aruna/Downloads/dutchbay-wt-d3c1-result-projection` /
  `codex/d3c1-result-projection`; and
- `/Users/aruna/Downloads/dutchbay-wt-d3c1-handover` /
  `codex/d3c1-handover`.

PR `#1209`'s remote feature branch was absent at this cutoff. Re-query before branch cleanup. Keep
the recovery tag and its object/blob reachable. Do not delete it, the durable main checkout, the
persistent project folder or `.venv`, protected history, PR records or issue records.

Only after protected `main` contains this successor and the old paths are safely retired may the
next thread create one fresh writer worktree from current `origin/main`:

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
successor_worktree=/Users/aruna/Downloads/dutchbay-wt-d3c1b-context-binding
successor_branch=codex/d3c1b-context-binding

cd "$expected_repo"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git fetch origin --prune
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
test ! -e "$successor_worktree"
! git show-ref --verify --quiet "refs/heads/$successor_branch"
! git show-ref --verify --quiet "refs/remotes/origin/$successor_branch"
git worktree add -b "$successor_branch" "$successor_worktree" origin/main
git -C "$successor_worktree" status --short --branch
```

Do not create that worktree until read-only ingress, live-state reconciliation, recruitment,
collision drills and the exact D3C-1b scope disposition are complete.

## 10. Copy-paste prompt for the next new thread

```text
Start this task from the Codex project DutchBay_EPC_Model and use only the persistent governed
Python 3.12 environment at /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv. Work from the durable
repository /Users/aruna/Downloads/dutchbay-epc-model or a new dedicated worktree created from
current origin/main; do not create a replacement environment.

Read AGENTS.md and docs/SESSION_HANDOVER_2026-09-01.md completely and execute its Bootstrap — run
this first section. Re-query protected main, open PRs, worktrees, branches, issue #1110 and VERSION;
treat every recorded SHA as an ancestry receipt, not assumed current state. Freshly ingest the
complete canonical GWTF v3.0 CSV, unabridged CASPER/CESSPIT/CCCDIR meanings, D0, D1, D2, D3A,
accepted D3B-0, merged D3B-1, merged D3C-0, merged D3C-1a, both D3C design records, the binding D3C
implementation acceptance ledger and the D3D charter before planning or editing.

Recruit one exclusive senior Python/Pydantic/v14 writer, one separate read-only renewable/hybrid
feasibility-domain reviewer and one separate read-only assurance/web-contract reviewer. Require
fresh corpus ingress, collision drills and exact-SHA leases. Use the stalled-writer and four
rejected D3C-1a candidates as training evidence. Persist both final exact-head review dispositions.

Implement D3C-1b only. Receive one exact D3A ProjectCase, its exact matching EvaluationRequest and
the immutable accepted D3BExecutionSuccess. Derive the D3C-1a projection from that success or prove
a supplied projection graph-identical to a fresh pure projection. Resolve D3C-0 authority only from
its stable ID through the code-owned catalogue; a caller-minted receipt is not authority and the
production catalogue remains empty. Receive the exact three artifact payloads as bounded in-memory
bytes and require their role, length and SHA-256 bindings without reading a locator.

Recompute and require every reciprocal report/run/case identity, ProjectCase/request/D3B-success
content digest, runtime, artifact and manifest fact. Do not invent an authority self-digest or D4
package hash. Preserve exact directed FX quote/date/price-basis/source provenance. Only then emit
minimum candidate D2 records, with unresolved completeness, evidence, review, professional-act and
grade facts explicit.

Do not assemble FeasibilityReportPackage; that is D3C-2. Do not call the evaluator or finance,
recompute a KPI, invent a jurisdiction/default, infer engine-less work, populate a production
authority catalogue, implement grade/release policy or claim Golden Path 1. Preserve warnings,
limitations, degradation, None, opaque artifacts, unknown keys and every unavailable or deferred
state.

Use strict bounded deterministic Python/JSON contracts, independent oracles, constructive and
hostile controls, complete contract regression and the canonical PR receipts table. Drive the one
reversible PR through exact-head independent acceptance, current-base required CI and automatic
squash merge under MERGE-01.

Issue #1110, its 23 controls, VERSION 15.4.0, evidence sufficiency, professional, lender, Board,
release, deployment, publication and HOLD state remain outside engineering authority. Report live
discrepancies before mutating; never reset, stash, clean or delete unfamiliar work.
```
