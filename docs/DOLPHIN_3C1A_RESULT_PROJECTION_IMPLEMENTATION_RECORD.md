# Dolphin 3C-1a result-only projection implementation record

**Status:** implementation candidate; independently reviewable; no D2 package assembly or HOLD
movement
**Protected base:** `e40c13a2fbd4bd974078c4d1dd32e4b1e7ebdf3f` (`origin/main`, PR `#1208` merge)
**Branch/worktree:** `codex/d3c1-result-projection` /
`/Users/aruna/Downloads/dutchbay-wt-d3c1-result-projection`
**Schema:** `dutchbay.section_result_facade.v1` / `1.0.0`

## 1. Outcome and boundary

D3C-1a implements the smallest reversible result-translation prerequisite left after the D3B-1
executor and D3C-0 assembly authority merged. It accepts **exactly one**
`analytics.contracts_v14.D3BExecutionSuccess` with outcome `success` or `degraded_success` and
produces a strict frozen `D3CResultProjection`.

The output is intentionally and structurally **non-authoritative**. It contains:

- exact D3B origin identities, dates and the observed engine-manifest fields;
- the exact returned D3B warning tuple, exact FX-degradation flag and mandatory
  `upstream_warning_channel_not_exhaustive` limitation;
- one ordered outcome for each of 23 reviewed result-scalar routes;
- all 20 taxonomy sections in YAML SSOT order, with route candidates and unresolved dependencies
  only;
- explicit artifact-only and known-refused path dispositions; and
- deterministic, value-opaque records for every present undeclared key in each inspected mapping.

It cannot express D2 `SectionRecord`, register records, `RunManifest`, capability disposition,
artifact/content digests, reconciliation, `FeasibilityReportPackage`, section completion,
applicability, evidence sufficiency, review, achieved grade, release, reliance, lender acceptance,
Board approval, deployment or publication. It receives no `ProjectCase`, `EvaluationRequest` or
`AcceptedAssemblyAuthority`; those reciprocal bindings remain D3C-1b/D3C-2 work.

## 2. Full-harness ingress and scope correction

The recruitment corpus was freshly re-ingressed from the current protected head, not carried from
the prior session:

1. the canonical GWTF CSV and the current canonical definitions of CASPER, CESSPIT and CCCDIR;
2. the newest PERSIST-01 handover and named predecessor;
3. D0 discovery/assurance findings and implementation records;
4. D1 contract, validation, audit and independent-review records;
5. D2 package schema, ledger, implementation and independent-review records;
6. D3A, D3B-0, D3B-1 and D3C-0 charters, implementations and independent reviews;
7. both D3C design records and the binding D3C implementation acceptance ledger; and
8. the D3D grade/release charter, kept outside this dolphin.

The original next-step description combined result translation and complete package assembly. The
domain and assurance challengers independently classified that as a whale. They required this
result-only D3C-1a split before a writer lease:

- D3C-1a: this exact immutable observation projection;
- D3C-1b: later reciprocal ProjectCase/request/authority binding and candidate register records;
- D3C-2: later ungraded held package assembly; and
- D3D: separate achieved-grade and release policy, unchanged.

The scope correction is material. A genuine public-gateway run emitted runtime warnings while its
accepted D3B warning tuple remained empty and its outcome was `success`. D3C-1a therefore preserves
the returned tuple exactly but **always** carries the warning-channel limitation; an empty tuple is
never described as proof that no upstream warning occurred.

## 3. Recruitment, leases and recovery

Recruitment followed the controlling separation-of-duties and lease rules:

- one renewable/finance-domain challenger completed a read-only pre-lease disposition;
- one assurance/contract challenger completed a separate read-only pre-lease disposition;
- the initial exclusive writer passed the corpus and hostile-drill gate, received a six-file lease,
  but produced only one untracked contract draft after two bounded prompts;
- that lease was explicitly revoked and acknowledged before any successor was allowed to write;
- a successor writer completed fresh ingress and received the same exclusive lease, but likewise
  failed to put its stated corrections on disk after two bounded prompts;
- the successor lease was explicitly revoked and acknowledged; and
- the coordinator then invoked the documented stalled-writer takeover exception as the sole writer.

No two writers held a live lease concurrently. The original draft was not discarded: its exact
bytes (`SHA-256 2af8fee946e29ccd904f39d288cd05b1fb1a147fd258bb9d26238f251a17d667`) are retained as Git
blob `16bc7ae293063ba5804b13ba8af73c52f1f13010` under the recovery tag
`recovery/d3c1a-contract-draft-2af8fee`. The final candidate corrects that draft rather than hiding
its failed controls.

## 4. Contract and translation controls

### 4.1 Exact values without D2 authority leakage

The leaf contract package imports neither the evaluator nor `analytics.contracts_v14`. It does not
reuse D2 `CanonicalValue` or `OutputClass.CANONICAL`. Its local value shape is an engine-result
**observation** with:

- exact full unrounded decimal text from `Decimal.from_float`;
- canonical finite `float.hex()` identity, accepting normals, signed zero and subnormals;
- exact big-endian IEEE-754 binary64 bytes;
- a reviewed static unit;
- mandatory reviewed meaningful precision as metadata, never rounding or accuracy; and
- a single static route and section-candidate set.

All identity-critical string validators run before Pydantic conversion and require exact `str`, so
numeric inputs and string subclasses cannot be coerced into accepted identities. SHA-256, Git
commit, UTC timestamp, integer lexical and binary64 byte/hex shapes are separately validated.

### 4.2 Closed translation and absence states

`analytics.feasibility_result_projection.project_d3b_result()` is the only public translation
entry point. Its signature contains one parameter and the module imports no evaluator, finance,
application, API, renderer, persistence, network or filesystem surface. It never recalculates IRR,
NPV, DSCR, CFADS, debt, balloon or FX values.

Each reviewed route becomes exactly one of:

- `carried` — exact finite type, mirror and route predicate satisfied;
- `ambiguous_default` — exact `+0.0` or `-0.0` without a computation-status receipt;
- `upstream_none` — the exact key exists with `None`;
- `not_computed` — a required exact source/status/series/context is absent; or
- `not_representable` — wrong exact type, missing/mismatched mirror or failed closed predicate.

FX statistics are always unavailable in D3C-1a even when present because the required same-direction
ProjectCase conversion, request price basis, annual timeline and source/date binding are deliberately
outside this result-only slice.

### 4.3 Unknown and artifact fields

Every mapping that the translator traverses has a closed expected-key catalogue, including nested
principal, WACC, equity-performance and annual-row mappings. Present undeclared keys are sorted by
exact key kind and identity, then surfaced deterministically without copying or inspecting their
values. String, integer, boolean and binary64 key identities are distinct; binary64 keys carry both
canonical text and bytes. More than 512 unknowns, unsupported key types, unbounded/control-bearing
string identities or malformed origin structures fail closed with a bounded code and RFC 6901
pointer.

Annual rows, schedules and the FX curve remain artifact-only. This slice checks finite
`annual_rows[*].cfads_usd` only as the accepted predicate for carrying the already-computed total; it
does not sum or type the rows and does not mint an artifact digest.

## 5. Verification evidence

The focused suite contains 71 tests and covers both changed implementation modules at **100% line
and branch coverage** (586 statements and 240 branches). It includes:

- a genuine public `evaluate_with_overrides(..., return_full_result=True)` path reached only through
  the accepted D3B executor, then handed to D3C-1a without a second call;
- an evaluator spy and import-direction AST control proving zero D3C gateway/finance calls;
- exact subnormal and signed-zero identity controls;
- absent, `None`, wrong-type, mirror-mismatch, empty-series, no-live-debt, balloon-basis,
  prudential-status and FX-context refusals;
- string/integer/boolean/binary64 unknown-key separation, insertion-order invariance, value-opacity
  and bounded-volume refusal;
- strict model/schema identity, frozen/extra-forbid, JSON round-trip and caller-constructed-substitute
  controls;
- post-construction origin-tampering and manifest-identity refusals; and
- fresh-process hash-seed invariance of the first exact validation error.

The genuine public oracle produced 23 route outcomes: 17 `carried`, four `not_computed`, and two
`ambiguous_default`; it surfaced 59 present undeclared keys and nine static excluded-field records.
Those counts describe that fixture only and confer no grade or release meaning.

The pre-change `tests/contracts` baseline was `1200 passed, 1 warning`. The candidate receipts are:

| Gate | Candidate result |
|---|---:|
| Focused D3C-1a hostile/oracle suite | `71 passed` |
| Focused changed-module line/branch coverage | `100.00%` (`586` statements, `240` branches) |
| Complete `tests/contracts` gate | `1271 passed` |
| Full governed ordinary suite | `7292 passed, 18 skipped, 24 warnings` |
| Full governed coverage floor | `95.25%` (`>=95%` required) |
| Narrow mypy over both implementation modules | `Success: no issues found` |

The inherited full-suite warnings and skips include optional-dependency/qualification isolation and
existing deprecation/runtime warnings; they are not D3C success evidence and do not lift any HOLD.
Exact-head CI remains the merge authority and is recorded in the PR rather than predicted here.

## 6. Explicit holds and next dolphins

This candidate changes no financial mathematics or committed result, so it does not change
`VERSION`. It does not lift issue `#1110`, release, lender, Board, deployment, evidence or
publication HOLDs.

The next permissible work is **not** to expand this slice in place. After independent exact-SHA
acceptance and protected-main merge:

1. charter D3C-1b to bind one exact projection to the one exact D3A `ProjectCase`, one exact
   `EvaluationRequest` and one selected accepted D3C-0 authority, with reciprocal origin checks;
2. emit candidate D2 register records only after those checks, leaving completeness, evidence,
   review and grade facts explicit and unresolved;
3. keep D3C-2 package construction separately reversible; and
4. leave grade/release aggregation exclusively to D3D.
