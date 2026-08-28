# Session handover - 2026-08-29, successor 7

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-28_6.md`](SESSION_HANDOVER_2026-08-28_6.md).
Successor 6 remains authoritative for the complete Dolphin 2 machine-contract design, veto and
remediation history, exact production fingerprints, accepted scope and retained limitations. This
record carries the post-restart recovery, coverage-gate repair, protected-delivery boundary and the
fresh executable Dolphin 3 startup. It changes no audit, lender, Board, grade or release authority.

## 1. Bootstrap - run this first

Create the new task from the Codex project `DutchBay_EPC_Model`. Run this read-only inventory from
the protected primary checkout before creating a Dolphin 3 branch or worktree:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
test "$(pwd -P)" = "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"

export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
test -x "$DUTCHBAY_VENV/bin/python"
"$DUTCHBAY_VENV/bin/python" -VV

git status --short --branch
git worktree list
git branch --show-current
gh pr view 1188 \
  --json number,state,headRefName,headRefOid,mergeCommit,mergedAt,mergeStateStatus,url
gh issue view 1110 --json number,state,title,body,updatedAt,url
```

Stop and reconcile exact ownership if the protected checkout is dirty or not on `main`, an
unexpected writer or worktree exists, PR #1188 is not merged, or issue #1110 no longer visibly
retains its open controlled audit/release boundary. Do not reset, stash, clean, delete or infer
release authority from CI.

After the inventory is understood, synchronize `main` by fast-forward only and prove the live
Dolphin 2 merge is contained in it:

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-epc-model
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"

test "$(git branch --show-current)" = "main"
test -z "$(git status --porcelain)"
git fetch origin --prune
git merge-base --is-ancestor HEAD origin/main
git merge --ff-only origin/main
live_main_sha="$(git rev-parse origin/main)"
test "$(git rev-parse HEAD)" = "$live_main_sha"

d2_state="$(gh pr view 1188 --json state --jq .state)"
test "$d2_state" = "MERGED"
d2_merge_sha="$(gh pr view 1188 --json mergeCommit --jq .mergeCommit.oid)"
test -n "$d2_merge_sha"
git cat-file -e "$d2_merge_sha^{commit}"
git merge-base --is-ancestor "$d2_merge_sha" "$live_main_sha"

required_files=(
  analytics/feasibility_report_contract/package.py
  docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
  docs/SESSION_HANDOVER_2026-08-28_6.md
  docs/SESSION_HANDOVER_2026-08-29.md
  tests/contracts/test_feasibility_report_machine_contract.py
  tests/contracts/test_feasibility_report_machine_contract_coverage.py
)
for required_file in "${required_files[@]}"; do
  test -f "$required_file"
done

rg -q '^\*\*Domain final exact-tree disposition: ACCEPTED\.\*\*$' \
  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
rg -q '^\*\*Assurance final exact-tree disposition: ACCEPTED\.\*\*$' \
  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md

DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py

printf 'live_main_sha=%s\nd2_merge_sha=%s\n' "$live_main_sha" "$d2_merge_sha"
git status --short --branch
```

Run the complete focused machine-contract and import/taxonomy gate from synchronized `main`:

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-epc-model
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider \
  tests/contracts/test_feasibility_report_machine_contract.py \
  tests/contracts/test_feasibility_report_machine_contract_coverage.py \
  tests/contracts/test_contracts_v14_import_surface.py \
  tests/analytics/test_feasibility_sections.py \
  tests/analytics/test_run_modes.py \
  tests/lint/test_compile_changelog.py -q
```

Fail closed before Dolphin 3 if protected delivery is absent, either specialist disposition is not
exactly `ACCEPTED`, the files are missing, governed ingress fails, or the focused gate is red.
Later merges may place `main` beyond the Dolphin 2 merge commit; ancestry rather than equality with
a historical SHA is the correct proof.

Then read, in order:

1. `docs/GLOBAL_FEASIBILITY_REPORT_MASTER_TEMPLATE.md` - Dolphin 0 human report architecture;
2. `docs/FEASIBILITY_REPORT_CONTRACT.md` and its source ledger - Dolphin 1 normative contract;
3. `docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md` - immutable pre-remediation veto receipt;
4. `docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md` - repairs and accepted exact-tree reviews;
5. `docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md` - Dolphin 2 implementation boundary;
6. successor 6 for the full technical handover; and
7. this recovery/delivery successor.

## 2. Restart recovery and PERSIST-01 receipt

The local machine restarted while the coverage-only repair was uncommitted. Recovery did not rely
on chat state. The protected primary checkout, isolated Dolphin 2 worktree, local branch, remote
branch and sole untracked test file were inventoried before mutation. The protected primary was
clean and already synchronized with `origin/main` at
`22d342ac32b7921de9b5cde0156f483fecf26294`. The existing PR #1188 remained open at pre-amendment
head `60cf735e28148b6a8f23de5446974a708a6e3724`; its only red required result was the aggregate
coverage-dependent `Test Summary`.

The recovered test file was 42,656 bytes and 1,137 lines at SHA-256
`e92457e51532f53a03a11f5b51bd1022cdf0ac550acd4451751cbfae701c4866`. It reproduced 292 passing
machine-contract tests and 95.58% contract-only coverage before the final narrow controls were
added. The final coverage-control file is 1,233 lines at SHA-256
`33dc75c941f08f230dd65d46fa4c92f68338c2e466c635c62cf863543b4878e5`.

The final additions are executable semantic negatives for reciprocal evidence, derived-input,
output/derivation and exact jurisdiction/technology source-scope bindings. They contain no
`model_construct`, validator bypass, monkeypatch, skip/xfail, no-cover pragma, coverage exclusion,
denominator manipulation or production change. The previously accepted production, original-test,
charter, changelog and independent-review fingerprints remained byte-identical to successor 6.

## 3. VERIFY-01 recovery receipts

The recovered exact tree passed:

```text
Original plus coverage-control machine-contract tests: 298 passed
Complete tests/contracts gate: 326 passed
Broadened contract/import/taxonomy gate: 386 passed
Live-path integration selection: 106 passed

Contract-only coverage:
  package.py:    769 statements, 67 missed,  91.29%
  records.py:    826 statements,  0 missed, 100.00%
  vocabulary.py: 211 statements, 0 missed, 100.00%
  package total: 1,809 statements, 67 missed, 96.30%
```

The tests execute 178 statements that were missed at the original 245-miss contract baseline. That
is 34 statements beyond the estimated 144-line aggregate-CI deficit that produced the original
94.48% result. GitHub exact-head CI remains the merge authority; local coverage is evidence for the
repair, not permission to bypass CI.

Static and schema receipts passed: Ruff check and format, Black, isort, mypy on the accepted source
surface and new test, Draft 2020-12 schema plus serialized fixture validation, and `git diff
--check`. A combined mypy invocation that names both test files aliases the imported fixture module
under two names; the established target set and the new file pass separately.

Independent post-restart rereview returned:

- **DOMAIN ACCEPTED** on the exact recovered fingerprints after the 39-case domain replay, all 298
  machine-contract tests and all 326 contract tests; and
- **ASSURANCE ACCEPTED** after full inspection of all 155 new cases, the 298-test gate, coverage,
  static and schema checks, with before/after production and review-record hashes exact.

Those are specialist AI review dispositions limited to the Dolphin 2 machine contract. They are not
human professional recruitment, statutory assurance, achieved-grade authority, lender acceptance
or package-release authority. They lift no `HOLD`.

## 4. Protected delivery and cleanup boundary

PR #1188 is the sole Dolphin 2 delivery vehicle. The original exact-head CI passed all six test
shards, Grid Study, Code Quality, Security, CodeQL, FX, fastlane, smoke, audit-image and VERIFY-01
jobs; only the aggregate 95% coverage gate failed at 94.48%. The coverage-control amendment must be
committed and pushed to that branch, and every required check must rerun against the new exact head.
The user's authorization is to merge only when that exact head is fully green.

After an authorized green merge, fast-forward protected `main`, prove the merge commit is its
ancestor, rerun the focused bootstrap gate, inventory ignored/tracked state, and only then remove:

- worktree `/Users/aruna/Downloads/dutchbay-wt-feasibility-report-machine-contract`;
- local branch `codex/feasibility-report-machine-contract`; and
- the remote topic branch if the merge workflow did not already remove it.

Do not remove or recreate `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`; it is the shared
governed environment. Do not alter issue #1110 or any audit/release control as cleanup.

## 5. Dolphin 3 controlled scope

Once section 1 passes, create one fresh worktree and `codex/*` branch from synchronized
`origin/main`. Dolphin 3 remains an additive facade over the v14 engine:

1. Define a global `ProjectCase` contract for project identity, location, jurisdiction, technology
   asset instances, capacity/count/type, CAPEX, itemized OPEX, currency/price basis and explicit
   source/assumption bindings. Never inherit Sri Lankan values into an unknown jurisdiction.
2. Define typed per-section result/disposition contracts that carry existing v14 outputs into the
   Dolphin 2 package without copying finance or domain mathematics.
3. Map only through `analytics.contracts_v14` and
   `analytics.evaluation_v14.evaluate_with_overrides()`. Preserve the existing engine and import
   direction; no big-bang rewrite.
4. Prove absent, unsupported, failed, degraded and executed mappings with negative controls. Never
   infer grade, review, release or stale outputs.
5. Keep grade aggregation, canonical hashing, adapter migration and product surfaces in later
   reversible dolphins unless a controlling Dolphin 1 criterion requires a smaller prerequisite.

The retained delivery sightline is:

1. additive global `ProjectCase` and per-section result facade;
2. Golden Path 1 - DutchBay/Sri Lanka complete report through all delivery modes;
3. Golden Path 2 - a second real jurisdiction/project validating the abstraction;
4. productization - web wizard, accounts, persistence, downloads, portfolios, licensing and
   commercial operations; and
5. performance measurement first, with only justified native kernels extracted while Python keeps
   orchestration and the contract/audit boundary.

Current D2 technology IDs are types, not asset instances. D2 is not wired into orchestration or
delivery adapters. Sri Lanka is not an assured pack, no second real jurisdiction has validated the
abstraction, canonical serialization/hashing remains later work, and live project, evidence, audit,
lender, Board and release states remain `HOLD`.
