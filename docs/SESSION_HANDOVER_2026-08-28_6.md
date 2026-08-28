# Session handover - 2026-08-28, successor 6

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-28_5.md`](SESSION_HANDOVER_2026-08-28_5.md).
Successor 5 remains authoritative for the merged Dolphin 0 human template and DBPL artifact; its
predecessor remains authoritative for DBAY-FRC-001 and its source ledger. This record carries the
Dolphin 2 machine-contract implementation, its blocking independent reviews, remediation, final
exact-tree specialist acceptance and the
fail-closed Dolphin 3 startup. It changes no audit, lender, Board or release authority.

## 1. Fresh Dolphin 3 bootstrap - run this first

Start the task from the Codex project `DutchBay_EPC_Model`. Run this read-only preflight from the
protected primary checkout before creating a writing worktree:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
actual_repo="$(git rev-parse --show-toplevel)"
test "$(cd "$actual_repo" && pwd -P)" = "$(cd "$expected_repo" && pwd -P)"

export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
test -x "$DUTCHBAY_VENV/bin/python"
"$DUTCHBAY_VENV/bin/python" -VV

git status --short --branch
git worktree list
git branch --show-current
gh pr list --state open --limit 100 \
  --json number,title,isDraft,headRefName,headRefOid,mergeStateStatus,url
gh issue view 1110 --json number,state,title,body,updatedAt,url
```

Stop and reconcile exact ownership if the primary checkout is dirty, not on `main`, has an
unexpected writer/worktree, or issue #1110 no longer visibly retains the governing open/HOLD
boundary. Do not reset, stash, clean, delete or infer release from CI.

Only after that output is understood, synchronize and live-resolve Dolphin 2. No SHA in this
handover is a substitute for this check, and the next task must not invent or copy a final merged
SHA:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"

test "$(git branch --show-current)" = "main"
test -z "$(git status --porcelain)"
git fetch origin --prune
git merge-base --is-ancestor HEAD origin/main
git merge --ff-only origin/main
live_main_sha="$(git rev-parse origin/main)"
test "$(git rev-parse HEAD)" = "$live_main_sha"

d2_pr_number="$(gh pr list --state merged \
  --head codex/feasibility-report-machine-contract --limit 1 \
  --json number --jq '.[0].number')"
test -n "$d2_pr_number"
d2_merge_sha="$(gh pr view "$d2_pr_number" \
  --json state,mergeCommit \
  --jq 'select(.state == "MERGED") | .mergeCommit.oid')"
test -n "$d2_merge_sha"
git cat-file -e "$d2_merge_sha^{commit}"
git merge-base --is-ancestor "$d2_merge_sha" "$live_main_sha"

test -f analytics/feasibility_report_contract/package.py
test -f docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
test -f docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
test -f docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
test -f tests/contracts/test_feasibility_report_machine_contract.py

rg -q '^\*\*Domain final exact-tree disposition: ACCEPTED\.\*\*' \
  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
rg -q '^\*\*Assurance final exact-tree disposition: ACCEPTED\.\*\*' \
  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md

DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py

printf 'live_main_sha=%s\nd2_pr_number=%s\nd2_merge_sha=%s\n' \
  "$live_main_sha" "$d2_pr_number" "$d2_merge_sha"
git status --short --branch
```

Fail closed if the Dolphin 2 PR is absent, unmerged, not contained in synchronized `main`, either
specialist final disposition is not exactly `ACCEPTED`, or the five controlled files are absent.
Later merges may place `main` beyond the Dolphin 2 merge commit; ancestry, not equality with a
historical SHA, is the correct proof.

Then read, in this order:

1. `docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md` — D0 controlled 20-section human projection;
2. `docs/FEASIBILITY_REPORT_CONTRACT.md` and
   `docs/FEASIBILITY_REPORT_CONTRACT_SOURCES.md` — D1 normative contract and sources;
3. `docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md` — immutable pre-remediation veto receipt;
4. `docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md` — second veto, repairs and final exact-tree
   dispositions;
5. `docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md` — non-normative implementation boundary; and
6. this handover and its predecessor chain only as directed.

Before any Dolphin 3 edit, rerun the exact focused contract gate from synchronized `main`:

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-epc-model
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider \
  tests/contracts/test_feasibility_report_machine_contract.py \
  tests/contracts/test_contracts_v14_import_surface.py \
  tests/analytics/test_feasibility_sections.py \
  tests/analytics/test_run_modes.py \
  tests/lint/test_compile_changelog.py -q
```

Do not proceed if the independent domain and assurance rereview of the remediated exact Dolphin 2
tree is absent or non-accepting. Green implementer tests do not replace that disposition.

## 2. Authoring identity and protected state

Dolphin 2 was authored in:

- worktree `/Users/aruna/Downloads/dutchbay-wt-feasibility-report-machine-contract`;
- branch `codex/feasibility-report-machine-contract`; and
- historical starting base `22d342ac32b7921de9b5cde0156f483fecf26294`.

At this handover's authoring checkpoint, the Dolphin 2 changes are intentionally uncommitted for
independent rereview. They have not been pushed, submitted or merged. Therefore this document does
**not** state a final head, PR number or merged SHA. The bootstrap must resolve those live after
protected delivery. Protected `main`, finance, orchestration, wizard, renderers, adapters, issue
state, P01/P02/P03, F5-01/F5-02 and package release were not modified.

Startup used `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` and verified Python 3.12.13, this
worktree first on `PYTHONPATH`, and 72/72 active GWTF v3.0 rules. The canonical GWTF, CASPER,
CESSPIT and CCCDIR definitions were re-read. `config/feasibility_sections.yaml`, accessed only
through `analytics.feasibility_sections.load_feasibility_taxonomy()`, remains the sole source of the
20 section identities and order.

## 3. Independent veto and remediation disposition

The durable pre-remediation record is
[`docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md). Do not
rewrite it: its fingerprints and accepted-invalid cases describe the reviewed predecessor tree.
The second exact-tree review and consolidated remediation are separately preserved in
[`docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md`](DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md). Its
domain and assurance final exact-tree dispositions are both `ACCEPTED`, bound to the recorded
implementation/test hashes and limited to the D2 machine-contract scope.

That review concluded **DOMAIN VETO** and **ASSURANCE VETO** despite green conventional tests. The
accepted-invalid classes were: grade overclaim and unrelated grade authority; broken claim/evidence
links; weak `ASSURED` packs; N/A with stale output; future/expired/wrong-scope evidence; unrelated
or AI-signed review; weak/negative release authority; performed approval without decision; public
artifacts carrying restricted/no-publication sources; Fictionland receiving Sri Lankan sources and
defaults; source-free unknown-technology support; applicable sections without packs; empty passed
reconciliation; provenance-free derived input; and unitless numeric values.

The remediated D2 tree now provides durable positive, negative and property controls for those
classes. Its controlling boundary is:

- root v1 package grade is only `ungraded`, with no grade decision; section grade is only
  `ungraded` or `not_applicable`; non-sentinel grade vocabulary remains reserved for a future typed
  policy receipt;
- decisions have typed outcomes and exact report/run/section/claim/evidence/artifact/review or
  pack/version/grade/effective-period subjects; only positive outcomes can authorize;
- claim/evidence, section/output/input/source, derivation and pack/capability links are reciprocal;
- N/A forbids current production material and shares an exact positive scope decision with its
  capability;
- supported and assured packs enforce structural source, validation, limitation, scope, review,
  independence, decision, evidence and effective-period meaning;
- source/evidence cutoff, expiry, jurisdiction, technology, project boundary, period and
  authenticity are intrinsic checks;
- numeric values require units, derived inputs require derivations/backlinks and passed
  reconciliations require real operands;
- performed human roles, independent review, assurance and release require verified organized
  human/institution authority and exact decisions; and
- public artifacts require validated structured treatment of every enumerated restricted or
  no-publication source.

The second independent pass returned **DOMAIN VETO** and **ASSURANCE VETO** on L-S/N5-N8. The
consolidated repair additionally:

- binds every performed human role to the exact verified human performer as the positive decision
  authority and rejects software/AI authority or undeclared delegation;
- requires verified human/institution pack ownership, a distinct human reviewer from a distinct
  organization, and assurance authority independent from the producing actor and organization;
- refuses future-effective sources and requires exact-pack, relevant, usable evidence for pack
  review and assurance;
- adds required UTC `captured_at` snapshot semantics without misusing evidence cutoff as a universal
  review cutoff; report-bound lifecycle events cannot predate report creation, contained lifecycle
  events cannot postdate capture, and pack reviews may legitimately predate report identity;
- refuses release-authority metadata on `HOLD` and requires an assurance subject to name exactly the
  qualifying independent review set;
- requires exactly one honest record for every one of the six reconciliation families; and
- adds typed jurisdiction-to-governed-subject/disposition-pack mappings plus exact single-axis
  jurisdiction and technology packs. Controlled two-jurisdiction and wind+BESS fixtures prove
  contract expressiveness only; they do not implement D3 asset topology or claim a second real
  golden path.

This is the implementer remediation history. The specialists subsequently reran A-K/domain 1-11,
L-S/N5-N8 and U1/T1-T7 against the same final implementation/test hashes and recorded exact-tree
`ACCEPTED` dispositions in the separate rereview record. No audit or release `HOLD` is lifted.

The third exact-tree review added **DOMAIN VETO U1** and **ASSURANCE VETO T1-T7**. The final narrow
repair replaces `resolving_pack_id` with neutral `disposition_pack_id` and permits an honest scoped
one-axis unsupported-jurisdiction disposition only when every exact affected section is applicable,
`not_run_unsupported_jurisdiction` and carries one matching typed capability with consequence and
remedy. Supported and assured contribution routing is unchanged. Wrong-pack, wrong-jurisdiction,
Sri Lankan fallback, duplicate binding/subject mapping and silent-omission controls are durable;
the positive Fictionland package remains ungraded and held.

All four performed human roles now enforce report creation <= performance <= supporting decision <=
capture. Held and authorized artifacts enforce report creation <= artifact creation <= capture.
Validation and section-production event times cannot postdate capture. Pack assurance follows every
qualifying review completion and signed review decision. Authorized package release names the exact
current `distribution_ids` covering exactly the released artifacts; held release names none. These
event timestamps are distinct from prospective valuation, effective-until and expiry/control-horizon
dates. The evidence cutoff remains the source/evidence currency boundary.

The final independent reruns accepted this third repair: the frozen 28-case domain pass closed U1
and retained the N5-N8/original-domain refusals; the assurance pass completed the 143-test A-S
machine-contract surface and a separately selected 29-test T1-T7, U1, lifecycle and distribution
proof. Those specialist AI dispositions are
not statutory assurance or human professional sign-off. Live issue `#1110` and every audit,
lender, Board and release `HOLD` remain unchanged.

## 4. Dolphin 2 implementation surface

- `analytics/feasibility_report_contract/vocabulary.py` — strict frozen Pydantic v2 base,
  constrained identities/values and explicit orthogonal vocabularies;
- `analytics/feasibility_report_contract/records.py` — typed identities, scope, subjects,
  responsibility, packs, inputs, sources, outputs, claims, evidence, derivations, limitations,
  reviews, decisions, run/artifact/distribution/release registers and discriminated capabilities;
- `analytics/feasibility_report_contract/package.py` — immutable root, exact SSOT taxonomy,
  reciprocal reference graph, fail-closed packs, authority, evidence and distribution invariants;
- `analytics/feasibility_report_contract/__init__.py` and additive public re-exports through
  `analytics.contracts_v14`;
- `tests/contracts/test_feasibility_report_machine_contract.py` — explicit held 20-section fixture,
  A-K/domain 1-11 and L-S/N5-N8 counterexamples, positive multi-pack and chronology controls,
  U1/T1-T7 unsupported-jurisdiction, all-role lifecycle and release/distribution controls, property
  mutations, JSON Schema and round trip;
- `docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md` — three-role boundary, D0/D1 traceability, veto
  remediation and forward sightline; and
- `docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md` — exact second-pass predecessor fingerprints,
  second/third veto classes, consolidated repair and final specialist dispositions;
- `changelog.d/feasibility-report-machine-contract.added.md` — KPI-neutral additive change.

Digest fields remain typed identities only. D2 does not implement canonical hashing, grade
aggregation, orchestration, finance changes, adapter migration or release. The fixture uses lender
run posture while remaining honestly incomplete, `ungraded` and `hold`.

## 5. Verification receipts and VERIFY-01 rule

The consolidated second-remediation focused machine-contract gate passed:

```text
143 passed, 1 non-failing Hypothesis norecursedirs warning
```

The consolidated broadened focused gate passed:

```text
231 passed, 1 non-failing Hypothesis norecursedirs warning
```

The consolidated complete `tests/contracts` gate passed:

```text
171 passed, 1 non-failing Hypothesis norecursedirs warning
```

Final static and independent schema receipts were:

```text
ruff check: All checks passed
ruff format --check: 6 files already formatted
mypy: Success: no issues found in 5 source files
jsonschema Draft 2020-12 schema+instance: PASS
git diff --check: passed
```

These are actual completed local receipts, not projected results. The warning was caused by the
independent-review `.hypothesis` cache being present during collection; that exact task cache
was inventoried and removed after the gates. No `__pycache__` or `.pytest_cache` remains in the D2
package or contract-test tree.

Exact commands:

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-wt-feasibility-report-machine-contract
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider \
  tests/contracts/test_feasibility_report_machine_contract.py \
  tests/contracts/test_contracts_v14_import_surface.py \
  tests/analytics/test_feasibility_sections.py \
  tests/analytics/test_run_modes.py \
  tests/lint/test_compile_changelog.py -q

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider tests/contracts -q

"$DUTCHBAY_VENV/bin/ruff" check \
  analytics/contracts_v14.py analytics/feasibility_report_contract \
  tests/contracts/test_feasibility_report_machine_contract.py
"$DUTCHBAY_VENV/bin/ruff" format --check \
  analytics/contracts_v14.py analytics/feasibility_report_contract \
  tests/contracts/test_feasibility_report_machine_contract.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/mypy" analytics/feasibility_report_contract \
  tests/contracts/test_feasibility_report_machine_contract.py

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" - <<'PY'
import jsonschema

from analytics.feasibility_report_contract.package import FeasibilityReportPackage
from tests.contracts.test_feasibility_report_machine_contract import _build_package

schema = FeasibilityReportPackage.model_json_schema()
jsonschema.Draft202012Validator.check_schema(schema)
jsonschema.Draft202012Validator(schema).validate(
    _build_package().model_dump(mode="json")
)
print("jsonschema Draft 2020-12 schema+instance: PASS")
PY
git diff --check
```

The focused test itself independently validates the generated Draft 2020-12 schema and serialized
instance through `jsonschema`. GitHub required checks against the exact PR head remain merge
authority. Structural green cannot authorize grade or release.

Final remediated SHA-256 fingerprints, computed after the completed gates and cache removal, are:

```text
3bf271c3008b6eb3c4b08a1f8ec2311c6e6ebc026a9965a65b1e5975b0535760  analytics/contracts_v14.py
ce1240affc8a64ca6553415f14d49695af945b0e75d2ce0b0af375b07a57dc99  analytics/feasibility_report_contract/__init__.py
786557a839f353ba73cebd3d81902a944165c4ffdb0aa45fcb065e3db37f81c4  analytics/feasibility_report_contract/vocabulary.py
d130d63d8d165ea5d74db0a87a8bc453d2e51c9306ade65a3618218cc104d2e0  analytics/feasibility_report_contract/records.py
f4fef3b85a061cff5bb8ecf74d21fc2782a73a009226ddee1fa3d8adfa233454  analytics/feasibility_report_contract/package.py
426fa320f25998b4f917c5fd871d116e3eba73207df46e7b2121a2b5baba4e5b  changelog.d/feasibility-report-machine-contract.added.md
69827eb77903f3efbc5b88bf3bd8dceef42219529839d9ca67de6b720f1395d1  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
5a3edbb49798890dee3f78bcd9f71afd4f32fc67d78f6e2f87b675ff8ff50ffc  docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
b9e5d9e38137438db59406db82bce668513af629049017ddc6950baf4d498c2b  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
4fa17fcd294ef828eed6a0084f093b4e74db1945b06fd4f7864042d0e34f2e5f  tests/contracts/test_feasibility_report_machine_contract.py
```

The successor file cannot carry its own self-referential hash; compute and report its SHA-256 after
the final write. The first-review record's evidence and wording remain immutable. Its historical
`756fbe34...` review hash and the final `69827eb7...` whitespace-normalized delivery hash are both
recorded in the rereview receipt; the only byte change was removal of three trailing-space markers
required for a clean staged `git diff --check`.

## 6. Executable Dolphin 3 scope

After section 1 passes and independent D2 rereview is accepting, create one new worktree and
`codex/*` branch from the live synchronized `origin/main`. Keep Dolphin 3 additive and reversible:

1. Define a global `ProjectCase` contract for project identity, location, jurisdiction, technology
   **asset instances**, capacity/count/type, CAPEX, itemized OPEX, currency/price basis and explicit
   source/assumption bindings. Do not hide Sri Lankan values as defaults.
2. Define typed per-section result/disposition contracts that can carry existing v14 outputs into
   D2 section records without copying finance or domain mathematics.
3. Add a facade/mapper over `analytics.contracts_v14` and the existing
   `analytics.evaluation_v14.evaluate_with_overrides()` gateway. Preserve the current v14 engine;
   do not perform a big-bang rewrite or reverse the import direction.
4. Prove with narrow spies and fixtures that absent, unsupported, failed, degraded and executed
   paths map to explicit D2 dispositions, never stale output or inferred grade/release.
5. Keep grade aggregation, release policy, canonical hashing, adapters and product surfaces in
   later independently reversible dolphins unless a controlling D1 acceptance criterion expressly
   requires a smaller prerequisite.

Write the next PERSIST-01 successor before any long gate and retain concise VERIFY-01 receipts.
Checkpoint each coherent dolphin; do not leave the only source of truth in chat.

## 7. Forward delivery sightline and retained holes

D3 onward must preserve this order:

1. additive global `ProjectCase` and section-result facade over the existing v14 engine;
2. Golden Path 1 — real DutchBay/Sri Lanka produces the definitive complete report through all
   delivery modes;
3. Golden Path 2 — a second real jurisdiction/project validates jurisdiction and technology
   abstractions;
4. productization after semantic convergence — web wizard, client accounts, project persistence,
   report download, portfolio management, licensing and commercial operations; and
5. profile first, then extract only measured native kernels while retaining Python orchestration
   and the contract/audit boundary.

Current `technology_ids` are technology-type identifiers, not asset instances. D2 is not wired to
current orchestration or delivery adapters; Sri Lanka is not yet an assured pack; no second real
jurisdiction has validated the abstraction; canonical serialization/hashing remains later work;
and all live project, evidence, audit, lender and release `HOLD` states remain unchanged.
