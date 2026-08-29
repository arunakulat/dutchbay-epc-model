# Session handover - 2026-08-29, successor 17

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

This record captures the sixth D3A domain acceptance, the first assurance veto, the bounded repair
commit, the pre-restart seventh domain review, the recovered independent assurance rereview, and
the bounded post-restart ASR-03 worker candidate. The clean persisted topic head is
`59f1f37d7c7cf3fcc1c1d10c63d26799c7c34c45`; its production/test predecessor is
`836502a607fbce479f8e0412e2c63cb8659fafcd`. D3A-ASR-01 exact identifiers and D3A-ASR-02 portable
SemVer are independently accepted. Both reviews reject the persisted production tree because its
D3A-ASR-03 repair falsely refuses valid resolved and explicit-missing solar DC
`electrical_collection` capacity in `MWdc` and `MWp`. The current uncommitted worker candidate
admits those two collection units while retaining the `grid_interconnection` AC/apparent-unit
boundary; it has no independent successor disposition yet.

Current Git status and live refs are authoritative. At restart recovery, local `HEAD`, the upstream
topic, the live remote topic and PR `#1191` all identified `836502a607fbce479f8e0412e2c63cb8659fafcd`.
Local/live `origin/main`, the protected primary checkout and the PR base all identified
`782c9588ef2685fcf0608d48f7745493aaa15b78`; main was clean and the topic was zero behind and
sixteen commits ahead. Exact-head CI was fully green, but the PR remained open and draft. Commit
`59f1f37d7c7cf3fcc1c1d10c63d26799c7c34c45` then introduced only the authorized three-document
PERSIST-01 review record; it did not alter production, tests, exports, changelog, GitHub, issue
`#1110`, release state or a `HOLD`. Never reset, stash or clean away this documentation checkpoint.
The exact vetoes and bounded repair gate are in the two D3A review records. The later uncommitted
ASR-03 worker diff changes only the ProjectCase production validator, its focused tests, the
changelog fragment, and this handover.

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
class remained accepted. Its documentation-only checkpoint was committed and pushed as
`722845742f7123af3d637373c1996a82e357347a`; the production, export, test and changelog files were
unchanged from `2a3831542a3160f6d02cb2f592c4487981647f19`. A separate independent assurance replay
bound local `HEAD`, upstream, live topic and PR production predecessor to
`722845742f7123af3d637373c1996a82e357347a` and verified that live main/base
`782c9588ef2685fcf0608d48f7745493aaa15b78` remained its ancestor.
That replay returned **ASSURANCE REJECTED** on D3A-ASR-01 through -03. Exact-head GitHub CI was fully
green at 18 successful, 3 expected skipped and 0 failed or pending; this is supplementary evidence,
not a substitute for the adverse assurance result. Live refs and status are authoritative after
any later authorized parent checkpoint.
The assurance record was then committed and pushed as
`c45154b49963182447913d02968b533cfc38f05a`. The bounded remediation startup proved the dedicated
worktree clean at that exact local/upstream topic head, fetched unchanged live `origin/main`
`782c9588ef2685fcf0608d48f7745493aaa15b78`, and proved main already an ancestor; no merge or
history rewrite was required. Governed Python 3.12.13, `check_venv.sh --no-bootstrap`, and the
canonical 72-rule GWTF bootstrap passed again with this worktree first on `PYTHONPATH` before the
worker read the complete assurance record and current handover.
The bounded ASR repair was committed and pushed as
`836502a607fbce479f8e0412e2c63cb8659fafcd`. Its production, export, focused test, changelog and
handover fingerprints are recorded in both review records. Before the restart, a seventh domain
review accepted ASR-01 and ASR-02 but returned **DOMAIN REJECTED** on the `MWdc` collection false
rejection. After restart, a separate senior Python/Pydantic and web/API assurance reviewer rebound
all refs to the same exact SHA, reran the governed bootstrap and gates, accepted ASR-01 and ASR-02,
and returned **ASSURANCE REJECTED** because both `MWdc` and `MWp` solar collection units are falsely
refused for resolved and missing capacity. It also proved that the role/unit validator is not
encoded in Draft 2020-12, so prior wording that the electrical counterexample was schema-refused was
false. The primary main checkout and `origin/main` remained exactly synchronized; no topic merge was
required.
The three-document restart-recovery checkpoint was committed and pushed as
`59f1f37d7c7cf3fcc1c1d10c63d26799c7c34c45`. A later read-only fetch found `origin/main` unchanged
at `782c9588ef2685fcf0608d48f7745493aaa15b78`, already an ancestor of that topic head; the topic
was zero behind and seventeen commits ahead, so no merge or history rewrite was needed before the
bounded ASR-03 worker resumed.
Sections 19-23 of `docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md` preserve the fourth review;
sections 24-27 preserve the fifth veto, and sections 28-31 contain the controlling sixth
**DOMAIN ACCEPTED** predecessor disposition. Sections 32-35 preserve the exact seventh
**DOMAIN REJECTED** successor review. Sections 9-14 of the assurance record preserve the recovered
**ASSURANCE REJECTED** disposition. Neither predecessor acceptance nor green CI grants merge,
grade, lender, release, or `HOLD` authority.

## 3. Dolphin 3A implementation checkpoint

The Dolphin 3A change set consists of:

- `analytics/feasibility_report_contract/project_case.py` - new pure immutable domain contract;
- `analytics/feasibility_report_contract/__init__.py` - additive public exports;
- `tests/contracts/test_project_case_contract.py` - fictional JSON-native fixture plus hostile
  contract controls;
- `changelog.d/project-case-v1.added.md` - concise additive release note; and
- the independent review records and this handover successor.

The persisted predecessor contains the bounded ASR-01 through -03 production, export,
focused-test, release-note and handover repair plus the later three-document veto checkpoint. The
current uncommitted diff is the narrower ASR-03 successor: one runtime admissible-unit change, its
full-root focused controls, a truthful changelog correction, and this handover. The independent
review records remain unchanged. No export, schema customization, adapter, Git ref, GitHub, issue,
release or `HOLD` state is changed by the worker candidate.

`ProjectCase` v1 is intentionally a single-site contract. It declares project, case, binding,
asset, topology, line, allocation, price-basis, source, assumption and missing-input identifiers.
The ASR-01 repair makes every such token an exact, non-normalizing ASCII value of 1-160 characters;
runtime plus validation- and serialization-mode Draft schemas use the same absolute-end grammar.
Full-root tests cover canonical and hostile forms across all 13 named identity roles, including
ASCII boundary whitespace, line separators, non-ASCII letters/digits, Python mode and a hostile
asset whose canonical links and allocation can no longer become reciprocal through normalization.
Project and case IDs are separate identity axes and must not be equal. Technology type and physical
asset identity are separate. Exactly one `site` jurisdiction must match the location and every
physical asset. Additional non-site subject jurisdictions can remain separately scoped; a
multi-site physical-asset case is deferred to a future version rather than misrepresented through
one location.

Jurisdiction and technology pack declarations now use a D3A-local exact portable ASCII SemVer type.
Its core and numeric prerelease identifiers reject leading zeroes, prerelease and build components
follow SemVer grammar, and an absolute-end assertion aligns Python runtime, both Draft 2020-12
schemas and an actual ECMAScript `RegExp` replay. The shared Dolphin 2 vocabulary type is untouched.

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
silently encode an unknown value; a missing capacity uses the explicit missing state. At exact
`836502a`, every `grid_interconnection` and `electrical_collection` resolved or missing capacity is
restricted to `MW`, `MWac`, or `MVA`. That persisted rule is correct for the grid interconnection
but is the controlling false rejection for a solar electrical collection declared in `MWdc` or
`MWp`. The bounded worker candidate changes only `electrical_collection` to accept `MW`, `MWac`,
`MWdc`, `MWp`, or `MVA`; `grid_interconnection` remains `MW`, `MWac`, or `MVA`.
Access-road, operations-facility and other non-electrical shared roles retain the open `UnitToken`
boundary required by their heterogeneous dimensions. Every
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

The contract is designed as a transport-neutral basis for a later JSON, form, Pydantic or FastAPI
adapter. Its explicit union discriminators, strict extra-field refusal, frozen object graph,
JSON-representable scalars and generated Draft 2020-12 schemas passed independent replay. The
identifier and pack-version repairs now agree across runtime, Draft and an actual ECMAScript
implementation. The role-dependent electrical-capacity rule is runtime semantic validation only.
The generated Draft 2020-12 schemas are structural and accept the original electrical-collection
`USD` counterexample as well as valid `MWdc` and `MWp` collection cases. The bounded worker
candidate corrects the runtime false rejects without adding conditional schema machinery. A future
adapter must invoke domain validation and must not claim schema-only acceptance is sufficient. The
worker candidate is not independently domain- or assurance-cleared for the future web boundary,
and no transport adapter was added.

The contract is not itself a FastAPI request model. Its strict domain types accept the JSON-native
fixture through `ProjectCase.model_validate_json()`, while direct Python-mode validation of an
already parsed dictionary correctly refuses lists, enum strings and date strings that have not been
normalized to domain-native tuples, enums and dates. A future transport adapter must therefore
either retain the raw request JSON and call `model_validate_json()`, or explicitly normalize parsed
request values before domain validation; it must then map the resulting `ValidationError`
locations and messages to versioned transport field errors. Cross-record missing and provenance
errors currently have root location `()` and include the exact JSON-pointer-shaped material field
path in the message; clients must not be required to parse that prose.

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

A future raw-body adapter must also reject duplicate JSON keys before Pydantic's last-value-wins
parser, preserve the strict runtime treatment of small integer controls even though Draft 2020-12
considers a numeric token such as `1.0` an integer, publish the exact Decimal/count patterns if it
uses the looser serialization-mode schema, and impose measured body/collection bounds before the
potentially quadratic provenance-scope checks. These are candid adapter exclusions, not claims that
D3A already supplies request normalization, error mapping, resource policy or OpenAPI behavior.

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
Pushed docs-head CI (`7228457`):               18 successful; 3 expected skipped; 0 failed/pending
Pushed docs-head required checks:              4/4 passed
Sixth independent domain disposition:         DOMAIN ACCEPTED
```

The subsequent assurance reviewer independently obtained this exact-head receipt:

```text
Assurance-reviewed pushed head:                722845742f7123af3d637373c1996a82e357347a
Unchanged production/test candidate:           2a3831542a3160f6d02cb2f592c4487981647f19
Reviewed live main/base:                       782c9588ef2685fcf0608d48f7745493aaa15b78
ProjectCase focused gate:                      241 passed; one pre-existing warning
Complete tests/contracts gate:                 567 passed; one pre-existing warning
Inherited D2 import/taxonomy gate:              386 passed; one pre-existing warning
Independent shared-FX brute-force oracle:       288 schedules; 0 mismatches
Independent arrangement/role/user matrix:        30 cases; 0 mismatches
R10 / `connected_to` runtime/schema probe:        passed; relationship absent/refused
Decimal/count full-root lexical matrix:          14 cases; 0 mismatches
Validation/serialization Draft schemas:          valid; 47 definitions each
Canonical dump against both schemas:             passed
Public exports:                                  62; all 58 ProjectCase exports present
Ruff/Ruff Format/Black/isort/mypy/compile:        passed
D3A excluded execution-surface diff:              empty
Exact-head GitHub CI:                             18 successful; 3 expected skipped; 0 failed/pending
Exact-head required checks:                       4/4 passed
Independent assurance disposition:               ASSURANCE REJECTED
Blocking findings:                                D3A-ASR-01, D3A-ASR-02, D3A-ASR-03
```

The bounded ASR-01 through -03 worker obtained this pre-commit receipt:

```text
Worker base/local upstream topic:                c45154b49963182447913d02968b533cfc38f05a
Fetched live main/base:                          782c9588ef2685fcf0608d48f7745493aaa15b78
ProjectCase hostile/runtime/schema gate:          297 passed; one pre-existing warning
Complete tests/contracts gate:                    623 passed; one pre-existing warning
Inherited D2 import/taxonomy gate:                 386 passed; one pre-existing warning
D2 plus ProjectCase filesystem coverage:          595 passed; 95.99% package total
ProjectCase module coverage:                      95.48%
ECMAScript SemVer matrix:                          10 valid, 20 invalid; passed
Validation/serialization Draft schemas:           valid; 47 definitions each
Public exports:                                    63; all 59 ProjectCase exports present
Ruff/Ruff Format/Black/isort/mypy/compile:          passed
AST import/context and excluded surfaces:          passed
Tracked diff whitespace; untracked-file gate:      passed; no untracked files
Worker Git/GitHub mutation:                        none
Independent successor disposition at that point:    not yet performed
Controlling predecessor disposition:               ASSURANCE REJECTED
```

The committed successor and restart recovery then produced:

```text
Exact pushed/reviewed head:                     836502a607fbce479f8e0412e2c63cb8659fafcd
Exact local/live main and PR base:              782c9588ef2685fcf0608d48f7745493aaa15b78
Topic relation to main:                         0 behind; 16 ahead
ProjectCase focused gate:                       297 passed; one pre-existing warning
Complete tests/contracts gate:                  623 passed; one pre-existing warning
Inherited D2 import/taxonomy gate:               386 passed; one pre-existing warning
In-memory D2 plus ProjectCase coverage:          595 passed; 95.99% package total
ProjectCase module coverage:                     95.48%
Targeted FX/topology/provenance replay:            55 passed
Domain ASR-01 matrix:                           5,225 cases; 0 mismatches
Domain ASR-02 matrix:                          81,660 cases; 0 mismatches
Domain role/unit/state matrix:                    100 cases; 2 MWdc false rejects
Assurance ASR-01 matrix:                          455 checks; 0 mismatches
Assurance ASR-02 runtime/Draft checks:             90 checks; 0 mismatches
Assurance Node/ECMAScript matrix:                  30 cases; 0 mismatches
Assurance solar collection/grid matrix:             8 cases; 4 collection false rejects
Validation/serialization Draft schemas:           valid; 47 definitions each
Public exports:                                    63; all 59 ProjectCase exports present
Ruff/Ruff Format/Black/isort/mypy/compile:        passed
AST imports, excluded surfaces and diff checks:   passed
Exact-head GitHub CI:                             18 successful; 3 expected skipped; 0 failed/pending
Exact-head required checks:                       4/4 passed
Seventh independent domain disposition:          DOMAIN REJECTED
Recovered independent assurance disposition:     ASSURANCE REJECTED
```

The controlling persisted rejection is bounded only to the ASR-03 electrical-collection capacity
dimension and truthful runtime/schema wording. ASR-01 exact identifiers and ASR-02 portable SemVer
are accepted.
The veto does not reopen the accepted R1-R10 arithmetic, topology, provenance or Decimal/count
transport repairs. Conversely, green gates and predecessor domain acceptance do not approve the
rejected successor tree.

The current uncommitted ASR-03 worker candidate produced this local receipt against persisted head
`59f1f37d7c7cf3fcc1c1d10c63d26799c7c34c45` and unchanged main
`782c9588ef2685fcf0608d48f7745493aaa15b78`:

```text
Targeted solar/electrical-role matrix:            38 passed
ProjectCase focused gate:                        330 passed; one pre-existing warning
Complete tests/contracts gate:                   656 passed; one pre-existing warning
Inherited D2 import/taxonomy gate:                386 passed; one pre-existing warning
D2 plus ProjectCase coverage:                    628 passed; 96.02% package total
ProjectCase module coverage:                      95.57%
Ruff/Ruff Format/Black/isort/mypy/compile:        passed
Validation/serialization Draft schemas:           valid; 47 definitions each
Public exports / ProjectCase exports:               63 / 59
ASR-02 Node/ECMAScript matrix:                     10 valid / 20 invalid; passed
AST imports, production fallback scan:            passed
Cumulative changed-file/exclusion gate:            passed; exact eight-file D3A set
Tracked diff whitespace and untracked-file gate:   passed; no untracked files
Worker Git/GitHub/issue/HOLD mutation:              none
Independent successor disposition:                 not yet performed
```

The full-root worker controls use a solar-PV generation asset with explicit DC/nameplate capacity,
a BESS charging reciprocally from that generation asset, a dedicated arrangement, and exactly one
user of the electrical facility. Resolved and explicit-missing `MWdc`/`MWp` collection cases
accept; the matching grid-interconnection cases reject; nearby `MW`/`MWac`/`MVA` states accept for
both electrical roles; non-power units reject for both electrical roles; and resolved/missing
access-road, operations-facility and other-facility units remain open. Missing capacity is closed
by the exact `/assets/2/capacity` record with a matching expected unit. A separate control proves
that both generated Draft schemas structurally accept the runtime-invalid `USD` case, preserving
the candid web boundary rather than manufacturing conditional schema behavior.

The ASR-focused additions cover canonical and hostile exact identifier forms for project, case,
asset, link, cost, allocation, both binding kinds, source, assumption, missing-input, price-basis
and conversion IDs against runtime and both generated schemas; Python non-normalization and the
normalization-created asset reciprocity counterexample are explicit. The SemVer matrix covers
release, prerelease and build positives plus Unicode digits, leading-zero core/numeric prerelease,
empty/double components, whitespace and terminal line separators through runtime, Draft 2020-12 and
ECMAScript. The in-tree collection matrix rejects `USD`, `km`, `item` and `MWh`, accepts `MW`,
`MWac` and `MVA`, and retains open units for all three non-electrical roles under a valid dedicated
topology. It lacks solar DC positives. Independent full-root cases prove that both resolved and
missing `MWdc`/`MWp` electrical collection are falsely refused while the same DC units remain
correctly refused for `grid_interconnection`.

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
domain result for that production/test tree and does not reopen any earlier accepted repair class.
The first assurance veto is preserved at pushed documentation commit
`c45154b49963182447913d02968b533cfc38f05a`. Its bounded repair is pushed at exact
`836502a607fbce479f8e0412e2c63cb8659fafcd`. The seventh domain review and recovered assurance
review both reject that successor on the remaining D3A-ASR-03 false rejection. ASR-01 and ASR-02
are accepted and should not be reopened without new evidence.

The current uncommitted worker candidate implements one bounded repair:

1. retain exact non-normalizing ASCII stable identifiers and portable D3A-local SemVer unchanged;
2. accept `MW`, `MWac`, `MWdc`, `MWp` and `MVA` for resolved and explicit-missing
   `electrical_collection` capacity;
3. retain `grid_interconnection` at `MW`, `MWac` or `MVA` and reject `MWdc`/`MWp` there;
4. preserve non-power rejection for both electrical roles, open non-electrical units, R1-R10,
   direct imports, exclusions and authority separations; and
5. add full-root resolved/missing solar controls and make changelog/handover runtime-versus-schema
   wording exact.

The generated Draft schemas do not encode the role/unit conditional. The changelog, web boundary,
and worker controls now state and prove that this semantic dimension is runtime-only and that a
future web/API adapter must invoke `ProjectCase` validation. Draft alone still accepts the original
`USD` counterexample; no conditional schema machinery was added.

Current Git identity and cleanliness must be read live. At this PERSIST writer handback, persisted
local/upstream topic head is `59f1f37d7c7cf3fcc1c1d10c63d26799c7c34c45`; its production/test
predecessor remains `836502a607fbce479f8e0412e2c63cb8659fafcd`. Exactly four files are modified
and uncommitted: the ProjectCase module, its focused test, the changelog fragment, and this
handover. There are no untracked files. The worker did not stage, commit, push, edit the PR, merge,
mutate issue `#1110`, or alter a `HOLD`.

Before any later authorized Git or GitHub action, fetch and compare live `origin/main`, the remote
topic and PR head; reconcile only with explicit authority. Repeat that synchronization at
each major checkpoint because another committer can advance `main`; never reset, stash, clean,
overwrite, or absorb unrelated work into the D3A-authored diff. After the worker candidate is
checkpointed under the controlling delivery authority, obtain a fresh exact-head domain delta
disposition and separate assurance disposition. Only if both accept,
make the protected PR ready, prove the exact reviewed head current and mergeable, and wait for all
required CI before the already authorized merge. Preserve all `HOLD` states after merge.

Domain acceptance remains contract-scope evidence only. It is not professional or statutory
engineering assurance, external audit, lender or Board acceptance, achieved-grade authority,
release or deployment authorization, or permission to merge before assurance and delivery controls
complete. The future adapter duties in section 4 remain exclusions. Issue #1110 and all live
project, evidence, audit, lender, Board and release states remain unchanged and on `HOLD`.
