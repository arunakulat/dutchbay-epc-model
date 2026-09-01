# Dolphin 3C-1b context-binding implementation record

**Status:** implementation candidate and full local verification complete; independent exact-SHA
review pending; no D2 package assembly or HOLD movement

**Protected base:** `be1956413b407b299d6b116e79bd84456ef62b2d` (`origin/main` at lease)

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
integer and canonical-byte ceilings produce bounded deterministic failures.

## 3. Candidate D2 records and precision

The candidate input surface follows the closed D3C acceptance-ledger table. It admits only:

- strict integral unit count with integral semantics;
- exact cost native and reporting amounts with their respective minor-unit precision; and
- exact directed ProjectCase currency-conversion rate with governed quote precision.

Each admitted value retains exact `Decimal` lexical identity and its authored JSON-number lexeme.
Source and assumption origins remain distinct explicit edges; the binder does not mint assumption
records. Explicit missing inputs remain missing instead of becoming defaults.

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
observation date, request price basis, source reference, conversion basis, annual-row count and
every finite annual-row rate agree. The accepted v1 context is the exact `USD` to `LKR` conversion
quoted as `LKR/USD`; an opposite `LKR` to `USD` conversion is refused rather than mathematically
inverted. A matching jurisdiction, currency pair or numeric rate alone is insufficient.

The constructive and hostile matrix includes positive directed-context oracles and independent
negative controls for reversed direction, source, quote, price-basis, date, statistic and annual-
rate drift. Two accepted D3B successes that yield equal D3C-1a projections but differ in opaque
metadata or annual `fx_rate` also produce different complete-success identities, preserving the
information-loss counterexamples from the successor handover.

## 5. Strict ingress and bounded failure

Candidate, section, artifact and blocked outcomes use strict frozen Pydantic v2 models with closed
vocabularies and mandatory schema/version identity. Python and JSON ingress reject unknown fields,
wrong scalar types, duplicate JSON keys, malformed or non-UTF-8 JSON, non-finite tokens, surrogate
code points, excessive depth and excessive volume. Validation and serialization Draft 2020-12
schemas, stable canonical JSON bytes and exact round trips are exercised by the contract harness.

All operational refusals use bounded codes, pointers and detail. The public production path emits
no candidate while the D3C-0 catalogue remains empty. The private constructive path requires the
exact immutable `MappingProxyType` catalogue and retains the same code-owned D3C-0 resolver
semantics.

## 6. Recruitment and lease

The D3C-1b pod was staged before the writer lease. One separate renewable/hybrid feasibility-domain
reviewer and one separate assurance/web-contract reviewer freshly ingressed the governed corpus,
accepted only the narrow D3C-1b boundary and remained read-only. The coordinator became sole
writer for the exact four-file lease:

- `analytics/feasibility_report_contract/context_binding.py`;
- `tests/contracts/test_d3c_context_binding_contract.py`;
- this implementation record; and
- `changelog.d/d3c1b-context-binding.added.md`.

No production catalogue, evaluator, finance, D2 schema, D3C-1a contract or release-policy file is
leased or changed. The interrupted-edit, unexpected-target-drift, failed-patch-context and
coordinator-takeover drills all resolve to stop, preserve and rebind rather than blind continuation.
The same two reviewers must inspect and accept the final exact candidate SHA before push or PR;
chat-only or pre-lease readiness is not acceptance.

## 7. Verification evidence

The focused D3C-1b harness currently contains 29 test functions and 38 executed cases. It covers
the new implementation module at 100% statement and branch coverage: 528 statements, 160 branches,
zero missed statements and zero partial branches. The complete contracts regression currently
passes 1,364 tests.

The matrix includes the genuine full-result graph, exact reciprocal identity and actual-byte
checks, same-projection/different-success counterexamples, directed FX positive and hostile
oracles, candidate graph re-ingress, strict validation and serialization schemas, canonical
round trips, duplicate-key and Unicode controls, type-sensitive/mapping-order-independent content
identity, alias/cycle/resource bounds, signed-zero binary64 identity, code-owned authority
selection, zero locator I/O, zero gateway/finance rerun spies and a forbidden-import AST guard.

| Gate | Candidate result |
|---|---:|
| Persistent Python / GWTF bootstrap | Python `3.12.13`; `73/73` rules; PASS |
| Focused D3C-1b constructive/hostile suite | `38 passed` |
| Focused implementation line/branch coverage | `100.00%` (`528` statements, `160` branches) |
| Complete `tests/contracts` regression | `1364 passed` |
| Repository-wide Ruff / Black / isort | pass; 742 Python files Black-clean; 4 isort skips |
| Complete governed mypy | zero issues in 269 typed source files and 67 scripts |
| Bandit / pinned dependency audit | no medium/high findings; no known vulnerabilities |
| Canonical-finance non-recomputation regression | `29 passed` |
| Full governed ordinary suite | `7385 passed, 18 skipped, 24 warnings` in `757.76s` |
| Full governed coverage floor | `95.39%` (`33135` statements, `1527` missed; `>=95%` required) |

The full governed run used the persistent Python 3.12.13 environment and the leased candidate code
and tests. The named temporary coverage database was outside the workspace and was removed by the
coverage harness at completion. Qualification-only skips and inherited warnings are not D3C-1b
success evidence. Focused, contract and static gates are rerun after the exact review head is
frozen; if implementation or test bytes change, these receipts do not transfer to the replacement.

Exact-head CI remains merge authority and is recorded in the PR rather than predicted here.

## 8. Explicit holds and next dolphin

D3C-1b changes no finance mathematics or committed KPI and therefore does not change `VERSION`.
It creates no production authority, completes no section and does not lift issue `#1110`, release,
lender, Board, deployment, evidence or publication HOLDs.

Only after independent exact-SHA acceptance and protected-main merge may a new clean D3C-2 dolphin
start from fresh `origin/main`. D3C-2 may assemble one complete D2 `FeasibilityReportPackage` only
with `achieved_grade = ungraded` and `package_release.status = hold`. D3D alone may later implement
grade ceilings, materiality and release aggregation.
