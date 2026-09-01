# Session handover — 2026-09-01, successor 25

**Status:** corrected successor independently accepted; protected delivery pending

**Independent review:**
[`DOLPHIN_3C1B_HANDOVER_REVIEW_RECORD.md`](DOLPHIN_3C1B_HANDOVER_REVIEW_RECORD.md)

Durable `PERSIST-01` successor to
[`SESSION_HANDOVER_2026-09-01.md`](SESSION_HANDOVER_2026-09-01.md) (successor 24). The predecessor
chain remains authoritative for Dolphin 0 through Dolphin 3C-1a and the protected merges, rejected
candidates and recovery evidence recorded there. This successor supersedes successor 24 where it
describes D3C-1b as unimplemented or names the D3C-1b worktree as the next writer surface.

This handover closes the thread that delivered D3C-1b, the authenticated reciprocal context-binding
prerequisite. Fresh assurance review proved that D2 package validation still reads its taxonomy
YAML on first construction. The immediate next thread must therefore deliver one separate
import-safe D2 taxonomy-validation prerequisite. D3C-2 package assembly remains on pre-lease
`HOLD` until that prerequisite is independently accepted and protected-main merged. D3D grade,
materiality and release policy remains a separate later dolphin.

Nothing in D3C-1b, this handover, a green test, a review or an engineering merge changes a finance
result, evidence disposition, professional conclusion, achieved grade, lender or Board decision,
package release, deployment authority, publication authority, issue state or `HOLD`.

## 1. Bootstrap — run this first

Create the next task from the Codex project named `DutchBay_EPC_Model`. Use only the persistent
governed environment at `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`. Do not create an
unscoped task, select another project or create a replacement environment. The SHAs below are dated
ancestry and object-identity receipts, not substitutes for live reconciliation.

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
gh pr view 1214 \
  --json number,state,headRefOid,baseRefOid,mergeCommit,mergedAt,url
gh issue view 1110 --json number,state,title,closedAt,updatedAt,url
```

Stop and reconcile any dirty tree, unfamiliar worktree, unexpected owner or ref movement. Never
reset, stash, clean, delete or guess. Only from a clean protected `main` run:

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
git merge-base --is-ancestor 009f2ff22ffc00cf375d563beca1bbe6d1914e72 HEAD

DUTCHBAY_VENV="$dutchbay_venv" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$dutchbay_venv/bin/python" \
  dutchbay_bootstrap_rules.py

shasum -a 256 go_with_the_flow_rules_v3_0_clean.csv
git log --oneline -10
git status --short --branch
```

The expected environment is Python `3.12.13`. At this handover, the canonical bootstrap loaded
`73/73` active v3.0 rules and the CSV SHA-256 was
`707ee9ba28a48536f3d145931afa87f2a053f234d6268c8cbebd5b385ead79d9`. Re-count and re-hash the
live file; a coherent later change supersedes those dated values.

Before this documentation-only handover branch, protected `main` and `origin/main` were clean and
equal at D3C-1b squash merge `009f2ff22ffc00cf375d563beca1bbe6d1914e72`, tree
`f06401410c635708d554308a0be8a0e63f6a2416`. The accepted final candidate had the same tree even
though its pre-squash commit is not an ancestor of the merge. This handover is delivered by a later
protected merge, so the next task must expect a descendant rather than exact equality.

## 2. Fresh corpus ingress before planning or writing

Read these sources in full from the newly synchronized checkout. Do not substitute this handover,
memory or a worker summary for the controlling corpus. Fresh ingress means D0, D1, D2 and every D3
increment each time.

1. Governance and continuity:
   - `AGENTS.md`;
   - the complete `go_with_the_flow_rules_v3_0_clean.csv`;
   - the unabridged canonical CASPER, CESSPIT and CCCDIR definitions loaded by global project
     instructions;
   - this handover and its immediate predecessor; and
   - live protected-head, open-PR, worktree, branch, issue `#1110` and `VERSION` state.
2. D0 and D1:
   - `docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md`;
   - `docs/FEASIBILITY_REPORT_CONTRACT.md`;
   - `docs/FEASIBILITY_REPORT_CONTRACT_SOURCES.md`; and
   - their validation, audit and independent-review records.
3. D2 machine contract:
   - `docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md`;
   - `analytics/feasibility_report_contract/records.py`;
   - `analytics/feasibility_report_contract/package.py`;
   - `analytics/feasibility_report_contract/vocabulary.py`;
   - `analytics/feasibility_sections.py`;
   - all D2 implementation/remediation/review records; and
   - complete D2 contract, schema and coverage tests.
4. D3A, D3B and D3C prerequisites:
   - `analytics/feasibility_report_contract/project_case.py` and its tests/review records;
   - `docs/DOLPHIN_3B_EXECUTION_CHARTER.md`;
   - `analytics/feasibility_report_contract/assessment_scope.py` and its tests/review records;
   - `analytics/feasibility_execution.py`, its contract tests and final D3B-1 records;
   - `docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md`;
   - `docs/DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md`;
   - `docs/DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md`;
   - `analytics/feasibility_report_contract/assembly_authority.py` and D3C-0 records/tests;
   - `analytics/feasibility_report_contract/taxonomy_identity.py`;
   - `analytics/feasibility_report_contract/engine_identity.py`;
   - `analytics/feasibility_report_contract/result_facade.py`;
   - `analytics/feasibility_result_projection.py` and D3C-1a records/tests;
   - `analytics/feasibility_report_contract/context_binding.py`;
   - `tests/contracts/test_d3c_context_binding_contract.py`;
   - `docs/DOLPHIN_3C1B_CONTEXT_BINDING_IMPLEMENTATION_RECORD.md`;
   - `docs/DOLPHIN_3C1B_DOMAIN_REVIEW_RECORD.md`; and
   - `docs/DOLPHIN_3C1B_ASSURANCE_REVIEW_RECORD.md`.
5. Later boundary:
   - `docs/DOLPHIN_3D_GRADE_RELEASE_POLICY_CHARTER.md`.

Re-probe the D3A defect families in every new surface: topology/charging source,
capacity/electrical basis, provenance/date binding, precision-preserving numerics, inferable
partial-state rejection, site identity, mandatory schema/version identity, provable claim states
and closed vocabulary. An implementer-authored green suite is not an independent oracle.

## 3. Live delivered state

| Increment | Protected result | Current disposition |
|---|---|---|
| D0 | `DBAY-GFR-MT-001` | Human twenty-section projection; unchanged |
| D1 | `DBAY-FRC-001` | Normative report contract; unchanged |
| D2 | `dutchbay.feasibility_report_package.v1` | Strict package, exact section topology and complete registers delivered |
| D3A | `dutchbay.project_case.v1` | Global ProjectCase contract delivered |
| D3B-0 | PR `#1204`, protected merge `3f83e14…` | Assessment scope and binding-policy declaration delivered |
| D3B-1 | PR `#1206`, protected merge `1d3b004…` | One preflighted public v14 execution seam delivered |
| D3C-0 | PR `#1207`, protected merge `411115c…` | Code-owned assembly-authority prerequisite delivered; production catalogue empty |
| D3C-1a | PR `#1209`, protected merge `7e53b6c…` | Strict result-only projection delivered; no D2 authority |
| D3C-1b | PR `#1214`, accepted tree `f064014…`, protected merge `009f2ff…` | Authenticated reciprocal binding and candidate D2 records delivered |
| D3C-2 taxonomy-I/O prerequisite | not implemented | Immediate next dolphin: remove first-construction taxonomy filesystem I/O without changing taxonomy semantics |
| D3C-2 package assembly | not implemented; pre-lease `HOLD` | Later dolphin after prerequisite merge: one complete ungraded/held D2 package plumbing proof |
| D3D | charter merged in PR `#1203` | Grade/materiality/release policy remains separately unimplemented |

At this handover cutoff:

- `VERSION` is `15.4.0`;
- issue `#1110` is `OPEN` and its Board/lender circulation `HOLD` remains intact;
- the D3C-0 production assembly-authority catalogue is an empty immutable `MappingProxyType`;
- the public D3C-1b production bind and re-ingress paths therefore return
  `authority_not_found`; and
- the only open PRs are dependency PRs `#1176` and `#1178`.

Re-query every fact. An engineering merge cannot infer or change any of them.

## 4. D3C-1b protected result and acceptance receipt

D3C-1b defines `dutchbay.d3c_context_binding.v1` version `1.0.0`. Its public binder accepts one
exact D3A `ProjectCase`, matching D3B-0 `EvaluationRequest`, immutable accepted D3B-1 success, one
matching or freshly derived D3C-1a projection, one stable D3C-0 authority ID and three bounded
in-memory governed artifact payloads. Only the code-owned catalogue can select authority.

The contract recomputes ProjectCase/request/success identities; reconstructs the complete accepted
success on re-ingress; freshly reproduces the projection and contextual FX graph; reruns full
reciprocal identity reconciliation; and re-hashes the supplied annual-row, debt-result and FX-curve
bytes. Serialized authority, report, pack, artifact or digest/length copies cannot authenticate.
Direct candidate construction, `model_validate` and `model_validate_json` have no acceptance
capability. Public re-ingress must reselect authority by stable ID and receive the actual bytes.

The candidate retains exact cost and conversion context, explicit `MissingValue` provenance,
directed FX source/date/basis/timeline facts, every annual binary64 FX identity, complete warnings,
degradation and opaque/unknown state, and all twenty taxonomy sections in SSOT order. Root and
sections remain unresolved, unperformed, ungraded, held, non-reliant and unpublished. It is not a
D2 `FeasibilityReportPackage`.

Two frozen candidates were independently rejected before the accepted repair:

- original commit `2a377a5210bc045f7493f40f999146434d920cb5`, tree
  `23fb6d3b425f395dac4b391ed1158767c7b05426`, failed exact FX timeline/date/provenance,
  source-origin, cost/conversion/MissingValue context, hostile ingress and import isolation; and
- corrected commit `8e28be915c5479b0cabeb5b2f1feb14d08795945`, tree
  `2d718aea0a5b62fc906577bf466e916c85add999`, still allowed coherent reciprocal-origin and
  authority/report/pack/artifact graph forgery and checked raw byte bounds too late.

Their green tests did not override constructive counterexamples and do not transfer. The domain
and assurance reviewers independently accepted implementation commit
`875179fcae059ab3993a8bd1c7ebd2934949ff1b`, tree
`a8cbc90585547f22a620e4897fcc7d0520a3cc20`, against base
`e60ea866da6b77c1d9e39236c206140eae1af08d`. Both then rebound acceptance to final docs-only head
`1e557c038bdd87ab6e66d9421cdd79b74b8fb502`, tree
`f06401410c635708d554308a0be8a0e63f6a2416`, after proving all accepted code, test and changelog
blobs unchanged.

The final local receipts were:

| Gate | Accepted result |
|---|---:|
| Persistent Python / GWTF bootstrap | Python `3.12.13`; `73/73` rules; PASS |
| Focused D3C-1b constructive/hostile suite | `73 passed`; implementation `100.00%` statement/branch coverage |
| Import/scope/D3C-0 compatibility selection | `429 passed` |
| Complete `tests/contracts` regression | `1399 passed` |
| Ruff / Black / isort | pass; 742 Python files Black-clean; 4 governed isort skips |
| Complete governed mypy | zero issues in 269 typed source files and governed entry points |
| Bandit / dependency audit | no medium/high findings; no known vulnerabilities |
| Canonical-finance non-recomputation slice | `31 passed` |
| Full ordinary suite, four workers | `7420 passed, 18 skipped, 18 warnings` in `606.69s` |
| Full local coverage | `95.42%` (`33,498` statements; `1,533` missed) |

PR `#1214` was exact-head clean and mergeable on final head `1e557c0`. All 18 executed GitHub
checks passed, including six Python shards, coverage, Test Summary, required fastlane/smoke/receipt
contexts, code quality, security, CodeQL and audit-image build. Grid Study was correctly skipped by
the fail-closed changed-path policy. Stochastic and report qualification were skipped because their
workflow conditions permit scheduled/manual runs rather than ordinary PR runs. It squash-merged
under `MERGE-01` as `009f2ff22ffc00cf375d563beca1bbe6d1914e72` at
`2026-09-01T06:10:14Z`. The protected merge tree exactly equals the accepted final-candidate tree.

For historical transparency, rejected commit `8e28be9` suffered one native OpenDSS worker segfault
under repository-default `-n auto`; the exact test passed serially and the rejected SHA later passed
with four workers. The accepted replacement was freshly green with four workers, and exact-head CI
later passed all six shards. Treat high local worker counts as an environment limitation, not a
D3C result or a reason to hide the failed receipt.

### 4.1 Successor-candidate review correction

The first frozen version of this successor, commit
`0ecde08129b357013d8e6e4c87f69a902ccbbea0`, tree
`7e07190dd0a53e7b8ccab2892eac322cb86ce441`, was accepted by the domain reviewer but rejected by
the assurance reviewer before push or PR. The domain acceptance could not override an assurance
veto.

The rejected draft simultaneously required a genuine newly validated D2 package, zero filesystem
I/O and an initial lease that forbade edits to D2 package validation. Assurance demonstrated in a
fresh process that `FeasibilityReportPackage` calls `load_feasibility_taxonomy()` and the loader
uses `Path.read_text()` on `config/feasibility_sections.yaml`. A warm cache or fixture monkeypatch
would hide rather than close that trust boundary. The draft also incorrectly attributed all three
skipped qualification jobs to changed-path policy and did not clearly distinguish the authenticated
private test-catalogue seam from supported production ingress.

This corrected successor retains the no-I/O control, stages the known taxonomy-validation repair as
a separate prerequisite, corrects the CI receipt and confines private catalogue helpers to the
controlled test harness. No package-assembly writer lease exists yet.

## 5. Immediate next task — import-safe D2 taxonomy validation only

D3C-2 package assembly is on pre-lease `HOLD`. The immediate next dolphin repairs the known
first-construction filesystem dependency in D2 package validation and nothing else.

### 5.1 Known blocker and existing safe identity

`analytics/feasibility_report_contract/records.py` validates every `SectionRecord.section_id` by
calling `load_feasibility_taxonomy().section_names`.
`analytics/feasibility_report_contract/package.py` repeats that call while validating exact package
section order. On the first call, `analytics/feasibility_sections.py` reads
`config/feasibility_sections.yaml` through `Path.read_text()`. Therefore a genuine fresh-process D2
package construction currently performs filesystem I/O.

The already delivered `analytics/feasibility_report_contract/taxonomy_identity.py` is the intended
import-safe identity surface. It exposes the exact ordered `FEASIBILITY_SECTION_IDS`, the authored
YAML source path and the source SHA-256. Existing contract tests compare its ordered IDs and digest
to the live YAML. The YAML remains the single authored source; the identity module is a generated,
checksum-guarded projection for pure consumers.

Do not accept a warm `lru_cache`, an eager preload, a fixture monkeypatch or a copied test tuple as
closure. Those techniques only move or hide the filesystem read. Do not replace the general YAML
loader for consumers that genuinely need groups, statuses or full definitions. This prerequisite is
limited to the two D2 validators that need only canonical section identity/order.

### 5.2 Exact prerequisite scope and lease

The initial writer lease is five files only:

1. `analytics/feasibility_report_contract/records.py`;
2. `analytics/feasibility_report_contract/package.py`;
3. `tests/contracts/test_d3c2_taxonomy_io_prerequisite.py`;
4. `docs/DOLPHIN_3C2_TAXONOMY_IO_PREREQUISITE_RECORD.md`; and
5. `changelog.d/d3c2-taxonomy-io-prerequisite.changed.md`.

The implementation should make both D2 validators consume
`taxonomy_identity.FEASIBILITY_SECTION_IDS` at import-safe call time. It must preserve exact
validation behavior: every canonical ID is accepted, every absent/unknown/out-of-order/duplicate ID
is refused as before, and package section order remains exactly the authored twenty-ID order.

The focused test may read the YAML deliberately to prove source-path, SHA-256 and ordered-ID parity;
that is a build/contract guard, not package runtime. A separate fresh-process sentinel must patch or
intercept `Path.read_text` before importing/constructing the records and prove that constructing
canonical `SectionRecord` objects and one genuine D2 package performs no filesystem I/O. Read the
test body: a sentinel that runs only after a warm cache is not evidence.

Any need to edit `taxonomy_identity.py`, the authored YAML, the general taxonomy loader, D3A/D3B/
D3C contracts, finance, evaluation, production catalogues or release policy is unexpected scope
drift. Stop, preserve and request a new exact-SHA lease or a separate prerequisite; do not expand
this repair opportunistically.

### 5.3 Prerequisite acceptance criteria

- Fresh-process `SectionRecord` and `FeasibilityReportPackage` construction performs no filesystem,
  environment, network, persistence or clock I/O.
- `records.py` and `package.py` no longer import or call `load_feasibility_taxonomy`; both use the
  import-safe ordered identity projection.
- Authored YAML path, exact SHA-256 and ordered IDs remain independently parity-tested. A taxonomy
  edit without a regenerated identity projection fails closed.
- Canonical, unknown, duplicate, missing and out-of-order section controls prove the validation
  semantics did not drift.
- Complete D2 and current `tests/contracts` regressions pass, together with focused statement/
  branch coverage, import-isolation probes and `git diff --check`.
- Ruff/format, Black, isort, complete governed mypy, Bandit/dependency audit, finance
  non-recomputation, full ordinary suite/coverage and exact-head GitHub checks receive exact
  receipts.
- `VERSION 15.4.0`, canonical finance outputs, the authored YAML, production catalogues, issue
  `#1110` and every HOLD/non-reliance state remain unchanged.
- Both independent reviewers accept the same exact final SHA/tree/base before push. Green tests do
  not override a semantic or I/O counterexample.

After this prerequisite is independently accepted and protected-main merged, write a new successor
handover, start from fresh live `origin/main`, re-ingress the full corpus and only then issue a D3C-2
package-assembly writer lease.

## 6. Later D3C-2 package assembly boundary

Only after the prerequisite above is protected-main merged may D3C-2 begin as one reversible
package-assembly dolphin. It consumes only authenticated D3C-1b context and emits one genuine D2
`FeasibilityReportPackage` as a controlled plumbing proof. It does not repair, weaken or expand
D3C-1b in the same PR. Any newly discovered prerequisite is delivered separately.

### 6.1 Authentication boundary

A type-shaped `D3CContextBindingCandidate` is not authority. Before a writer lease, select and
record one supported ingress design:

1. call the public D3C-1b binder from the exact ProjectCase/request/accepted-success/projection,
   stable authority ID and three actual byte payloads; or
2. call the public authenticated D3C-1b re-ingress path on canonical candidate content with the
   same stable authority ID and freshly supplied bytes.

Raw candidate construction, `model_validate*`, `model_construct`, unchecked `model_copy`, a
caller-minted authority or copied artifact metadata is not authenticated ingress. Do not add a
public acceptance-capability parameter. Production package code must not import, re-export or
depend on underscore test helpers. The focused test harness may use the existing private immutable
test-catalogue bind/re-ingress seam solely to produce the held positive plumbing fixture. That seam
is authenticated within the controlled test harness but remains unsupported for production or
downstream ingress; it neither populates nor emulates production authority. Production stays
blocked while the code-owned D3C-0 catalogue is empty.

### 6.2 Exact output and register duty

The controlled positive path must create exactly one D2 package with:

```text
achieved_grade = ungraded
package_release.status = hold
run_manifest.payload_digest = None
```

It must contain exactly the twenty taxonomy sections in SSOT order. Every engine-less section is
present with an honest missing/deferred/unperformed disposition; none becomes complete,
adequately evidenced or not-applicable merely because a location, capacity, technology, topology
edge, finance row or successful computation exists.

Construct every D2 register required by `FeasibilityReportPackage`: actor/responsibility,
pack/capability, input/source/output, claim/evidence, assumption/judgement/derivation,
limitation/error, review finding/review, decision, reconciliation/validation and distribution.
Use an exact valid empty register where the contract permits no fact; never invent a decorative
record to make a register non-empty.

Create exactly one reconciliation record for each D1 family: `project_basis`, `energy`, `cost`,
`revenue_tax_currency`, `debt` and `non_financial_gaps`. A passed/failed record names the operands
actually compared. `not_applicable` cannot hide missing data or an analysis that should have run.

Carry four distinct report-scoped `ResponsibilityAssignment` records for `prepared`, `checked`,
`reviewed` and `approved`. Each remains `not_performed` with truthful reason and no actor,
performed-at timestamp or decision. Software, an AI agent, CI, PR review and merge are not human
professional acts.

### 6.3 Static mapping and manifest bridge

The static section and numeric tables in the binding D3C acceptance ledger remain controlling.
Map no scalar by parsing a field name, suffix, currency symbol, UI label or neighbouring value.
Every carried numeric has the reviewed static unit, precision source and acceptance predicate.
Series/schedules remain digest-bound artifacts. Unknown keys, defaulted zero, `None`, non-finite,
synthetic, failed, missing, degraded, unsupported, deferred and genuine not-applicable states must
remain distinguishable and must each have a firing negative control.

Bridge the D3B engine manifest to D2 exactly as the ledger specifies. In particular:

- `request_id` never becomes D2 `run_id` or `report_id`;
- the accepted D3C-0 receipt supplies exact report/run, packs, runtime, artifacts and held
  distribution facts;
- the evaluated/source/resolved config digests retain distinct identities;
- engine `git_sha` becomes D2 `code_commit` only after exact commit validation;
- engine generation time is not package creation time without independent proof;
- environment/dependency/dirty-worktree facts require the governed runtime receipt; and
- D4 serialization and payload/section hashes remain deferred, so D3C-2 leaves `payload_digest`
  `None`.

D3C-2 imports or calls no evaluator or finance surface, does no persistence/network/clock/locator
I/O, does not recompute an annual total, KPI, FX statistic, debt metric, IRR, NPV or DSCR and does
not render or serve the package.

### 6.4 Package-assembly acceptance criteria

- Authenticated ingress reselects code-owned authority and freshly verifies all three byte
  payloads; direct/type-shaped candidate ingress is refused.
- One genuine captured `return_full_result=True` success remains load-bearing without a gateway
  call and retains annual rows, debt result, metadata, warnings, degradation, `None`, legacy tuples
  and finite numeric mapping keys.
- Package report/run/case/request/success/projection/authority identities and every reciprocal D2
  reference reconcile exactly.
- Exactly twenty sections, every required register, all six reconciliation families and all four
  visibly unperformed human roles are present.
- All D2 validation and serialization schemas validate as Draft 2020-12; canonical dumps and exact
  supported round trips pass.
- Static units/precision and the complete ledger predicate matrix have independent positive and
  negative oracles. No oracle copied from the implementation is independent.
- Spies and structural guards prove zero evaluator/finance rerun, zero locator/filesystem/network/
  environment/clock I/O and import isolation.
- Root/sections/package remain unresolved or honestly dispositioned, ungraded, held, non-reliant
  and unpublished. No review, decision, evidence sufficiency or professional act is invented.
- `VERSION`, canonical finance outputs, production catalogues and issue `#1110` remain unchanged.
- Focused coverage, complete `tests/contracts`, inherited D2/D3 gates, Ruff/format, Black, isort,
  complete governed mypy, Bandit/dependency audit, finance non-recomputation, full ordinary suite,
  repository coverage and exact-head GitHub checks all receive exact receipts.

D3D alone may later implement grade ceilings, materiality, decisions and release aggregation. Do
not pull any D3D field or authority forward.

## 7. Recruitment, collision harness and prerequisite writer lease

Recruit three separated roles afresh for the taxonomy-validation prerequisite:

- one exclusive senior Python/Pydantic v2/D2-contract writer-coordinator with import-isolation and
  generated-identity experience;
- one read-only renewable/hybrid feasibility-domain reviewer proving the exact twenty-section
  identity/order and all section semantics remain unchanged; and
- one read-only software-contract/assurance reviewer covering fresh-process I/O sentinels,
  source-digest parity, Pydantic validation, import isolation and hostile taxonomy drift.

Before a writer lease, every worker freshly ingresses section 2 and demonstrates the complete GWTF,
CASPER, CESSPIT and CCCDIR harness. The coordinator records each scoped pre-lease disposition.
Reviewers never edit the writer worktree.

Run all four collision drills: interruption, unexpected target-hash drift, failed patch context and
coordinator takeover. The only passing response is stop, preserve, return to read-only and request
a new exact-SHA lease. A revoked writer never reconciles another writer's work; no two writers hold
the lease concurrently.

Use D3C-1a and D3C-1b rejection history as training evidence. Chat progress, object type and green
tests are not filesystem or authentication evidence. Freeze each candidate, inspect the actual
diff and bind both independent dispositions to the same exact SHA/tree/base before push. Preserve
rejected receipts; do not relabel them as success.

The exact five-file prerequisite lease is in section 5.2. It authorizes no D3C-2 package-assembly
module or fixture and no semantic change to D2 records. D3C-2 recruitment and its own new lease
occur only in a later thread after the prerequisite merge and a new successor handover.

## 8. Verification and delivery boundary

Record exact commands and results for the persistent Python receipt and `73/73` rules bootstrap,
focused taxonomy parity and hostile-I/O coverage, complete contracts, inherited D2/D3 selections,
fresh-process `Path.read_text` sentinels, validation/serialization schemas and canonical round-trip
controls, Ruff/format/Black/isort, complete governed mypy, security/dependency audit, finance
non-recomputation, full ordinary suite/coverage and `git diff --check`.

Every PR uses the canonical `Verification — receipts, not claims` table from
`.github/pull_request_template.md`. A check not run is stated with its reason. Exact-head CI remains
merge authority; a local green result cannot replace it.

Under `MERGE-01`, squash-merge only when both reviewers accept the same exact final head, the
branch is current with protected `main`, GitHub reports `MERGEABLE`/`CLEAN`, and every required
check succeeds on that exact head with none failed, pending or unreported. QSTS may skip only when
the fail-closed path classifier proves the prerequisite is unrelated. If live changed-path policy
classifies the D2 validation files as QSTS-relevant, the GitHub-hosted Grid Study must run and pass;
do not predict the classification from this handover.

After merge, fast-forward protected `main`, prove it clean/equal to `origin/main`, compare merged
trees/blobs to the accepted candidate, and re-query issue `#1110`, `VERSION`, production catalogues
and all HOLD boundaries.

## 9. Explicit deferrals

The immediate prerequisite does not implement a package assembler, change taxonomy content or
modify general taxonomy loading. It does not implement D3C-2 mapping, achieved-grade aggregation,
grade ceilings, materiality/release policy, D4 canonical serialization or payload/section hashes,
HTML/API/PDF/DBPL/XLSX output, `ReportContext` or wizard replacement, Sri Lankan pack assurance,
Golden Path completion, another
jurisdiction/project, accounts, persistence, downloads, portfolios, licensing, language/runtime
rewrites, native kernels, F5-01, F5-02, P01, P02 or P03. It changes no finance mathematics, KPI
baseline, canonical scenario or `VERSION`.

The product remains a global commercial-feasibility platform. Sri Lankan material is a reference
pack, never an inherited global jurisdiction, tax, tariff, permit, FX, accounting or evidence
default.

## 10. Worktree retirement and successor creation

After this handover is independently checked, protected-main merged and itself verified, prove the
following exact worktrees clean before retiring them:

- `/Users/aruna/Downloads/dutchbay-wt-d3c1b-context-binding` /
  `codex/d3c1b-context-binding`; and
- `/Users/aruna/Downloads/dutchbay-wt-d3c1b-handover` / `codex/d3c1b-handover`.

Delete only those local/remote branches after their merges are proven. Do not touch the unrelated
detached `.claude` worktree, recovery tags, durable main checkout, persistent project folder or
`.venv`, protected history, PR records or issue records.

Only after those paths are safely retired may the prerequisite thread create one fresh writer
worktree from current `origin/main`:

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
successor_worktree=/Users/aruna/Downloads/dutchbay-wt-d3c2-taxonomy-io-prerequisite
successor_branch=codex/d3c2-taxonomy-io-prerequisite

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

Do not create that writer worktree until live reconciliation, full ingress, recruitment, collision
drills and the exact five-file lease are complete. Do not create a D3C-2 package-assembly worktree
in the same thread.

## 11. Copy-paste prompt for the next new thread

```text
Start this task from the Codex project DutchBay_EPC_Model and use only the persistent governed
Python 3.12 environment at /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv. Work from the durable
repository /Users/aruna/Downloads/dutchbay-epc-model or a dedicated worktree created from current
origin/main; do not create a replacement environment.

Read AGENTS.md and docs/SESSION_HANDOVER_2026-09-01_2.md completely and execute its Bootstrap — run
this first section. Re-query protected main, open PRs, worktrees, branches, issue #1110, VERSION and
the production catalogues. Treat recorded SHAs as ancestry/object receipts, not assumed live state.
Freshly ingest the canonical GWTF CSV, unabridged CASPER/CESSPIT/CCCDIR meanings, D0, D1, D2, D3A,
D3B-0/1, D3C-0/1a/1b, both D3C design records, the binding acceptance ledger and D3D charter before
planning or editing.

Recruit one exclusive senior Python/Pydantic/D2-contract writer, one separate read-only
renewable/hybrid taxonomy-domain reviewer and one separate read-only software-contract/assurance
reviewer. Require fresh corpus ingress, collision drills and exact-SHA leases. Persist both final
exact-head review dispositions.

Implement only the import-safe D2 taxonomy-validation prerequisite in handover section 5. A fresh
SectionRecord or FeasibilityReportPackage currently calls load_feasibility_taxonomy(), which reads
config/feasibility_sections.yaml. Change only records.py and package.py so their identity/order
validators consume taxonomy_identity.FEASIBILITY_SECTION_IDS. Add one focused test, one durable
implementation record and one changelog fragment. Preserve the YAML as authored SSOT through an
independent path/SHA-256/ordered-ID parity test, and prove with a true fresh-process Path.read_text
sentinel that genuine record/package construction performs zero filesystem I/O. A warm cache or
monkeypatch after loading is not evidence.

Do not change taxonomy content or the general loader, assemble D3C-2, edit D3A/D3B/D3C, call the
evaluator or finance, populate production authority, implement D3D policy, render/serve a package
or change VERSION. After the prerequisite is independently accepted and merged under MERGE-01,
write a new successor and start D3C-2 package assembly only in a fresh later thread.

Use independent constructive and hostile oracles, full contract/regression gates and the canonical
PR receipts table. Drive the one reversible PR through exact-head independent acceptance, current-
base required CI and automatic squash merge under MERGE-01.

Issue #1110, evidence sufficiency, professional, lender, Board, release, deployment, publication and
HOLD state remain outside engineering authority. Report live discrepancies before mutating; never
reset, stash, clean or delete unfamiliar work.
```
