# Session handover - 2026-08-29, successor 14

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

This record captures the sixth exact-head D3A domain review. The independent disposition is
**DOMAIN ACCEPTED** at `2a3831542a3160f6d02cb2f592c4487981647f19`: R10 dedicated-versus-shared
electrical topology is closed, and R8-R9 and every earlier repair class remain accepted. The fifth
**DOMAIN REJECTED** disposition at `b0020ece4e864cc2cf589bae40f82edd5c30320d` remains preserved as
history but is no longer the current domain disposition. Separate exact-head assurance is now the
next review boundary. Current Git status and live refs are authoritative. Never reset, stash or
clean away the D3A worktree; keep it first on `PYTHONPATH`.
The documentation worker is not authorized to stage, commit, push, edit the pull request, merge, or
otherwise mutate GitHub; the controlling parent task holds the user's sequential delivery
authority. Do not bypass separate assurance, exact-head CI, current-branch, protected-PR, or
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
review record was committed as `debc4875628a8f597f21de5a9cc7aefa3d18779c`. Bounded R8-R9 were
then committed and pushed as `b0020ece4e864cc2cf589bae40f82edd5c30320d`. The fifth independent
review accepted R8-R9 and every earlier repair class, but rejected that exact candidate on R10: a
`dedicated_separate` topology can still retain one electrical shared facility used by both wind and
BESS. That fifth review record was committed and pushed as
`50a32a2343b5c7941c29fe00cba695e2c13ce1c8`; it was the clean base of the bounded R10 worker
handback. The bounded R10 implementation was committed and pushed as
`2a3831542a3160f6d02cb2f592c4487981647f19`. The sixth independent review accepted that exact head
after two independent topology matrices returned zero mismatches and every original/R1-R9 repair
class remained accepted. Live refs and status are authoritative after any later authorized parent
checkpoint.
Sections 19-23 of `docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md` preserve the fourth review;
sections 24-27 preserve the fifth veto, and sections 28-31 contain the controlling sixth
**DOMAIN ACCEPTED** disposition. Separate assurance remains required; neither domain acceptance nor
green CI grants merge, grade, lender, release, or `HOLD` authority.

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
and every physical asset. Additional non-site subject jurisdictions can remain separately scoped;
a multi-site physical-asset case is deferred to a future version rather than misrepresented through
one location.

The object graph contains mandatory schema and contract versions, explicit location/site-
jurisdiction binding, versioned jurisdiction and technology contract declarations, discriminated
generation/storage/shared-infrastructure assets, and discriminated aggregate/unitized generation
capacity. Generation declares its electrical and capacity basis. BESS power, energy and duration
each declare compatible electrical and capacity bases. A storage asset must declare a
discriminated charging source: another asset, a governed source record, or an exact missing-input
record.

Hybrid topology declares either `common_shared` or `dedicated_separate` interconnection. A common
path must be a typed `grid_interconnection` asset used by every technology asset. The R10 successor
reconciles every `uses_shared_infrastructure` relationship under a dedicated arrangement: a
`grid_interconnection` or `electrical_collection` facility cannot have more than one technology-
asset user. Distinct electrical facilities with one user each remain valid, as do shared
non-electrical access-road, operations-facility and other shared-facility roles. Reciprocal links
distinguish infrastructure use from `charges_from`; storage charging declarations must agree with
their charging links. A direct storage-to-generation `charges_from` link remains charging semantics,
but a storage link to a shared grid-interconnection is a material electrical connection and counts
that storage asset in the dedicated-facility user invariant. The untyped `connected_to` relationship
has been removed from the v1 enum and generated schema rather than retained as an unvalidated escape.

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

The bounded R10 worker handback and sixth independent review gates pass:

```text
Exact sixth-reviewed candidate:                2a3831542a3160f6d02cb2f592c4487981647f19
ProjectCase hostile/JSON/schema gate:          241 passed
Selected original and R1-R10 replay:           132 passed
Complete tests/contracts gate:                 567 passed
Existing D2 focused gate:                      386 passed
Prior worker D2 plus ProjectCase coverage:     539 passed; 95.92% package total
Prior worker ProjectCase module coverage:      95.29%
Independent R10 hand-constructed matrix:        35 cases; 0 mismatches
Independent R10 arrangement/role/user matrix:   48 cases; 0 mismatches
Independent R9 schedule oracle:                  6 cases; 0 mismatches
Ruff check and format:                         passed
Black check:                                   passed
isort check:                                   passed
mypy --no-incremental:                         passed
in-memory compile/import/schema/export:        passed; 62 exports, 47 definitions
AST forbidden production import scan:         passed
Exact-head GitHub CI:                          18 successful; 3 expected skipped; 0 failed/pending
Exact-head required checks:                    4/4 passed
Sixth independent domain disposition:         DOMAIN ACCEPTED
```

The eight R10 focused cases reject the reviewed shared POI and shared electrical-collection paths
under `dedicated_separate`, plus wind use and BESS charging through the same POI. They accept the
existing no-shared case, shared access-road and operations facilities, distinct one-user electrical
facilities, direct storage-to-generation charging, and BESS use/charging through its own distinct
grid facility. A full-root runtime and Draft 2020-12 control proves that `connected_to` is absent
from the `AssetLinkKind` schema and refused at the exact link-kind field.
The sixth review added independent 35-case and 48-case topology oracles spanning both arrangements,
all five shared-facility roles, same and distinct facilities, two and three technology assets,
shared-grid and generation charging, and malformed duplicate/dangling/self/reversed link graphs; both
returned zero mismatches. Its 132-case replay is an external independent selection rather than a
named repository selector. The 241-case focused gate covers all in-tree original/R1-R10 controls.

The 48 R8-R9 additional focused cases prove sole-string Decimal/count JSON ingress, deterministic
full-model dump/re-ingress, hostile runtime/Draft parity, exact 36/37-digit count boundaries, the
reviewed disjoint `9950..10050` and `19950..20050` shared-rate intervals, common-rate controls,
inferable-native variants, missing-report overflow and nearby feasible controls, zero-native
controls, mixed minor/quote precision, three consumers, and the consistent fail-closed
underdetermined-native/missing-report rule for resolved and missing FX. Their independent bounded
`Fraction`/half-even oracle does not call the production rounding or interval helper when deriving
expected witnesses.

The fifth review independently replayed the original D3A-DOM-01 through -09 and R1-R9 pairs, ran
113 selected controls, and accepted those repair classes. Independent exact oracles returned zero
mismatches across 1,524 Decimal runtime/schema strings, 1,016 count strings, 120 shared-FX
schedules, 1,488 shared-rate grid intervals, 12,096 missing-factor cases, and 18 hostile-context
native Decimal round trips; all nine raw JSON numeric-token controls were refused and all 20
half-even ties behaved correctly. The sixth review replayed those classes in proportion to risk,
including the full R8 root round trip and a six-schedule independent R9 oracle, without a regression.
The accepted exact refs, hashes, CI, topology evidence, exclusions, and authority boundary are in
sections 28-31 of the remediation rereview record.

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

The bounded R8 exact JSON/count representation, R9 one-rate shared-conversion intersection, and R10
dedicated electrical-path closure are committed, pushed, and independently accepted at exact
`2a3831542a3160f6d02cb2f592c4487981647f19`. The sixth **DOMAIN ACCEPTED** disposition is the
current domain result. It does not reopen any earlier accepted repair class. Separate independent
assurance is the next required review boundary.

Current Git identity and cleanliness must be read live; this durable receipt does not assert that
the documentation diff remains uncommitted after the controlling parent acts. The implementation
and documentation workers must not stage, commit, push, edit the pull request, merge, or mutate
GitHub. The controlling parent must inspect this PERSIST-only diff, checkpoint and push it only under
the user's delivery authority, then dispatch separate assurance against the resulting immutable
head. Any later production, export, test, or changelog change invalidates this sixth domain receipt
and requires a new exact-head domain review.

Before any later authorized Git or GitHub action, fetch and compare live `origin/main`, reconcile
only with explicit authority, and rerun the applicable gates against the resulting exact tree. Never
reset, stash, clean, overwrite, or absorb unrelated work into the D3A-authored diff. A later delivery
sequence must still use a protected pull request, exact-head independent review and required CI,
prove the topic branch current and mergeable, and preserve all `HOLD` states after merge.

Domain acceptance remains contract-scope evidence only. It is not professional or statutory
engineering assurance, external audit, lender or Board acceptance, achieved-grade authority,
release or deployment authorization, or permission to merge before separate assurance and delivery
controls complete. The future adapter duties in section 4 remain exclusions. Issue #1110 and all
live project, evidence, audit, lender, Board and release states remain unchanged and on `HOLD`.
