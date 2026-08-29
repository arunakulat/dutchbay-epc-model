# Session handover - 2026-08-29, successor 11

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

This record captures the fourth exact-head D3A domain veto and the bounded R8-R9 pre-checkpoint
writer handback based on it.
The fourth independent review disposition is **DOMAIN REJECTED** at
`c47aa8ffc1ff658b03216dbba93680d1eff2618d`; it remains controlling until an independent reviewer
accepts a later exact successor identified by live Git refs and file hashes. Current Git status and
live refs are authoritative. Never reset, stash or clean away the D3A worktree; keep it first on
`PYTHONPATH`.
The implementation worker is not authorized to stage, commit, push, edit the pull request, merge,
or otherwise mutate GitHub; the controlling parent task holds the user's sequential delivery
authority. Do not bypass another independent domain rereview, exact-head CI, current-branch or
continuing `HOLD` controls.

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
`adb0e7c29bae8e2ce26bf71dbf5b59cf94d25dba` then added the first independent domain-review
record. The first remediation of D3A-DOM-01 through D3A-DOM-09 was committed as `ce10721`; the
dual-formatter correction was committed as `6e6f07a`. The exact second domain veto was recorded at
`c7db8f7c7cfee86f69bd43de280335f816508131`. Bounded R1-R4 were committed as
`de897d0aff7daa1caaf7797ce5556cdd040c8627`; the third domain veto was then recorded at
`47fd2638b3d947c5e52d41fd5670514944d0030f`. Bounded R5-R7, exact allocation, and deterministic
Decimal serialization were committed as `c47aa8ffc1ff658b03216dbba93680d1eff2618d` and passed the
required and wider GitHub checks. The fourth independent review nevertheless rejected that exact
candidate on R8 JSON-number/schema precision and R9 shared missing-FX consistency. Its durable
review record was committed as `debc4875628a8f597f21de5a9cc7aefa3d18779c`; that clean pushed
head was the base at the pre-checkpoint writer handback described here. Live refs and status are
authoritative after any later authorized parent checkpoint. Sections 19-23 of
`docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md` are the controlling durable review record. The
fourth veto remains controlling until an independent reviewer accepts a later exact committed head;
neither this working-tree proof nor green tests supersede it.

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

Material numeric fields intend one strict, finite Decimal domain: at most 72 total digits, 36 digits
before the decimal point and 36 decimal places. The Python-native and plain-string paths use
`Decimal.as_tuple()` and exact lexical checks rather than Pydantic `max_digits` or
`decimal_places`; those paths are independent of ambient precision and rounding. The anchored
plain-ASCII JSON string grammar correctly accepts exact-scale zero through 36 places and refuses
exponent strings and excessive scale. Strict Python mode requires a domain-native `Decimal`.

The R8 successor removes the rejected JSON-number branch. Anchored plain-ASCII strings are now the
sole JSON representation for every `FiniteDecimal`; raw JSON integer or floating tokens are refused
before coercion, and the generated Draft 2020-12 schema exposes only the same anchored grammar.
Normalized Python mode still requires a native `Decimal`, and JSON serialization emits deterministic
plain notation. `ResolvedCount` likewise uses a positive unsigned no-leading-zero string of at most
36 digits in JSON, while normalized Python mode requires a native positive `int`; JSON serialization
is the exact decimal string. This removes the runtime/schema ambiguity for JSON `1`, `1.0`, and
`1e0` rather than treating numerically equivalent token spellings as lexically identical inputs.

Resolved generation, storage and shared-infrastructure capacity must be positive, so zero cannot
silently encode an unknown value; a missing capacity uses the explicit missing state. Every
one-missing count/unit/total generation proposition and power/energy/duration BESS proposition must
have an exact bounded 1e-36-grid completion within the 1e-9 engineering tolerance. Two-or-more
missing states are retained only where the validator constructs a bounded completion. Generation,
BESS, allocation, cost and FX arithmetic never uses the ambient Decimal context. Exact rational
comparison governs engineering and allocation predicates, while multiplication and quantization
use explicit contexts sized above the largest permitted exact product. A Decimal operation failure
becomes a controlled Pydantic validation error rather than escaping as a raw Decimal exception.

Money declares native and reporting minor-unit precision. Cost multiplication and FX conversion
use exact bounded-domain Decimal arithmetic with explicit half-even rounding; FX rates must fit
their declared quote precision. When FX is resolved and native amount plus a product operand is
missing, the validator derives the complete native minor-unit interval that maps to the declared
reporting amount by monotone binary search, then intersects that interval with the exact
quantity/rate output set. This rejects the reviewed USD 1/native-scale-0/FX-2 contradiction and
accepts the nearby USD 2 completion. Where quantity and rate make native amount inferable, a
missing FX rate still uses the previously verified exact single-equation predicate.

For a resolved reporting target, ProjectCase v1 intentionally does not admit a connected cost chain
where both the effective native amount and FX rate remain unresolved. When reporting is missing, v1
requires the effective native amount to be resolved or exactly inferable whether FX is resolved or
missing. Those are fail-closed admissibility rules because D3A does not contain a complete
two-variable existential proof; neither is a claim that no mathematical completion exists. Sampled
interior witnesses are never treated as proof. A zero factor cannot hide a non-zero product, and
inferred native amounts cannot conflict with same-currency reporting amounts. Cost status
`complete` or `incomplete_missing_input` must match the actual graph.

The R9 successor treats each missing `CurrencyConversion.rate` as one schedule-level graph
variable. Every consuming line derives an exact inclusive interval on the shared positive integer
quote grid. A resolved or inferable native amount plus a resolved report uses the exact monotone
half-even output interval; a missing report contributes the maximum rate whose rounded output
remains inside its declared reporting minor-unit and 72/36 numeric domain. The schedule intersects
all consumer intervals and accepts only if one common rate remains. No sampled witness or
production brute force is used.

A cost line's `PriceBasis` must carry source or assumption bindings whose scope covers the line's
jurisdiction and technology. A currency conversion rate's evidence scope is derived only from the
cost lines that name the conversion and from those lines' allocations and assets; it does not
inherit unrelated project technologies. Resolved allocation shares are positive; complete shares
sum to exactly one as a rational value. A partial allocation remainder must lie on the 1e-36 share
grid and be at least one positive grid quantum for every missing share. Allocation, price-basis and
currency-conversion registers are closed and reciprocal.

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
JSON-mode dumps emit every Decimal and resolved count as a deterministic plain-ASCII string using
ambient-independent fixed or integer notation. Decimal fractional scale is preserved where present;
accepted positive exponents are expanded to plain integer notation, positive/negative zero retain
their sign, and a 36-place zero retains its 36-place scale. Those outputs can be ingressed again and
satisfy the generated Draft 2020-12 validation schema. Runtime/schema ingress equivalence is proved
for the sole anchored Decimal and count string representations, including exact 72/36 Decimal and
36-digit count values; raw JSON numeric tokens; hostile 37/73/100/500-place, excessive-zero-scale,
exponent, Unicode-digit, whitespace and terminal LF/CR/CRLF/U+2028/U+2029 strings; and `1`, `1.0`,
`1e0`, signed, zero and leading-zero count forms under hostile Decimal contexts. Both generated
patterns use an absolute-end assertion rather than `$`, so Draft 2020-12 cannot accept a terminal
line break that runtime `re.fullmatch` refuses. Python-mode string refusal remains the explicit
transport-normalization seam. A future web adapter must still impose request-size and transport
resource controls before domain validation; D3A adds no adapter or endpoint policy. D3A defines no
canonical whole-document JSON byte representation or hashing policy. Array indexes in
missing-input paths identify the exact submitted v1 document; a later editing adapter must rewrite
such paths if it reorders arrays before validation.

No FastAPI route, Pydantic transport adapter, UI/form, ORM, persistence, authentication,
deployment, renderer, canonical document serialization/signing policy, engine call, finance
mathematics, `evaluate_with_overrides`, ProjectCase-to-v14 mapping, 20-section package assembly,
grade/review
aggregation, KPI change or release decision is present. `analytics.contracts_v14`, finance and KPI
paths are untouched.

## 5. Verification receipt

The current remediation and inherited gates pass:

```text
ProjectCase hostile/JSON/schema gate: 233 passed
Complete tests/contracts gate:        559 passed
Existing D2 focused gate:            386 passed
D2 plus ProjectCase coverage gate:    531 passed; 95.91% package total
ProjectCase module coverage:          95.26%
Ruff check and format:               passed
Black check:                         passed
isort check:                         passed
mypy --no-incremental:               passed
py_compile/import/schema/export:      passed; 62 exports, 47 schema definitions
AST forbidden production import scan: passed
Fourth independent domain disposition: DOMAIN REJECTED (R8 and R9)
```

The 48 R8-R9 additional focused cases prove sole-string Decimal/count JSON ingress, deterministic
full-model dump/re-ingress, hostile runtime/Draft parity, exact 36/37-digit count boundaries, the
reviewed disjoint `9950..10050` and `19950..20050` shared-rate intervals, common-rate controls,
inferable-native variants, missing-report overflow and nearby feasible controls, zero-native
controls, mixed minor/quote precision, three consumers, and the consistent fail-closed
underdetermined-native/missing-report rule for resolved and missing FX. Their independent bounded
`Fraction`/half-even oracle does not call the production rounding or interval helper when deriving
expected witnesses.

The preceding 58 additional focused cases include the exact R5 rejected USD 1 and accepted USD 2
chains;
missing quantity, rate, native-amount and FX combinations; the explicit two-unbound admissibility
refusal; all four reviewed R6 negatives and nearby positives; constructive multi-missing capacity
cases; exact complete and partial allocation closure; and R7 runtime/schema probes over exact and
hostile strings, numbers and Python-native Decimals under multiple ambient contexts. Twenty-three
R7 cases use the independent Draft 2020-12 `jsonschema` implementation as the schema oracle. A
compact independent enumeration also checks 1,242 bounded native-grid target intervals against the
analytic monotone solver.

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
"$DUTCHBAY_VENV/bin/black" --check \
  analytics/feasibility_report_contract/project_case.py \
  analytics/feasibility_report_contract/__init__.py \
  tests/contracts/test_project_case_contract.py
"$DUTCHBAY_VENV/bin/isort" --check-only \
  analytics/feasibility_report_contract/project_case.py \
  analytics/feasibility_report_contract/__init__.py \
  tests/contracts/test_project_case_contract.py
PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/mypy" --no-incremental \
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

The bounded R8 exact JSON/count representation and R9 one-rate shared-conversion intersection were
implemented and locally proved in the pre-checkpoint writer handback described here. Current Git
identity and cleanliness must be read live; this durable receipt does not assert that the diff
remains uncommitted after the controlling parent acts. The implementation worker itself must not
stage, commit, push, edit the pull request, merge, or mutate GitHub. The controlling parent must
inspect the exact diff, checkpoint and push a new immutable SHA only under its delivery authority,
then obtain another independent domain disposition. The existing **DOMAIN REJECTED** disposition
remains controlling; separate assurance review is blocked until domain acceptance.

Before any later authorized Git or GitHub action, fetch and compare live `origin/main`, reconcile
only with explicit authority, and rerun the applicable gates against the resulting exact tree. Never
reset, stash, clean, overwrite, or absorb unrelated work into the D3A-authored diff. A later delivery
sequence must still use a protected pull request, exact-head independent review and required CI,
prove the topic branch current and mergeable, and preserve all `HOLD` states after merge.

Completion of D3A remains contract-scope evidence only. Issue #1110 and all live project, evidence,
audit, lender, Board and release states remain unchanged and on `HOLD`.
