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

This record was updated while the Dolphin 3A remediation patch was intentionally uncommitted. The
independent review disposition remains **DOMAIN REJECTED** until an independent reviewer accepts
the exact remediated tree. Current Git status and live refs are authoritative. Never reset, stash
or clean away the D3A worktree; keep it first on `PYTHONPATH`. The isolated implementation worker
was not authorized to stage, commit, push, edit the pull request, merge, or otherwise mutate
GitHub. The parent task does carry the user's explicit authorization to proceed sequentially
through checkpointing, independent reviews, required CI and merge. That authority does not permit
bypassing the independent rereview, exact-head CI, current-branch or continuing `HOLD` controls.

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

The first D3A candidate was committed as `efba1e79c1ce400fed13e6fd90a9d31be5a77bbd`.
Commit `44f64a2` merged live `origin/main` `782c9588ef2685fcf0608d48f7745493aaa15b78`
into the topic branch without rewriting history. Commit
`adb0e7c29bae8e2ce26bf71dbf5b59cf94d25dba` then added the independent domain-review record.
The present uncommitted successor remediates every D3A-DOM-01 through D3A-DOM-09 finding in that
record; neither this handover nor green local gates supersedes its veto.

## 3. Dolphin 3A implementation checkpoint

The Dolphin 3A change set consists of:

- `analytics/feasibility_report_contract/project_case.py` - new pure immutable domain contract;
- `analytics/feasibility_report_contract/__init__.py` - additive public exports;
- `tests/contracts/test_project_case_contract.py` - fictional JSON-native fixture plus hostile
  contract controls;
- `changelog.d/project-case-v1.added.md` - concise additive release note; and
- this handover successor.

`ProjectCase` v1 is intentionally a truthful single-site contract. It uses stable project, case,
binding, asset, topology, line, allocation, price-basis, source, assumption and missing-input
identifiers. Project and case IDs are separate identity axes and must not be equal. Technology type
and physical asset identity are separate. Exactly one `site` jurisdiction must match the location
and every asset; a multi-site or multi-jurisdiction case is deferred to a future version rather than
misrepresented through one location.

The object graph contains mandatory schema and contract versions, explicit location/site-
jurisdiction binding, versioned jurisdiction and technology contract declarations, discriminated
generation/storage/shared-infrastructure assets, and discriminated aggregate/unitized generation
capacity. Generation declares its electrical and capacity basis. BESS power, energy and duration
each declare compatible electrical and capacity bases. A storage asset must declare a
discriminated charging source: another asset, a governed source record, or an exact missing-input
record.

Hybrid topology declares either `common_shared` or `dedicated_separate` interconnection. A common
path must be a typed `grid_interconnection` asset used by every technology asset; a dedicated case
cannot silently retain a common shared path. Reciprocal links distinguish `uses_shared` from
`charges_from`, and storage charging declarations must agree with those links. Shared assets have
typed infrastructure roles, preventing an access road or operations facility from masquerading as
the electrical interconnection.

Material numeric fields use strict, finite, precision-preserving `Decimal` semantics and explicit
units. Resolved generation, storage and shared-infrastructure capacity must be positive, so zero
cannot silently encode an unknown value; a missing capacity uses the explicit missing state. A
resolved unit count is a positive integer with unit `count` and the same provenance rule as
capacity and costs. Generation and BESS arithmetic reconciles only on compatible declared bases;
it is deferred where an operand is an explicit `MissingValue`, but still must be arithmetically
feasible. Engineering reconciliation and allocation closure use separate absolute tolerances.

Money declares native and reporting minor-unit precision. Cost multiplication and FX conversion
use exact Decimal arithmetic with explicit half-even rounding; FX rates must fit their declared
quote precision. A cost line's `PriceBasis` must itself carry source or assumption bindings whose
scope covers the line's jurisdiction and technology. Cost status `complete` or
`incomplete_missing_input` must match the actual graph. Resolved allocation shares are positive;
complete shares sum to one, while a partial allocation with explicit missing shares must leave a
strictly positive remainder. Allocation, price-basis and currency-conversion registers are closed
and reciprocal.

Every missing value must name a unique `MissingInputRecord` whose `field_path` is the exact
JSON-pointer-shaped path in the submitted document and whose `expected_unit` equals the missing
value unit. Unreferenced missing records are refused. Every resolved value/count must bind a source
or assumption, and that record must cover the exact jurisdiction and technology context derived
from its location, asset or allocated cost line. A Fictionland fixture and hostile multi-scope
tests prove that an LKA- or wind-scoped record cannot support another jurisdiction or technology.
There is no Sri Lankan fallback.

Technology and jurisdiction bindings expose only `unsupported` and the neutral `declared` state.
`declared` means that the caller supplied a contract declaration; it proves no review or support
decision. It does not represent engineering assurance, statutory approval, lender acceptance,
achieved/report grade, release authority or a `HOLD` decision. Boundary statuses now include
`indicative`, `contractual`, `surveyed`, `registered`, `derived` and `disputed`; accepting a
disputed boundary is not an assertion that it is surveyed or contractual.

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

The mandatory evolution boundary is `schema_id = dutchbay.project_case.v1` and
`contract_version = 1.0.0`; neither field has a default, and unknown or future values fail closed.
JSON-mode dumps retain Decimal values as precision-preserving strings. D3A defines no canonical JSON
byte representation or hashing policy. Array indexes in missing-input paths identify the exact
submitted v1 document; a later editing adapter must rewrite such paths if it reorders arrays before
validation.

No FastAPI route, Pydantic transport adapter, UI/form, ORM, persistence, authentication,
deployment, renderer, serialization/signing policy, engine call, finance mathematics,
`evaluate_with_overrides`, ProjectCase-to-v14 mapping, 20-section package assembly, grade/review
aggregation, KPI change or release decision is present. `analytics.contracts_v14`, finance and KPI
paths are untouched.

## 5. Verification receipt

The current remediation and inherited gates pass:

```text
ProjectCase hostile/JSON/schema gate: 107 passed
Complete tests/contracts gate:        433 passed
Existing D2 focused gate:            386 passed
D2 plus ProjectCase coverage gate:    405 passed; 96.62% package total
ProjectCase module coverage:          97.36%
Ruff check and format:               passed
mypy on new module and test:          passed
py_compile/import/schema/export:      passed; 62 exports, 47 schema definitions
Forbidden production import scan:     passed
```

The only pytest warning is the pre-existing Hypothesis warning that repository `norecursedirs`
suppresses `.hypothesis` collection. On this macOS environment, use the filesystem coverage target
`--cov=analytics/feasibility_report_contract`: the dotted package target makes pytest-cov import
`analytics` before the repository conftest replaces the package root and can trigger NumPy's
`cannot load module more than once per process` guard before collection. The filesystem target
avoids that harness-only double import and produced the passing receipt above. Before any later
delivery, rerun section 6 after an amendment and record exact status and diff checks.

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$DUTCHBAY_VENV/bin/python" -m pytest -p no:cacheprovider \
  --cov=analytics/feasibility_report_contract --cov-report=term-missing \
  --cov-fail-under=95 \
  tests/contracts/test_feasibility_report_machine_contract.py \
  tests/contracts/test_feasibility_report_machine_contract_coverage.py \
  tests/contracts/test_project_case_contract.py -q

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
PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" -m py_compile \
  analytics/feasibility_report_contract/project_case.py \
  analytics/feasibility_report_contract/__init__.py \
  tests/contracts/test_project_case_contract.py
git diff --check
git status --short --branch
```

## 7. Rereview and delivery boundary

Under the user's explicit sequential-delivery authorization, the parent task's next action is to
reconcile live `origin/main`, replay the root gates, commit and push exactly the five-file
remediation, and hand that immutable candidate to the independent domain reviewer with its file
hashes and test receipt. The implementation worker itself must not stage, commit, push, edit the
pull request, merge, or mutate GitHub. The existing **DOMAIN REJECTED** disposition remains
controlling until the reviewer issues an exact-tree successor disposition.

Before any later authorized Git or GitHub action, fetch and compare live `origin/main`, reconcile
only with explicit authority, and rerun the applicable gates against the resulting exact tree. Never
reset, stash, clean, overwrite, or absorb unrelated work into the D3A-authored diff. A later delivery
sequence must still use a protected pull request, exact-head independent review and required CI,
prove the topic branch current and mergeable, and preserve all `HOLD` states after merge.

Completion of D3A remains contract-scope evidence only. Issue #1110 and all live project, evidence,
audit, lender, Board and release states remain unchanged and on `HOLD`.
