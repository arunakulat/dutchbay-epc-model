# Session handover - 2026-08-29, successor 8

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-29.md`](SESSION_HANDOVER_2026-08-29.md). The predecessor remains
authoritative for the complete Dolphin 0-Dolphin 2 history, protected Dolphin 2 delivery,
acceptance records, wider Dolphin 3 sightline, and retained limitations. This record carries only
the additive Dolphin 3A `ProjectCase` v1 checkpoint. It changes no audit, statutory, engineering,
lender, Board, report-grade or release authority and lifts no `HOLD`.

## 1. Bootstrap - run this first

Resume from the dedicated worktree without mutating protected `main`:

```bash
set -eu
worktree="/Users/aruna/Downloads/dutchbay-wt-d3-project-case-contract"
cd "$worktree"
test "$(pwd -P)" = "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
test "$(git branch --show-current)" = "codex/d3-project-case-contract"

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

This record was written while the Dolphin 3A patch was intentionally uncommitted. On 29 August
2026 the user authorized sequential protected delivery: stage and commit the exact D3A files,
persist the branch remotely, obtain separate domain and assurance reviews, keep synchronizing with
live `origin/main`, run exact-head CI to green, and then merge. Current Git status and live refs are
therefore authoritative over the historical dirty-tree wording. Never reset, stash or clean away
the D3A worktree; keep it first on `PYTHONPATH`. Do not bypass the pull request, exact-head CI,
review, current-branch or continuing `HOLD` controls.

## 2. Base and ingress receipt

The branch originally pointed at exact `origin/main`
`13dc3d0958eb1084048cfadf45e8245f0b42bb5c`. A read-only fetch found it clean and strictly behind
current `origin/main`; the branch was fast-forwarded with `git merge --ff-only origin/main` to
`0e63f7adacd47953f5eb6d555ad4d63c1d8dc212`. The incoming change was the unrelated merged NSO OEM
evidence tranche. The Dolphin 2 merge commit
`367a17dc5f3e6054850523cde9673accdcb61227` remained an ancestor.

The governed Python is 3.12.13. `check_venv.sh --no-bootstrap` passed with the dedicated worktree
selected for imports, and the canonical GWTF bootstrap reported all 72 rules active. Before editing,
the complete required Dolphin 0-Dolphin 2 normative chain and both current handovers were ingressed
in the predecessor-prescribed order. The unchanged focused machine-contract/import/taxonomy gate
passed 386 tests at the new base.

## 3. Dolphin 3A implementation checkpoint

The Dolphin 3A change set consists of:

- `analytics/feasibility_report_contract/project_case.py` - new pure immutable domain contract;
- `analytics/feasibility_report_contract/__init__.py` - additive public exports;
- `tests/contracts/test_project_case_contract.py` - fictional JSON-native fixture plus hostile
  contract controls;
- `changelog.d/project-case-v1.added.md` - concise additive release note; and
- this handover successor.

`ProjectCase` v1 uses stable project, case, binding, asset, topology, line, allocation, source,
assumption and missing-input identifiers. Project and case IDs are separate identity axes and must
not be equal. Technology type and physical asset identity are separate.
The object graph contains explicit location/site-jurisdiction binding, versioned jurisdiction and
technology contract bindings, discriminated generation/storage/shared-infrastructure assets,
discriminated aggregate/unitized generation capacity, BESS MW/MWh/duration, hybrid topology and
reciprocal links, itemized CAPEX/OPEX, allocations, price bases, currency conversions, and material
values bound to sources, assumptions or exact missing-input records.

Material numeric fields are finite and explicitly unit-bearing. Resolved generation, storage and
shared-infrastructure capacity must be positive, so zero cannot silently encode an unknown value; a
missing capacity uses the explicit missing state. A resolved unit count is a positive
integer with unit `count` and the same provenance rule as capacity and costs. Generation and BESS
arithmetic reconciles when all operands are resolved and is deferred only where an operand is an
explicit `MissingValue`. Cost reconciliation similarly requires the declared status `complete` or
`incomplete_missing_input` to match the actual cost graph. Resolved allocations are non-zero and
sum to one; allocation, price-basis and currency-conversion registers are closed and reciprocal.

Every missing value must name a unique `MissingInputRecord` whose `field_path` is the exact
JSON-pointer-shaped path in the submitted document and whose `expected_unit` equals the missing
value unit. Unreferenced missing records are refused. Every resolved value/count must bind a source
or assumption, and that record must cover the exact jurisdiction and technology context derived
from its location, asset or allocated cost line. A Fictionland fixture and hostile multi-scope
tests prove that an LKA- or wind-scoped record cannot support another jurisdiction or technology.
There is no Sri Lankan fallback.

The enum values `unsupported`, `contract_supported` and `contract_reviewed` describe only input
contract availability and contract-scope review. They do not represent engineering assurance,
statutory approval, lender acceptance, achieved/report grade, release authority or a `HOLD`
decision.

## 4. Web and evolution boundary

The contract is suitable for a later JSON, form, Pydantic or FastAPI adapter because it exposes
stable field names and identifiers, explicit union discriminators, JSON-representable scalars,
strict extra-field refusal, immutable collections, generated Draft 2020-12 JSON Schema, and
predictable Pydantic error locations. It is not itself a FastAPI request model. Its strict domain
types accept the JSON-native fixture through `ProjectCase.model_validate_json()`, while direct
Python-mode validation of an already parsed dictionary correctly refuses lists, enum strings and
date strings that have not been normalized to domain-native tuples, enums and dates. A future
transport adapter must therefore either retain the raw request JSON and call
`model_validate_json()`, or explicitly normalize parsed request values before domain validation;
it must then map the resulting `ValidationError` locations and messages to transport field errors.
Cross-record missing and provenance errors include the exact JSON-pointer-shaped material field
path for that mapping.

The evolution boundary is `schema_id = dutchbay.project_case.v1` and
`contract_version = 1.0.0`. D3A defines no canonical JSON byte representation or hashing policy.
Array indexes in missing-input paths identify the exact submitted v1 document; a later editing
adapter must rewrite such paths if it reorders arrays before validation.

No FastAPI route, Pydantic transport adapter, UI/form, ORM, persistence, authentication,
deployment, renderer, serialization/signing policy, engine call, finance mathematics,
`evaluate_with_overrides`, ProjectCase-to-v14 mapping, 20-section package assembly, grade/review
aggregation, KPI change or release decision is present. `analytics.contracts_v14`, finance and KPI
paths are untouched.

## 5. Verification receipt

The current implementation and focused test pass:

```text
ProjectCase hostile/JSON/schema gate: 81 passed
Complete tests/contracts gate:       407 passed
Existing D2 focused gate:            386 passed
D2 plus ProjectCase coverage gate:    379 passed; 96.75% package total
ProjectCase module coverage:          98.06%
Ruff check and format:               passed
mypy on new module and test:          passed
py_compile/import/schema smoke:       passed
```

The only pytest warning is the pre-existing Hypothesis warning that repository `norecursedirs`
suppresses `.hypothesis` collection. Before delivery, rerun the commands in section 6 after any
review amendment and record the exact dirty-tree status and diff checks.

## 6. Exact rerun gate

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-wt-d3-project-case-contract
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider \
  tests/contracts/test_project_case_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider \
  tests/contracts/test_feasibility_report_machine_contract.py \
  tests/contracts/test_feasibility_report_machine_contract_coverage.py \
  tests/contracts/test_contracts_v14_import_surface.py \
  tests/analytics/test_feasibility_sections.py \
  tests/analytics/test_run_modes.py \
  tests/lint/test_compile_changelog.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider tests/contracts -q

"$DUTCHBAY_VENV/bin/ruff" check \
  analytics/feasibility_report_contract/project_case.py \
  analytics/feasibility_report_contract/__init__.py \
  tests/contracts/test_project_case_contract.py
"$DUTCHBAY_VENV/bin/ruff" format --check \
  analytics/feasibility_report_contract/project_case.py \
  analytics/feasibility_report_contract/__init__.py \
  tests/contracts/test_project_case_contract.py
PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/mypy" \
  analytics/feasibility_report_contract/project_case.py \
  tests/contracts/test_project_case_contract.py
git diff --check
git status --short --branch
```

## 7. Authorized sequential delivery and synchronization boundary

The authorized delivery sequence is:

1. stage only the five files named in section 3 and create an immutable candidate commit;
2. fetch and reconcile with live `origin/main`, rerun the focused gate, push the topic branch and
   open a draft pull request as the remote PERSIST checkpoint;
3. obtain separate read-only domain and assurance dispositions against one exact candidate;
4. persist those dispositions, remediate any finding in a new narrow commit, rerun all applicable
   gates, resynchronize with `origin/main`, and mark the pull request ready;
5. require every exact-head GitHub check to pass and the branch to be current and mergeable; and
6. merge only through the protected pull request, fast-forward protected `main`, prove containment,
   rerun the post-merge gate, preserve `HOLD`, and then remove the obsolete topic worktree/branch.

Another committer is active on the NSO BESS evidence tree and may advance `origin/main` during this
sequence. Fetch before every major state change. If the D3A branch is behind, incorporate only the
verified upstream commits without resetting, stashing, cleaning, overwriting or absorbing unrelated
NSO work into the D3A-authored diff. After every synchronization, verify the exact head, changed-file
set and gates again before review, push, CI acceptance or merge.

Completion of D3A remains contract-scope evidence only. Issue #1110 and all live project, evidence,
audit, lender, Board and release states remain unchanged and on `HOLD`.
