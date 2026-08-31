# Dolphin 3B-1 execution-seam implementation record

**Status:** seventh exact production/test freeze independently domain and assurance accepted;
protected exact-head CI green at 95.03% aggregate coverage
**Base:** `dc2b211954f67c9d010831350e51884c9fe79c52` (`origin/main`, synchronized
2026-08-31)  
**Branch:** `codex/d3b-v14-execution-seam-r2`  
**Governed runtime:** `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, Python 3.12.13  
**Release, grade, professional, lender, Board and deployment authority:** none

## 1. Delivered boundary

D3B-1 adds one held execution seam from one exact D3A `ProjectCase` and one accepted D3B-0
`EvaluationRequest` to the canonical public v14 gateway. The public function accepts only the case,
request and a module-owned authority ID. A caller cannot supply a path, authority object, selector,
generic override or dotted-path rule.

Before computation, the seam:

- binds the exact ProjectCase and request digests to a code-owned authored-scenario record;
- binds explicit jurisdiction-subject/domain and technology-key/kind facts rather than inferring
  either from free text or key names;
- binds evidence cutoff, valuation date, their authority source IDs, price basis, nominality and
  reporting currency;
- resolves one exact normalized `.yaml`, `.yml` or `.json` path beneath `scenarios/`, refusing
  symlinks, traversal, suffix inference and noncanonical spellings;
- opens every absolute path component through anchored directory descriptors with `O_NOFOLLOW`,
  requires a regular file no larger than 16 MiB, reads one exact inode once, hashes those bytes,
  makes the public loader parse those exact verified bytes, and rechecks the authorized path digest
  and inode receipt after loading;
- refuses scenario-declared approved-source manifests at this held boundary and validates any AEP
  source only against a detached copy of the immutable code-owned built-in manifest, never a
  process-global registry widened by an earlier scenario load;
- requires the authored canonical repository-relative `meta.source_path` and the exact loaded
  config digest;
- runs the public strict v14 schema guard for the request's exact validation modules;
- reconciles the live ProjectCase element sets, closed material dispositions, binding-specific
  subject jurisdictions, explicit technology authorities, scalar selectors, units,
  electrical/capacity bases, cost line kind and exact periodicity, price basis and authored
  redundancies;
- discloses each ProjectCase Decimal-to-authored-binary64 comparison through a bounded receipt
  carrying the original Decimal spelling and exact `float.hex()` value, while refusing nonzero
  underflow to signed zero and requiring exact equality for every authored integer; and
- permits only an empty override or the canonical scope-owned `run.mode` addition.

Only after all preflight controls pass does the function make the sole syntactic and runtime call:

```python
evaluate_with_overrides(
    raw_config=config,
    overrides=overrides,
    validation_modules=validation_modules,
    return_full_result=True,
)
```

The executor imports that symbol inside the public function. It imports no finance, pipeline, app,
API, renderer or persistence module and contains no finance mathematics.

## 2. Result and failure boundary

A successful result preserves the actual current v14 full-result surface, including
`scenario_result`, `kpis`, `annual_rows`, `debt_result`, metadata, FX state, warnings, `None`, the
engine manifest and the engine's legacy finite float-keyed and tuple-valued debt structures. The
handoff also repeats the exact verified ProjectCase and EvaluationRequest content digests so D3C
can independently recompute and refuse an ID-matching but content-different input. The
snapshot is recursively immutable, contract-owned and resource-bounded. The exported success
constructor recursively detaches even read-only proxy inputs from caller-retained mapping backings
before accepting them; mutation of an input backing after construction cannot change the handoff.
Shared acyclic legacy containers preserve their alias identity; a separate occurrence-volume pass
prevents a small alias DAG from expanding without bound during comparison or serialization. Cycles,
excessive depth/volume, unsupported objects, non-finite values and unsupported keys fail closed. The
separately exposed engine manifest is the identical owned frozen subtree and remains strictly
string-keyed.

Before a result can enter that snapshot, the seam freezes it once and validates the current public
gateway protocol against that immutable object: required mappings and sequences, nonempty
annual/debt/config/metadata surfaces, exact nested/top-level annual-row, debt and KPI equality,
exact evaluated-config digest, canonical `<inline>` origins, strict validation mode, finite canonical
scalars, strict FX degradation coherence, the required seed key, current engine and manifest-schema
versions, a real Git SHA and UTC timestamp. Duplicate surfaces use a bounded comparator that
requires identical scalar and mapping-key types and identical binary64 hex values, including signed
zero; ordinary Python coercive equality is not the oracle. A structurally convenient but
semantically malformed fake success is therefore a one-call failure, not a D3C input.

Every refusal or failure carries a closed code, closed phase and exact zero/one gateway call count.
The real Python exception is retained for in-process diagnostics, but serialization emits only its
bounded type name and never arbitrary exception or configuration text. A gateway exception is not
retried. A malformed or digest-mismatched result cannot become a success-like object.

The current full-result object is an internal D3B-to-D3C handoff, not a web response. Its preserved
legacy float mapping keys mean a future HTTP/JSON adapter must define its own explicit safe
projection; D3B does not invent that adapter or silently stringify those keys.

## 3. Constructive and hostile evidence

The focused suite exercises:

- wind-only, solar-DC, storage-only, common-POI wind+BESS and explicit legacy single-wind turbine
  constructive cases;
- storage MW × hours = MWh reconciliation and mismatch;
- fictional multi-subject and same-subject multi-jurisdiction routing without Sri Lankan fallback;
- exact and adjacent binary64 projections with disclosure receipts;
- forged numeric spellings/hex receipts, nonzero underflow, adjacent large-integer collapse,
  nonannual OPEX and binding/domain ordering refusals;
- exact canonical run posture, absent canonical run posture and legacy alias refusal;
- bound missing values versus unrelated D3B-v1-excluded missing inputs;
- code-owned authority-fact tampering, path normalization, suffix, symlink-swap and oversized-source
  attacks;
- schema failure, exact-byte loader drift, source-read resource failure, ambient/external AEP
  authority, conflicting gateway duplicate surfaces, bool/int/float and signed-zero collapse,
  typed mapping-key drift, jointly changed noncanonical origins, result-protocol failure and
  failure-text redaction;
- actual mutable-result containment, caller-retained proxy-backing isolation, shared-container
  aliasing, cycle/depth/volume controls;
- injected allocation failures at every pre-gateway helper boundary, typed to their exact closed
  phase and code, plus exported receipt/module/count bounds;
- exactly one public gateway call and no direct finance/pipeline import by AST; and
- three fresh-interpreter import orders.

The independent real-gateway oracle deliberately does not patch the evaluator. It executes the
controlled fictional ProjectCase/config through the public v14 gateway with
`return_full_result=True` and proves that the current engine returns one accepted result containing
25 annual rows, the full debt result, metadata, preserved `None`, strict manifest identity and the
legacy float year keys that a flat KPI fixture would lose. This test corrected two false early
assumptions in the implementation: that nested result keys were string-only and that result
sequences were list-only.

Local evidence at the uncommitted candidate:

| Gate | Result |
|---|---:|
| Governed environment receipt | PASS, Python 3.12.13 |
| GWTF bootstrap | PASS, v3.0, 73 active rules |
| Focused D3B-1 suite | 138 passed |
| Complete `tests/contracts` | 1,097 passed |
| Affected loader/AEP/evaluator/manifest/BESS/pipeline regressions | 487 passed |
| Inherited Dolphin 2 import/taxonomy gate | 386 passed |
| Evaluator/manifest/BESS/pipeline regressions | 272 passed, including both native grid tests serially |
| Ruff check and format, Black and isort | PASS |
| Complete governed mypy, no incremental cache | PASS, 263 source files |
| Governed scripts mypy, no incremental cache | PASS, 67 source files |
| `git diff --check` | PASS |
| Sixth-freeze exact full local test and coverage gate | 7,115 passed, 18 skipped; 95.02% aggregate coverage |
| Seventh-freeze full local attempt | 7,117 passed, 18 skipped; one macOS OpenDSS worker crashed, so no aggregate-coverage PASS claimed |
| Exact serial native-grid recovery | 4 passed |

The THREAD-01 split startup receipt also passed: `check_venv.sh --no-bootstrap` selected the
persistent governed Python 3.12.13 environment with this worktree first on `PYTHONPATH`, and
`dutchbay_bootstrap_rules.py` loaded 73 active v3.0 rules. The legacy combined
`check_venv.sh --run-bootstrap` path is not claimed as passing: its older bootstrap still searches
for a checkout-local `.venv`, which THREAD-01 prohibits for this configured host. No replacement
environment was created.

An earlier pre-remediation full local xdist/coverage run completed 7,010 tests and skipped 18, but
two macOS native workers exited during Numba/llvmlite startup and did not return coverage. Both
exact affected tests pass in the final serial regression selection above. A later third-candidate
run completed 7,062 tests with 18 skips and no test or worker failure, but its aggregate 94.87%
coverage missed the 95.00% gate. Neither earlier run is claimed as an exact-final-tree green full
gate. The fourth candidate completed a local gate with 7,109 passing tests and 95.05% coverage, but
independent assurance then proved four pre-gateway allocation failures could escape its typed
failure boundary. That exact freeze was vetoed. The fifth candidate closed those four sites and
completed a local gate with 7,113 passing tests and 95.05% coverage, but assurance then proved that
the exported success constructor could accept a caller-owned mapping proxy whose retained backing
remained mutable after validation. That exact freeze was also vetoed. This sixth candidate
recursively detaches all accepted proxy trees into contract-owned storage, preserves safe aliases,
refuses cycles, and has hostile controls proving retained annual-row, manifest and root backings
cannot mutate the handoff. Its exact final local gate completed with 7,115 passing tests, 18
governed skips, all workers returned and 95.02% aggregate coverage. Protected exact-head Linux CI
then passed every test shard on commit `6bef07913d06a75af2b5588796a16df66225a98e` but failed the
combined coverage gate at 94.98% (`1,556` missed of `30,981` executable statements). Green test
shards and the prior local coverage result did not override that exact-head failure.

The seventh freeze changes no production source. It adds hostile controls for mapping cycles,
mapping-specific container/text bounds, exact numeric equality, canonical digest refusal,
unsupported scalar selectors, run-posture ambiguity and mismatched technology keys. On the local
coverage trace these controls reduced the new executor's missed statements from 57 to 42. The exact
full local attempt executed 7,117 passing tests and 18 governed skips, but one xdist worker
segfaulted while importing the macOS OpenDSS native backend; that worker returned neither its test
result nor coverage data. The exact affected native-grid file then passed all four tests serially.
This is not claimed as a green aggregate local gate. Fresh dual review and protected exact-head
Linux CI remained required before merge. The independent domain and assurance reviewers then
accepted exact committed production/test head
`b6d50cb895acde505520d324c6e0f8e299bd922d`. Protected Linux run `33387739842` passed all six
test shards, grid, quality, security and summary gates and combined `30,981` executable statements
with `1,541` missed, or 95.03% aggregate coverage. The documentation-only persistence of those
receipts remains subject to an exact documentation rebind and protected checks; it does not alter
the accepted production or test bytes.

These are engineering evidence only. They establish no professional conclusion, achieved grade,
evidence sufficiency, lender acceptance, package approval or release authority.

## 4. Deliberate production hold

The module-owned production authority catalogue is intentionally empty. No current committed
scenario has the complete governed metadata required by this seam: top-level `scenario_name`,
canonical authored repository-relative `meta.source_path`, subject-routed jurisdiction facts and a
dated cutoff/valuation authority binding. The committed candidates must therefore continue to fail
closed rather than obtaining identity from a filename, `project.name`, country-name heuristic or
Sri Lankan default.

A separate small governed scenario-metadata/authority dolphin must select one scenario, add or bind
those exact facts, construct its exact ProjectCase/request pair and add one immutable production
catalogue entry. That prerequisite may not alter finance mathematics or hide inside D3C. The
controlled test catalogue proves the D3B seam and the real gateway shape; it is not a project,
jurisdiction, evidence or release authority pack.

## 5. Downstream D3C gate

D3C remains held until this exact D3B-1 candidate is independently accepted, merged through the
protected branch, and protected `main` is resynchronized. D3C must train only on that merged corpus.
It consumes one `D3BExecutionSuccess`, the matching exact ProjectCase/request and separately
governed D2 report/run assembly identity; it never aliases `request_id` into a D2 identity and
never imports or calls the evaluator.

The restored D3C requirements omitted by the earlier contract-only charter are controlled by
[`DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md`](DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md).
They include every D2 register, the engine-manifest-to-D2-manifest bridge, visible unperformed human
roles, all twenty sections, all six reconciliation families and a static field-to-section mapping.

The exact independent dispositions, review probes, fingerprints and limitations are persisted in
[`DOLPHIN_3B1_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_3B1_INDEPENDENT_REVIEW_RECORD.md).

## 6. Unchanged authority state

Issue `#1110` remains outside D3B. Its 23 controls, Board/lender circulation `HOLD`, evidence
sufficiency, professional review, package release and deployment authority cannot be changed by a
successful calculation, local gate, CI result, independent engineering acceptance or merge.
`VERSION` remains `15.4.0`; no finance output or KPI baseline is changed by this dolphin.
