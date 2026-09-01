# Dolphin 3C-1b context-binding implementation record

**Status:** corrected replacement candidate and pre-freeze local verification complete;
independent exact-SHA review pending; no D2 package assembly or HOLD movement

**Protected base:** `be1956413b407b299d6b116e79bd84456ef62b2d` (`origin/main` at lease)

**Current integration base:** `e60ea866da6b77c1d9e39236c206140eae1af08d` (`origin/main` after
non-overlapping license-only advance and clean rebase)

**Branch/worktree:** `codex/d3c1b-context-binding` /
`/Users/aruna/Downloads/dutchbay-wt-d3c1b-context-binding`

**Schema:** `dutchbay.d3c_context_binding.v1` / `1.0.0`

## 1. Outcome and boundary

D3C-1b supplies the reciprocal context-binding prerequisite between the delivered D3A, D3B and
D3C surfaces. Its public entry point accepts exactly one D3A `ProjectCase`, one matching D3B-0
`EvaluationRequest`, the original immutable D3B-1 `D3BExecutionSuccess`, an optional strict D3C-1a
projection, one stable D3C-0 authority ID and three bounded in-memory governed artifact payloads.

The authority ID is resolved only through the code-owned D3C-0 production catalogue. That
catalogue remains intentionally empty, so production calls return a structured blocked outcome.
The constructive harness uses only D3C-0's immutable code-owned test-catalogue path; there is no
public accepted-authority or receipt injection parameter.

Only after all reciprocal checks pass does the binder return a strict frozen
`D3CContextBindingCandidate`. It contains the minimum justified candidate D2 input, origin, output
and artifact record graph plus all twenty taxonomy sections in SSOT order. Every section and the
candidate root remain explicitly `unresolved`, `not_performed`, `ungraded` and `hold`; reliance is
not permitted and publication is not authorized.

The result is not a D2 `FeasibilityReportPackage` or `SectionRecord`. It cannot express package
completeness, evidence sufficiency, a professional act, achieved grade, release, lender or Board
acceptance, deployment or publication authority. Package assembly remains D3C-2 and grade,
materiality and release aggregation remain D3D.

## 2. Exact reciprocal binding

Before candidate emission, the implementation independently requires:

- exact ProjectCase, request, report, run, case, revision and D3B/D3C origin identities;
- freshly recomputed ProjectCase and request digests using the resolved-config digest;
- a bounded canonical content digest of the complete accepted D3B success;
- the corresponding bounded canonical content-identity preimage, retained as a non-D4 witness so
  strict Python/JSON re-ingress can reconstruct the same immutable success, recompute its accepted
  digest and freshly reproduce the projection and contextual FX graph;
- a supplied D3C-1a projection that is graph-identical to a fresh pure projection, or the fresh
  projection itself;
- exact runtime-receipt and engine-manifest reconciliation;
- exact authority actor, source, pack, registry, distribution and report bindings; and
- exact role, byte length and SHA-256 equality for the three supplied annual-row, debt-result and
  FX-curve byte payloads against both D3C-0 byte bindings and D2 artifact records.

The binder hashes only the supplied immutable bytes. It never follows a locator and performs no
filesystem, environment, network, persistence or clock I/O. It imports and calls neither the
evaluation gateway nor finance and never sums annual rows or recomputes a KPI.

No D3C-0 authority self-digest or D4 package/payload digest is invented. The dedicated accepted-
success content identity exists solely for the D3C acceptance-ledger binding. It covers every
accepted-success field, including opaque metadata and every annual-row `fx_rate`, while preserving
scalar type and exact IEEE-754 binary64 bytes. Its canonical traversal is mapping-order- and alias-
topology-independent, occurrence-bounded and cycle-refusing. Depth, container, scalar, text,
integer and canonical-byte ceilings produce bounded deterministic failures. The retained canonical
preimage is not a package serialization or an authority self-digest: it is the minimum witness
needed to keep the original accepted D3B success load-bearing after candidate round-trip. A
coordinated edit to a projection, FX derivation and output cannot validate against the unchanged
accepted-success digest.

## 3. Candidate D2 records and precision

The candidate input surface follows the closed D3C acceptance-ledger table. It admits only:

- strict integral unit count with integral semantics;
- exact cost native and reporting amounts with their respective minor-unit precision; and
- exact directed ProjectCase currency-conversion rate with governed quote precision.

Each admitted value retains exact `Decimal` lexical identity and its authored JSON-number lexeme,
plus the ledger context that makes the value meaningful: ProjectCase pointer, family, precision
source, asset/line/conversion identity, periodicity, price basis, directed currency edge and
valuation date as applicable. Source and assumption origins remain distinct explicit edges; the
binder does not mint assumption records or allow a `source:project-basis` edge to be replaced by a
runtime source. Explicit `MissingValue` inputs are retained as missing candidate inputs with their
exact missing-input ID, field path, expected unit, reason, consequence and remedy instead of being
discarded or defaulted.

Carried D3C-1a route observations become candidate D2 output references without changing their
binary64 hex or bytes. The three governed artifacts also become candidate references only after
their actual supplied bytes pass the reciprocal checks. Warnings, degraded status, limitations,
opaque artifacts, unknown-key identities, `None` and unavailable/not-computed/not-representable
route dispositions remain in the complete retained projection rather than being inferred away.

Every output and section reference is checked for exact report/run ownership and dangling or
duplicate identities. Every one of the twenty sections remains an honest unresolved candidate;
capacity, location, finance rows or declared technology never stand in for an engine-less study.

## 4. Directed FX boundary

Contextual FX statistics are admitted only when the exact direction, source and target currencies,
source observation date, conversion/request valuation date, request price basis, source reference,
conversion basis, exact positive expected timeline count, annual-row cardinality and every finite
annual-row binary64 rate agree. The accepted v1 context is the exact `USD` to `LKR` conversion
quoted as `LKR/USD`; an opposite `LKR` to `USD` conversion is refused rather than mathematically
inverted. A matching jurisdiction, currency pair or numeric rate alone is insufficient. Each
candidate statistic carries structured output-to-derivation-to-conversion-input-to-source edges and
its exact binary64 bytes; re-ingress reproduces those facts from the retained accepted-success
witness rather than trusting a self-consistent edited derivation.

The constructive and hostile matrix includes positive directed-context oracles and independent
negative controls for reversed direction, source, quote, price-basis, date, statistic and annual-
rate drift. Two accepted D3B successes that yield equal D3C-1a projections but differ in opaque
metadata or annual `fx_rate` also produce different complete-success identities, preserving the
information-loss counterexamples from the successor handover.

## 5. Strict ingress and bounded failure

Candidate, section, artifact and blocked outcomes use strict frozen Pydantic v2 models with closed
vocabularies and mandatory schema/version identity. Python and JSON ingress reject unknown fields,
wrong scalar types, duplicate JSON keys (including long duplicate names), malformed or non-UTF-8
JSON, non-finite tokens, oversized integers, surrogate code points, non-canonical accepted-success
witnesses, excessive bytes, excessive depth and excessive volume. Validation and serialization
Draft 2020-12 schemas, stable canonical JSON bytes and exact round trips are exercised by the
contract harness. Hostile Python objects cannot execute `repr`, and blocked invalid authority IDs
always serialize through one safe constant sentinel.

All operational refusals use bounded codes, pointers and detail. The public production path emits
no candidate while the D3C-0 catalogue remains empty. The private constructive path requires the
exact immutable `MappingProxyType` catalogue and retains the same code-owned D3C-0 resolver
semantics.

## 6. Recruitment and lease

The D3C-1b pod was staged before the writer lease. One separate renewable/hybrid feasibility-domain
reviewer and one separate assurance/web-contract reviewer freshly ingressed the governed corpus,
accepted only the narrow D3C-1b boundary and remained read-only. The coordinator became sole
writer for the initial exact four-file lease:

- `analytics/feasibility_report_contract/context_binding.py`;
- `tests/contracts/test_d3c_context_binding_contract.py`;
- this implementation record; and
- `changelog.d/d3c1b-context-binding.added.md`.

The first frozen candidate, commit `2a377a5210bc045f7493f40f999146434d920cb5` and tree
`23fb6d3b425f395dac4b391ed1158767c7b05426`, was rejected independently by both reviewers before
push or PR. The domain review found absent exact timeline cardinality, source observation-date and
structured FX provenance checks; source-origin substitution; and lost cost/conversion/MissingValue
context. The assurance review additionally proved material candidate graph drift on Python/JSON
re-ingress, hostile `repr`/surrogate/integer/duplicate-key failures, and evaluator/finance imports
caused solely by loading the D3C contract module. Its otherwise green local receipts do not transfer
to this replacement.

Correction required a documented lease expansion to three import-isolation files:

- `analytics/__init__.py`, to preserve its historical public exports lazily;
- `analytics/core/__init__.py`, to preserve its historical public exports without recreating an
  evaluation import cycle; and
- `analytics/feasibility_report_contract/assembly_authority.py`, to validate section IDs against
  the import-safe canonical taxonomy identity rather than performing filesystem I/O on model
  re-ingress.

No production catalogue, evaluator, finance mathematics, D2 schema, D3C-1a contract or release-
policy file is leased or changed. The interrupted-edit, unexpected-target-drift,
failed-patch-context and coordinator-takeover drills all resolve to stop, preserve and rebind rather
than blind continuation. The same two reviewers must inspect and accept the final exact replacement
SHA before push or PR; chat-only or first-candidate readiness is not acceptance.

## 7. Verification evidence

The corrected focused D3C-1b harness currently executes 55 cases. It covers the implementation
module at 100% statement and branch coverage: 809 statements, 264 branches, zero missed statements
and zero partial branches. The complete contracts regression passes 1,381 tests; a targeted import,
assessment-scope and D3C-0 authority regression passes 429 tests.

The matrix includes the genuine full-result graph, exact reciprocal identity and actual-byte
checks, same-projection/different-success counterexamples, directed FX positive and hostile
oracles, candidate graph re-ingress, strict validation and serialization schemas, canonical
round trips, duplicate-key and Unicode controls, type-sensitive/mapping-order-independent content
identity, alias/cycle/resource bounds, signed-zero binary64 identity, code-owned authority
selection, zero locator I/O, zero gateway/finance rerun spies, a forbidden-import AST guard,
fresh-process import isolation and historical public-facade compatibility. A separately implemented
like-for-like reference encoder, not an implementation helper or pinned value alone, reproduces the
full accepted-success digest and changes for the opaque-metadata counterexample.

| Gate | Candidate result |
|---|---:|
| Persistent Python / GWTF bootstrap | Python `3.12.13`; `73/73` rules; PASS |
| Focused D3C-1b constructive/hostile suite | `55 passed` |
| Focused implementation line/branch coverage | `100.00%` (`809` statements, `264` branches) |
| Targeted import/scope/D3C-0 compatibility regression | `429 passed` |
| Complete `tests/contracts` regression | `1381 passed` |
| Repository-wide Ruff / Black / isort | pass; 742 Python files Black-clean; 4 isort skips |
| Complete governed mypy | zero issues in 269 typed source files and governed entry points |
| Bandit / pinned dependency audit | no medium/high findings; no known vulnerabilities |
| Canonical-finance non-recomputation regression | `31 passed` |
| Full governed ordinary suite | `7402 passed, 18 skipped, 19 warnings` in `615.91s` |
| Full governed coverage floor | `95.42%` (`33442` statements, `1532` missed; `>=95%` required) |

All replacement receipts above use the persistent Python 3.12.13 environment. Named temporary
coverage databases were outside the workspace and removed by the coverage harness at completion.
Qualification-only skips and inherited warnings are not D3C-1b success evidence. Focused,
contract and static gates were rerun after the replacement rebase; if implementation or test bytes
change, receipts do not transfer.

The first rebased full-suite attempt used the repository default `-n auto` worker count. At 80%,
one worker segfaulted while importing the native `dss_python_backend` for
`test_authenticated_inputs_refuse_wrong_digest_and_cross_record_substitution`; pytest replaced the
worker, but the run correctly failed with `7401 passed, 18 skipped`, missing worker coverage and
only `92.52%`. The exact reported test then passed serially. A complete rerun of the identical
ordinary/full/coverage selection with four workers passed as recorded above, including the same
95% floor. The failed high-concurrency receipt is retained here as an environment limitation, not
relabelled as D3C success or hidden by the green reduced-concurrency run.

Exact-head CI remains merge authority and is recorded in the PR rather than predicted here.

## 8. Explicit holds and next dolphin

D3C-1b changes no finance mathematics or committed KPI and therefore does not change `VERSION`.
It creates no production authority, completes no section and does not lift issue `#1110`, release,
lender, Board, deployment, evidence or publication HOLDs.

Only after independent exact-SHA acceptance and protected-main merge may a new clean D3C-2 dolphin
start from fresh `origin/main`. D3C-2 may assemble one complete D2 `FeasibilityReportPackage` only
with `achieved_grade = ungraded` and `package_release.status = hold`. D3D alone may later implement
grade ceilings, materiality and release aggregation.
