# Session handover — 2026-08-31, successor 23

Durable `PERSIST-01` successor to
[`SESSION_HANDOVER_2026-08-31.md`](SESSION_HANDOVER_2026-08-31.md) (successor 22).
The predecessor chain remains authoritative for Dolphin 0 through Dolphin 3B-0, the D3B-0 veto
history and the protected merges recorded there. This successor supersedes successor 22 only where
it says Dolphin 3B-1 is unbuilt, Dolphin 3C-0 is absent or Dolphin 3C is still blocked on either of
those prerequisites.

This handover closes the thread that delivered the governed D3B-1 execution seam and D3C-0
assembly-authority boundary. It prepares the next new thread to implement the first real, held
D3C `FeasibilityReportPackage` without rerunning finance. It changes no finance result, achieved
grade, evidence disposition, professional conclusion, lender or Board decision, package-release
state, deployment authority, issue state or `HOLD`.

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
gh issue view 1110 --json number,state,title,updatedAt,url
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
git merge-base --is-ancestor 411115ca4fd4248b09319af52a5dab2f72750001 HEAD

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

At the authored cutoff, protected `main` and `origin/main` were clean and equal at
`411115ca4fd4248b09319af52a5dab2f72750001`, tree
`f3ebf409b3fe4fe9f5f81e6922fc9e5c933a637e`. This handover is delivered through a later
documentation-only protected merge, so the next thread must expect live `main` to be a descendant,
not necessarily equal to that SHA.

## 2. Fresh corpus ingress before planning or writing

Read the files below from the newly synchronized checkout. Do not substitute this handover, memory
or a prior worker summary for the source documents. Read each selected instruction or charter in
full before issuing a writer lease.

1. Governance and startup:
   - `AGENTS.md`;
   - the complete `go_with_the_flow_rules_v3_0_clean.csv`;
   - the unabridged canonical CASPER, CESSPIT and CCCDIR definitions loaded by the global project
     instructions; and
   - this handover and its immediate predecessor.
2. Founding contract:
   - `docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md` (D0);
   - `docs/FEASIBILITY_REPORT_CONTRACT.md` (D1, normative and not amendable by a charter);
   - `docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md`;
   - `analytics/feasibility_report_contract/records.py`;
   - `analytics/feasibility_report_contract/package.py`;
   - `analytics/feasibility_report_contract/vocabulary.py`;
   - `analytics/feasibility_report_contract/taxonomy.py`; and
   - the D2 machine-contract and coverage tests.
3. Project and execution inputs:
   - `analytics/feasibility_report_contract/project_case.py` and the final D3A review records;
   - `docs/DOLPHIN_3B_EXECUTION_CHARTER.md`;
   - `analytics/feasibility_report_contract/assessment_scope.py` and the final D3B-0 records;
   - `analytics/feasibility_execution.py`;
   - `docs/DOLPHIN_3B1_EXECUTION_IMPLEMENTATION_RECORD.md`;
   - `docs/DOLPHIN_3B1_INDEPENDENT_REVIEW_RECORD.md`; and
   - `tests/contracts/test_d3b_execution_contract.py`.
4. D3C controlling corpus:
   - `docs/DOLPHIN_3C_RESULT_FACADE_CHARTER.md`;
   - `docs/DOLPHIN_3C_CONTRACTS_DISPOSITION_RECORD.md`;
   - `docs/DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md`;
   - `analytics/feasibility_report_contract/assembly_authority.py`;
   - `docs/DOLPHIN_3C0_ASSEMBLY_AUTHORITY_IMPLEMENTATION_RECORD.md`; and
   - `tests/contracts/test_d3c_assembly_authority_contract.py`.

Re-probe the D3A defect families in every new surface: topology and charging source, capacity/electric
basis, provenance/date binding, precision-preserving numerics, inferable partial-state rejection,
site identity, mandatory schema/version identity, provable claim states and closed vocabulary. A
passing implementer-authored suite is not an independent oracle.

## 3. Live delivered state

| Increment | Protected result | Current disposition |
|---|---|---|
| D0 | `DBAY-GFR-MT-001` | Human twenty-section projection; unchanged |
| D1 | `DBAY-FRC-001` | Normative report contract; unchanged |
| D2 | `dutchbay.feasibility_report_package.v1` | Strict package, exact twenty-section topology and registers delivered |
| D3A | `dutchbay.project_case.v1` | Global ProjectCase contract delivered |
| D3B-0 | PR `#1204`, protected merge `3f83e14…` | Assessment scope and binding-policy declaration delivered |
| D3B-1 | PR `#1206`, topic `2b84477…`, protected merge `1d3b004…` | One preflighted public v14 execution seam delivered |
| D3C-0 | PR `#1207`, accepted head `058ac2b…`, protected merge `411115c…` | Assembly-authority prerequisite delivered |
| D3C package assembly | not implemented | Next dolphin; this is the controlling open boundary |
| D3D | charter merged in PR `#1203` | Grade/materiality/release policy remains separately unimplemented |

D3B-1 preserves one genuine `return_full_result=True` result containing annual rows, debt result,
metadata, warnings, degradation, `None`, exact engine manifest and legacy typed structures. D3C must
consume that governed handoff; it may not import or call the evaluator and may not recompute a KPI.

D3C-0 supplies strict report/run identity, case/request/result digests, runtime receipt, D2 actors,
sources, packs, three byte-bound result artifacts and a closed internal non-reliance distribution
profile. Its public production authority catalogue is intentionally empty. D3B-1's production
scenario-authority catalogue is also intentionally empty because no committed scenario currently
has the complete governed metadata. A positive controlled test authority proves plumbing only; it
does not silently create production project, pack, evidence or release authority. Any production
catalogue entry is a separate reviewed dolphin.

At final live verification before this handover was authored:

- `VERSION` was `15.4.0`;
- issue `#1110` was `OPEN`;
- `0` of its controls were checked and `23` were unchecked; and
- its explicit Board/lender circulation `HOLD` remained intact.

Re-query all four facts. No engineering merge is allowed to derive or change them.

## 4. Next implementation boundary

The next work is D3C result translation and held package assembly. It receives exactly:

1. one exact D3A `ProjectCase`;
2. the matching accepted D3B-0 `EvaluationRequest`;
3. one immutable accepted D3B-1 success or degraded-success outcome; and
4. one selected accepted D3C-0 assembly-authority receipt.

It emits one real `FeasibilityReportPackage` as a plumbing proof. The package remains:

```text
achieved_grade = ungraded
package_release.status = hold
```

The first implementation checkpoint is the immutable static section/field/unit/precision mapping
and pure result-facade translation. No package assembler may emit a package until that checkpoint's
constructive and hostile controls pass. If the mapping/facade checkpoint is independently useful
and the combined diff stops being dolphin-sized, deliver it as D3C-1, merge it, start again from
fresh protected `main`, and deliver assembly as D3C-2. Do not force both through as a whale.

The complete assembly acceptance boundary remains:

- exactly the twenty taxonomy IDs in `config/feasibility_sections.yaml` order;
- every section populated or carrying its exact honest disposition;
- all required actor, responsibility, pack, capability, input, source, output, claim, evidence,
  assumption, judgement, derivation, limitation, error, review-finding, review, decision,
  reconciliation, validation and distribution registers;
- exactly one reconciliation for each of `project_basis`, `energy`, `cost`,
  `revenue_tax_currency`, `debt` and `non_financial_gaps`;
- four separate report-scoped `prepared`, `checked`, `reviewed` and `approved` assignments visibly
  `not_performed` when no authorized human performed them;
- the explicit D3B-engine-manifest to D2-package-manifest bridge, with no semantic relabelling of
  request IDs, timestamps, digests or partial computation provenance;
- the ledger's static Section 2, Section 4 and Sections 10–20 routing;
- mandatory reviewed meaningful precision and static units for every carried numeric;
- exact duplicate-surface comparison with scalar/key type and binary64 sign identity;
- negative controls for defaulted zero, `None`, non-finite, unknown-key, synthetic, failed,
  missing, degraded, unsupported, deferred and genuine not-applicable states;
- no evaluator, finance, private pipeline, app, API, renderer or persistence import;
- an execution spy proving zero D3C gateway calls and zero finance reruns; and
- no investment recommendation, evidence-sufficiency conclusion, professional act, lender or
  Board authority, release authorization or Golden Path 1 claim.

The first package must expose engine-less sections honestly. It must not use capacity, finance rows,
location, a jurisdiction code or a declared technology as proof that resource, permit, grid,
construction, E&S, climate, sensitivity, Monte Carlo or optimization work ran.

## 5. Worker profile, retraining and lease

Use one exclusive writer/coordinator. The writer is a principal or senior Python/Pydantic v2 and
v14-integration engineer with enough web-contract knowledge to reason about JSON/Python ingress,
wire identity, schema parity, bounded hostile payloads, immutable API surfaces and later HTTP
adapter risks. The writer must understand renewable/hybrid feasibility and project-finance result
semantics well enough not to infer domain meaning from names.

Keep two separate read-only reviewers for the complex implementation:

- a renewable/hybrid feasibility-domain reviewer, including wind, solar, BESS, shared interfaces,
  resource/energy, cost, tariff, debt, FX/tax and non-financial gaps; and
- an assurance/web-contract reviewer covering Pydantic/JSON Schema, Python-versus-wire ingress,
  deterministic bounded errors, alias/cycle safety, provenance, reciprocal identity and structural
  no-rerun/no-import controls.

Before any writer lease, require fresh corpus ingress and the four collision drills from the D3C
acceptance ledger: interruption, unexpected target-hash drift, failed patch context and coordinator
takeover. The only passing response is to stop, preserve the tree, return to read-only and request a
new exact-SHA lease. A revoked writer never reconciles another writer's work.

The earlier D3C-0 writer incident is controlling training evidence:

- the first writer produced no patch after two delivery prompts while its internal status implied a
  patch existed;
- the replacement patch landed only as its lease was revoked and guessed or shadowed D2 fields;
- the coordinator preserved, inspected and rejected that patch rather than crediting it as
  delivery; and
- the accepted implementation uses the actual D2 types and reciprocal invariants.

Progress labels are not filesystem evidence. Before reporting delivery, prove the exact changed
paths, inspect the diff, run the checks and bind the result to the branch head.

## 6. Verification and review boundary

At minimum, record exact commands and results for:

- the governed environment receipt and canonical 73-rule bootstrap;
- focused constructive and hostile D3C tests;
- the complete current `tests/contracts` regression;
- the inherited D2 import/taxonomy/section/run-mode gate and its current superseding selection;
- a genuine full-result oracle preserving annual rows, debt result, metadata, warnings, `None` and
  the manifest;
- zero-gateway and zero-finance-rerun execution spies;
- the structural forbidden-import guard;
- Draft 2020-12 validation and serialization schemas, canonical dump validation and exact
  round trips;
- Ruff check and format, Black, isort, complete governed mypy and `git diff --check`;
- canonical-finance non-recomputation regression; and
- the complete exact-head GitHub rollup after the branch is current with protected `main`.

Read test bodies. A green test count does not prove a charter gate was exercised. New guards require
negative controls proving they fire. Write both independent exact-SHA review dispositions to
durable `docs/` records when they land; do not retain the only copy in chat context.

Every PR body must contain the canonical `Verification — receipts, not claims` table from
`.github/pull_request_template.md`, populated with exact commands/results or explicit
`not run - <reason>` declarations. PR `#1207` initially failed only because that table was omitted;
editing the body restored VERIFY-01 without changing the independently reviewed commit.

Under `MERGE-01`, squash-merge automatically when and only when:

- both independent reviewers accept the same exact candidate SHA;
- the branch is current with protected `main`;
- GitHub reports it mergeable and clean;
- every required check reports success on the exact head; and
- no required check is failed, pending or unreported.

After merge, fast-forward the durable `main`, prove it is clean and equal to `origin/main`, verify
the merged file bytes and re-query issue `#1110`, `VERSION` and the `HOLD` boundary.

## 7. Explicit deferrals

D3C does not implement achieved-grade aggregation, grade ceilings, materiality or release policy;
D4 canonical serialization or payload/section hashes; HTML, API, PDF, DBPL or XLSX migration;
`ReportContext` or wizard replacement; Sri Lankan pack assurance; Golden Path completion; a second
jurisdiction/project; accounts, persistence, downloads, portfolios or licensing; language/runtime
rewrites or native kernels; F5-01, F5-02, P01, P02 or P03. It changes no finance mathematics, KPI
baseline or `VERSION`.

The global product remains a global commercial-feasibility platform. A Sri Lankan scenario or
reference pack must never become an inherited global jurisdiction, tax, tariff, permit, accounting
or evidence default.

## 8. Closed-thread retirement state

This closing thread is required to retire these feature worktrees and local branches only after
this handover itself is protected-main merged and the target worktrees are proven clean:

- `/Users/aruna/Downloads/dutchbay-wt-d3b-v14-execution-seam-r2` /
  `codex/d3b-v14-execution-seam-r2`;
- `/Users/aruna/Downloads/dutchbay-wt-d3c0-assembly-authority` /
  `codex/d3c0-assembly-authority`; and
- `/Users/aruna/Downloads/dutchbay-wt-d3c-package-assembly` /
  `codex/d3c-next-thread-handover`.

The D3B-1 topic files were proven byte-identical to protected merge `1d3b004…`. The D3C-0 recovery
checkpoint `379d048…` changes only the predecessor `assembly_authority.py`; it is superseded by the
reviewed implementation on protected `main`, but the commit itself was not reachable from a remote
ref. Before retirement it was therefore preserved in the verified incremental Git bundle:

- path: `/Users/aruna/Downloads/DutchBay_D3C0_Recovery_379d048_2026-08-31.bundle`;
- contained ref: `379d048de40fb851133dc0c66bf30312c2bf9782`
  (`refs/heads/codex/d3c0-assembly-authority`);
- protected-history prerequisite: `1d3b004d8c1cc6ecfa9515d0a4b51ec876e986f8`; and
- bundle SHA-256: `dafd9b6ee83592799150c45d0467aa6725d6f6df559e02f59107b22531e33abc`.

The bundle must remain outside the retired worktrees. Verify or recover it from a repository that
contains the protected-history prerequisite with:

```bash
recovery_bundle=/Users/aruna/Downloads/DutchBay_D3C0_Recovery_379d048_2026-08-31.bundle
git bundle verify "$recovery_bundle"
git bundle list-heads "$recovery_bundle"
git fetch "$recovery_bundle" \
  refs/heads/codex/d3c0-assembly-authority:refs/heads/recovery/d3c0-379d048
```

The corresponding remote D3B-1 and D3C-0 feature branches were already absent at this cutoff.

Do not delete the durable main checkout `/Users/aruna/Downloads/dutchbay-epc-model`, the persistent
project folder `/Users/aruna/Downloads/Dutchbay_EPC_Model`, its `.venv`, protected history, PR
records or issue records. The final response from this thread is the receipt that retirement and
thread archival actually occurred; this file does not claim completion before those actions run.

After confirming the paths and branches above are absent, the next thread may create one fresh
writer worktree from current protected `origin/main`:

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
successor_worktree=/Users/aruna/Downloads/dutchbay-wt-d3c-package-assembly
successor_branch=codex/d3c-package-assembly

cd "$expected_repo"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
git fetch origin --prune
git merge --ff-only origin/main
test ! -e "$successor_worktree"
! git show-ref --verify --quiet "refs/heads/$successor_branch"
git worktree add -b "$successor_branch" "$successor_worktree" origin/main
git -C "$successor_worktree" status --short --branch
```

Do not create the writer worktree until the read-only ingress, live-state reconciliation, worker
retraining and scope decision are complete.

## 9. Copy-paste prompt for the next new thread

```text
Start this task from the Codex project DutchBay_EPC_Model and use only the persistent governed
Python 3.12 environment at /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv. Work from the durable
repository /Users/aruna/Downloads/dutchbay-epc-model or a new dedicated worktree created from
current origin/main; do not create a replacement environment.

Read AGENTS.md and docs/SESSION_HANDOVER_2026-08-31_2.md completely and execute its Bootstrap — run
this first section. Re-query protected main, open PRs, worktrees, branches, issue #1110 and VERSION;
treat every recorded SHA as an ancestry receipt rather than assumed current state. Freshly ingest
the complete canonical GWTF v3.0 CSV, the unabridged CASPER/CESSPIT/CCCDIR meanings, D0, D1, D2,
D3A, final D3B-0, merged D3B-1, merged D3C-0, both D3C design records and the binding D3C
implementation acceptance ledger before planning or editing.

Continue the next small D3C dolphin. First bind the immutable static section/field/unit/precision
mapping and pure result-facade translation to one accepted D3B-1 result. Do not permit package
assembly until that checkpoint's constructive and hostile controls pass. Then construct one real
FeasibilityReportPackage from one exact ProjectCase, its matching EvaluationRequest, one governed
D3B-1 success/degraded-success and one accepted D3C-0 authority. Do not call the evaluator, rerun
finance, recompute a KPI, invent a default, infer authority or silently populate the intentionally
empty production authority catalogues.

The first package must contain all twenty sections in SSOT order, every required D2 register,
exactly one record for each of the six reconciliation families, four visibly unperformed human
responsibility roles, the explicit engine-manifest-to-D2-manifest bridge, mandatory static units and
meaningful precision, achieved_grade=ungraded and package_release.status=hold. Preserve every
missing, failed, degraded, synthetic, unsupported and deferred state. Produce no HTML, API, PDF,
DBPL or XLSX surface and do not claim Golden Path 1.

Use one exclusive senior Python/Pydantic/v14 writer with web-contract knowledge, one separate
renewable/hybrid feasibility-domain reviewer and one separate assurance/web-contract reviewer.
Apply the collision drills and exact-SHA lease in the handover. Persist review work immediately.
Implementer tests are not an independent oracle. Drive each independently reversible PR through
the canonical receipts table, exact-head required CI and automatic squash merge under MERGE-01.

Issue #1110, all 23 controls, VERSION 15.4.0, achieved grade, evidence sufficiency, professional,
lender, Board, package-release, deployment and HOLD state remain outside engineering authority.
Report live discrepancies before mutating; never reset, stash, clean or delete unfamiliar work.
```
