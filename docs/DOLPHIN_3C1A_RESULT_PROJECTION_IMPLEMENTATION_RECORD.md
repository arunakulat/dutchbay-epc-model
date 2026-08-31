# Dolphin 3C-1a result-only projection implementation record

**Status:** corrected replacement candidate; exact-SHA review pending; no D2 package assembly or
HOLD movement

**Protected base:** `e40c13a2fbd4bd974078c4d1dd32e4b1e7ebdf3f` (`origin/main`, PR `#1208` merge)

**Branch/worktree:** `codex/d3c1-result-projection` /
`/Users/aruna/Downloads/dutchbay-wt-d3c1-result-projection`

**Schema:** `dutchbay.section_result_facade.v1` / `1.0.0`

## 1. Outcome and boundary

D3C-1a is the smallest reversible result-translation prerequisite left after the D3B-1 executor
and D3C-0 assembly authority merged. It accepts exactly one
`analytics.contracts_v14.D3BExecutionSuccess` with outcome `success` or `degraded_success` and
produces one strict frozen `D3CResultProjection`.

The projection is structurally **non-authoritative**. It contains:

- exact D3B identities, digests, dates and observed engine-manifest fields;
- an independently revalidated, occurrence-bounded origin receipt covering the one-call gateway
  fact, closed validation-module vocabulary, strict `<inline>` full/nested protocol,
  evaluated-config digest and exact duplicated annual/KPI/debt graphs;
- every ordered D3B numeric projection receipt with exact ProjectCase Decimal lexical values,
  authored JSON-number lexemes, binary64 hex and big-endian binary64 bytes;
- the exact gateway-warning tuple, returned D3B warning tuple, complete structured FX integration,
  exact FX-degradation flag and mandatory `upstream_warning_channel_not_exhaustive` limitation;
- one ordered outcome for each of 23 reviewed result-scalar routes;
- all 20 taxonomy sections in canonical YAML order, with route candidates and unresolved
  dependencies only;
- one immutable reviewed disposition for every inspected upstream path, plus explicit
  artifact-only and known-refused summaries; and
- deterministic value-opaque records for every present undeclared inspected key.

It cannot express D2 `SectionRecord`, registry records, package `RunManifest`, capability outcome,
artifact/content digests, package reconciliation, `FeasibilityReportPackage`, section completion,
applicability, evidence sufficiency, review, achieved grade, release, reliance, lender acceptance,
Board approval, deployment or publication. It receives no `ProjectCase`, `EvaluationRequest` or
`AcceptedAssemblyAuthority`; those reciprocal bindings remain D3C-1b/D3C-2 work.

## 2. Full-harness ingress and scope correction

The recruitment corpus was freshly re-ingressed from the current protected head:

1. the canonical GWTF CSV and current canonical CASPER, CESSPIT and CCCDIR definitions;
2. the newest PERSIST-01 handover and named predecessor;
3. D0 discovery/assurance findings and implementation records;
4. D1 contract, validation, audit and independent-review records;
5. D2 package schema, ledger, implementation and independent-review records;
6. D3A, D3B-0, D3B-1 and D3C-0 charters, implementations and reviews;
7. both D3C design records and the binding D3C implementation acceptance ledger; and
8. the D3D grade/release charter, kept outside this dolphin.

The original next-step description combined result translation and complete package assembly. The
domain and assurance challengers independently classified it as a whale and required:

- D3C-1a: this exact immutable result observation;
- D3C-1b: later reciprocal ProjectCase/request/authority binding and candidate D2 records;
- D3C-2: later ungraded held package assembly; and
- D3D: separate achieved-grade and release policy.

A genuine public-gateway run emitted transient runtime warnings while its accepted D3B warning
tuple remained empty and its outcome was `success`. D3C-1a preserves the returned tuple exactly but
always carries the warning-channel limitation; an empty tuple never proves that no upstream warning
occurred.

## 3. Rejected first candidate and correction

The first exact candidate, commit `432061b9aa3b4b0aab958dbabcdf0e4719e9f9b7`, was independently
**rejected** by both domain and assurance challengers. The branch was not pushed and no PR was
opened. Their convergent blockers were:

- incomplete independent D3B-origin reconciliation;
- a blanket zero-is-ambiguous rule contrary to the per-field ledger;
- an expected-key allowlist that could hide deliberately unclassified paths;
- an incorrect pre-IDC balloon denominator;
- dropped D3B numeric receipts and structured FX facts;
- import-time taxonomy filesystem I/O; and
- missing persisted schema, cold-import, no-I/O and real hash-seed traversal controls.

The replacement preserves that rejection as evidence and corrects only the chartered result-only
boundary. No D3C-1b, D3C-2 or D3D concern was pulled into this branch.

## 4. Recruitment, leases and recovery

Recruitment followed the separation-of-duties and lease rules:

- one renewable/finance-domain challenger and one assurance/contract challenger completed
  separate read-only pre-lease dispositions;
- the initial writer passed the corpus and hostile drill, received an exclusive six-file lease,
  but produced only one untracked draft after two bounded prompts;
- that lease was revoked and acknowledged before a successor wrote;
- the successor completed fresh ingress and received the same exclusive lease, but likewise failed
  to put stated corrections on disk after two bounded prompts;
- that lease was revoked and acknowledged; and
- the coordinator invoked the documented stalled-writer takeover exception as sole writer.

No two writers held a live lease concurrently. The first draft remains recoverable: exact bytes
SHA-256 `2af8fee946e29ccd904f39d288cd05b1fb1a147fd258bb9d26238f251a17d667`, Git blob
`16bc7ae293063ba5804b13ba8af73c52f1f13010`, annotated recovery tag
`recovery/d3c1a-contract-draft-2af8fee` (tag object
`f5fdcb7425a25867b5d6c9bc4903794605e9dd5f`).

Assurance's no-filesystem-I/O blocker required one additional pure leaf,
`taxonomy_identity.py`. It is a generated identity projection, not a competing authored SSOT: its
canonical YAML path, exact source SHA-256 and ordered section IDs are bound by committed tests.

## 5. Contract and translation controls

### 5.1 Exact values without D2 authority leakage

The leaf contract imports neither the evaluator nor `analytics.contracts_v14`. It does not reuse D2
`CanonicalValue` or `OutputClass.CANONICAL`. Its local engine-result observation preserves:

- full unrounded `Decimal.from_float` text;
- canonical finite `float.hex()` identity, including signed zero and subnormal values;
- exact big-endian IEEE-754 binary64 bytes;
- a reviewed static unit and mandatory meaningful-precision metadata; and
- a single static route and section-candidate set.

Identity-critical string validators run before Pydantic conversion and require exact `str`.
SHA-256, Git commit, UTC timestamp, integer lexical, authored-number lexical and binary64 byte/hex
shapes are independently validated.

### 5.2 Independent origin reconciliation

`analytics.feasibility_result_projection.project_d3b_result()` is the only public entry point. Its
signature has one parameter and imports no evaluator, finance, application, API, renderer,
persistence, network or filesystem surface.

Before any scalar route is inspected, the adapter independently detaches and validates the exact
frozen graph with depth/container/scalar/text occurrence bounds and cycle refusal. Its comparator
distinguishes scalar types, mapping-key types and IEEE-754 bytes, including zero sign. It rechecks:

- exactly one gateway call and the closed validation-module vocabulary;
- exact success/degraded outcome, top-warning and structured-FX coherence;
- strict top/nested `config_path` and `validation_mode` literals;
- complete top/nested annual-row, KPI and debt graphs;
- ScenarioResult config against the evaluated-config digest;
- KPI/ScenarioResult/debt reciprocal mirrors; and
- exact manifest identity and evaluated digest.

It imports none of D3B's private comparator or private gateway validator. Every numeric projection
receipt is revalidated and projected in order with unique assertion identity.

### 5.3 Route states, zero policy, balloon basis and FX context

Each reviewed route becomes exactly one of `carried`, `ambiguous_default`, `upstream_none`,
`not_computed` or `not_representable`.

Only `project_irr` and `project_npv` declare exact zero as `ambiguous_default`, because their ledger
rows identify zero as an upstream-default ambiguity. Exact finite zero remains carryable for every
other authorized family, including zero LKR/USD/DFI tranche principal, zero total IDC and a fully
amortized balloon; signed-zero bytes remain exact.

`balloon_pct` is reconciled against only the explicit IDC-inclusive `principal_by_tranche` basis and
`balloon_remaining`. Missing, nonpositive, negative or disagreeing bases are
`not_representable`; pre-IDC `debt_total` is never substituted. The check validates an accepted
output against its explicit operands and never emits a recomputed replacement.

FX statistics distinguish absent, upstream `None`, wrong-type and present-but-context-unbound
states. Present finite values remain `not_representable` until D3C-1b supplies the exact directed
ProjectCase conversion, request price basis, timeline and source/date binding.

### 5.4 Total path dispositions and pure taxonomy binding

The old expected-key allowlist was replaced by an immutable path-disposition catalogue. Every
inspected path has exactly one role: route candidate, mirror operand, predicate operand, origin
invariant, manifest projection, structured projection/container, opaque artifact or known refusal.
Inspected-key sets are derived from the catalogue, so an expected-but-silent path cannot exist.

Present undeclared keys are ordered by exact key kind and identity without copying their values.
String, integer, boolean and binary64 key identities are distinct; binary64 keys retain hex and
bytes. More than 512 unknowns, unsupported key types or resource-bound violations fail with a
bounded code and pointer.

The contract/translator performs no filesystem I/O. The import-safe taxonomy identity leaf carries
the generated ordered IDs and source SHA; tests bind both back to
`config/feasibility_sections.yaml`. Runtime metrics, metadata, annual columns, schedules and the FX
curve remain explicitly opaque/artifact-only. Finite `annual_rows[*].cfads_usd` is checked only as a
predicate for the already-computed total; it is never summed.

## 6. Verification evidence

The corrected focused suite contains 111 tests and covers all three changed implementation modules
at **100% line and branch coverage** (951 statements and 416 branches). Persistent controls include:

- one genuine public gateway reached through D3B and then projected without a second call;
- an evaluator spy and import-direction control proving no D3C gateway/finance invocation;
- exact subnormal, per-route zero, signed-zero and balloon-basis oracles;
- absent/`None`/wrong-type/context-unbound state separation;
- exact unknown-key separation, ordering, value-opacity and resource bounds;
- both Draft 2020-12 schema modes, canonical JSON validation, round trip and fresh-schema isolation;
- the complete gateway/module/status/path/mode/config/duplicate/warning/FX/receipt hostile matrix;
- taxonomy checksum parity, fresh-process no-I/O import/call and three cold-import orders;
- total static and observed path-disposition parity; and
- hash-seed-stable real unknown traversal and first origin failure.

The corrected genuine public oracle produced 23 route outcomes: 19 `carried`, one `not_computed`
and three `not_representable`. Legitimate zero LKR/DFI principals are carried; three present FX
statistics remain context-unbound. It projected four ordered numeric receipts, surfaced no
unclassified live key and emitted fourteen static exclusion summaries. These counts describe that
fixture only and confer no grade or release meaning.

The pre-change `tests/contracts` baseline was `1200 passed, 1 warning`. Replacement receipts:

| Gate | Replacement candidate result |
|---|---:|
| Focused D3C-1a hostile/oracle suite | `111 passed` |
| Focused changed-module line/branch coverage | `100.00%` (`951` statements, `416` branches) |
| Ruff / Black / isort / Bandit | pass |
| Narrow mypy over three implementation modules | `Success: no issues found` |
| Complete `tests/contracts` gate | `1312 passed, 1 inherited warning` |
| Full governed ordinary suite | pending replacement exact-head run |
| Full governed coverage floor | pending replacement exact-head run (`>=95%` required) |

Inherited warnings/skips are not D3C success evidence. Exact-head CI remains merge authority and is
recorded in the PR rather than predicted here.

## 7. Explicit holds and next dolphins

This candidate changes no financial mathematics or committed result and therefore does not change
`VERSION`. It does not lift issue `#1110`, release, lender, Board, deployment, evidence or
publication HOLDs.

After independent exact-SHA acceptance and protected-main merge, the next permissible work is:

1. D3C-1b: bind one exact projection to one exact D3A `ProjectCase`, one exact
   `EvaluationRequest` and one selected accepted D3C-0 authority;
2. emit candidate D2 records only after reciprocal origin checks, retaining explicit unresolved
   completeness/evidence/review/grade facts;
3. keep D3C-2 held package construction separately reversible; and
4. leave achieved grade/release aggregation exclusively to D3D.
