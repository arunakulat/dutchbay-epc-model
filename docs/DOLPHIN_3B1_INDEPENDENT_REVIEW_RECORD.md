# Dolphin 3B-1 independent review record

**Review date:** 2026-08-31  
**Disposition:** `DOMAIN ACCEPT`; `ASSURANCE ACCEPT`  
**Accepted base:** `dc2b211954f67c9d010831350e51884c9fe79c52`  
**Branch:** `codex/d3b-v14-execution-seam-r2`  
**Governed runtime:** `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, Python 3.12.13  
**Merge state at latest production/test review:** exact committed head `b6d50cb895acde505520d324c6e0f8e299bd922d` independently accepted and protected exact-head CI green; this receipt update remains documentation-only

## 1. Exact accepted implementation freeze

The two independent reviews were bound to these eight exact files:

```text
ecd83ad49cd76e3720cb6f2866c7a4bbdeb04c5bed3cb39c5db8b1c91c00296d  analytics/aep_provenance.py
ec2ad2ae3a8b494ccdb57c033db5d659038faf980f6d1ca30d144ddbb61d0d66  analytics/contracts_v14.py
15c887b6fe6f430328f49092fd4af27fb81d501411add19b28ab3d545a7d0c2f  analytics/loader/aep_loader.py
b8bb85a7e1b788ff9ca34231f63ec86797b4b4022dfc53218e3c190a63e84f32  analytics/scenario_loader.py
42bf1df615c8f5e475a2c08109119f068946eb60d93691a070ec890df98f2fe8  analytics/feasibility_execution.py
082660117780dcb75e7f1067a1969198bc26e83145d1914a1506b756901ef86e  docs/DOLPHIN_3B1_EXECUTION_IMPLEMENTATION_RECORD.md
3842b736ca75775353027b5b941680daee51f918bbf98b14aee5edf029337a44  docs/DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md
720c58884bc0152c18f9c753eb802fdbbebab1dc66c925641d28451ac96fb5ff  tests/contracts/test_d3b_execution_contract.py
```

Both reviewers independently verified the same fingerprints before and after their probes. At the
review boundary, `HEAD` and `origin/main` were both the accepted base above and the worktree
contained exactly four modified and four untracked candidate files. Neither reviewer changed a
file, Git ref, issue, pull request or external state.

This post-review persistence record and the status/link update in the implementation record are
documentation-only additions. They do not alter any accepted source, test or D3C-ledger byte. Their
accuracy is separately rebound before commit.

## 2. Review history and controlling vetoes

The accepted sixth freeze is not a relabelled earlier candidate. Two prior exact freezes were
rejected and replaced:

1. The fourth freeze was assurance-vetoed because four zero-call preflight helpers could leak
   `MemoryError` rather than return the promised typed failure code, phase and call count.
2. The fifth freeze closed all four allocation paths, but assurance then proved an exported
   `D3BExecutionSuccess` could accept caller-owned `MappingProxyType` trees whose retained backing
   dictionaries remained mutable after validation.
3. The sixth freeze closes both vetoes. It has a nine-helper typed-allocation matrix and makes every
   accepted success recursively detach into contract-owned immutable storage before becoming
   observable.

No green local test, coverage result or domain acceptance overrode either assurance veto.

## 3. Domain acceptance

The independent domain reviewer returned `DOMAIN ACCEPT` on the exact freeze.

The review independently established:

- retained annual-row, engine-manifest and root proxy backings cannot mutate an accepted success;
- safe shared aliases and the exact owned manifest-subtree identity are preserved;
- Decimal, oversized text and cyclic proxy inputs are refused;
- all 135 focused D3B-1 tests pass;
- 57 changed AEP/loader regressions pass;
- the nine zero-call allocation outcomes remain typed and closed;
- fictional and multi-subject jurisdiction paths do not inherit Sri Lankan defaults;
- wind, solar-DC, storage, common-POI hybrid and explicit legacy wind cases retain their declared
  ProjectCase/technology/topology semantics;
- Decimal-to-binary64 receipts, exact duplicated result origins, mapping-key types, signed zero,
  OPEX periodicity, dates, source authorities and material dispositions remain reconciled;
- the executor still contains exactly one public v14 gateway call and no direct finance or pipeline
  import; and
- the production scenario-authority catalogue remains deliberately empty.

The domain reviewer did not independently rerun the root's 1,094-contract, 386-D2, 7,115-full-test,
Black, isort or mypy gates. Protected exact-head CI therefore remains mandatory.

## 4. Assurance acceptance

The independent assurance reviewer returned `ASSURANCE ACCEPT` on the exact freeze.

The review independently exercised:

- a complete genuine-result tree rebuilt through caller-owned mapping proxies, followed by mutation
  of retained annual-row, manifest and root backings;
- safe mapping and tuple alias preservation;
- mapping cycles and mixed tuple/proxy cycles;
- alias-occurrence, container, scalar, text, integer-bit-length and depth bounds;
- 200 ordinary concurrent constructions while an input backing changed, proving every returned
  object owns a stable post-construction snapshot;
- constructor-copy allocation failure through the public executor, producing exactly one gateway
  call and a typed `result_snapshot_failed` / `result_protocol` failure without retry;
- all nine preflight allocation outcomes with exact code, phase, zero call count and retained
  in-process cause;
- bool/int/float, signed-zero, typed mapping-key, nested/top-level mirror and canonical `<inline>`
  result-origin controls;
- descriptor cleanup, no-follow path traversal, source byte/digest/inode rechecks and the 16 MiB
  authored-source limit;
- refusal of ambient or scenario-declared widening of the built-in AEP source authority;
- exactly one function-local call to `analytics.evaluation_v14.evaluate_with_overrides()` and no
  finance import, pipeline import, retry or KPI recomputation; and
- the unchanged twenty-section D3C ledger against the YAML SSOT in exact order.

The assurance reviewer reran the two ownership controls, all 135 focused tests, selected AEP/path
and error tests, and independent semantic probes. The reviewer did not independently rerun the
root's complete 1,094-contract, 386-D2 or 7,115-full-suite gates.

## 5. Exact-tree root verification

The primary writer's final exact-tree receipts were:

| Gate | Exact result |
|---|---:|
| Focused D3B-1 | 135 passed |
| Complete `tests/contracts` | 1,094 passed |
| Inherited Dolphin 2 import/taxonomy gate | 386 passed |
| Complete governed test suite | 7,115 passed; 18 governed skips; all workers returned |
| Aggregate coverage | 95.02%; 95.00% floor passed |
| Ruff | passed |
| Black | 733 files unchanged |
| isort | passed; four configured skips |
| Complete governed mypy | 263 source files passed |
| Governed scripts mypy | 67 source files passed |
| `git diff --check` | passed |

These local receipts are engineering evidence. The protected branch must reproduce its required
exact-head checks before merge.

## 6. Accepted scope and limitations

The accepted D3B-1 boundary provides one held, preflighted, zero-or-one-call transition from one
exact ProjectCase and EvaluationRequest to the current public v14 evaluation gateway, plus an owned,
bounded, immutable result handoff for D3C. It does not authorize a production scenario because the
module-owned production authority catalogue is empty.

The exported success type enforces structural ownership, immutability and bounds. It does not prove
that a caller-constructed object originated from the evaluator. D3C must still recompute reciprocal
ProjectCase and EvaluationRequest digests, recheck all full-result origins and mirrors, bind the
separate D3C-0 report/run assembly authority, and refuse caller-constructed substitutes.

D3C may consume one accepted D3B result. It may not import or call the evaluator, retry the gateway,
rerun finance, recompute a KPI or infer authority from a successful calculation.

## 7. Authority boundary unchanged

`VERSION` remains `15.4.0`. Issue `#1110` remains `OPEN`; its 23 controls and explicit Board/lender
circulation `HOLD` are outside D3B-1.

These engineering acceptances establish no achieved grade, evidence sufficiency, professional
conclusion, lender acceptance, Board approval, report approval, package release, circulation,
deployment authority or HOLD movement. D3C remains gated by merged D3B-1, a separately governed and
accepted D3C-0 assembly authority, the full implementation acceptance ledger and its own independent
review.

## 8. Seventh-freeze coverage-control rebind

Protected CI for the accepted sixth freeze passed every test shard but correctly refused merge when
its combined coverage was 94.98% (`1,556` missed of `30,981` executable statements). The seventh
freeze at exact commit `b6d50cb895acde505520d324c6e0f8e299bd922d` changed only this implementation
record and the focused test file. It changed no production, contract, loader, D3C-ledger, changelog,
finance or authority-catalogue byte.

The accepted production/test fingerprints were:

```text
ecd83ad49cd76e3720cb6f2866c7a4bbdeb04c5bed3cb39c5db8b1c91c00296d  analytics/aep_provenance.py
ec2ad2ae3a8b494ccdb57c033db5d659038faf980f6d1ca30d144ddbb61d0d66  analytics/contracts_v14.py
15c887b6fe6f430328f49092fd4af27fb81d501411add19b28ab3d545a7d0c2f  analytics/loader/aep_loader.py
b8bb85a7e1b788ff9ca34231f63ec86797b4b4022dfc53218e3c190a63e84f32  analytics/scenario_loader.py
42bf1df615c8f5e475a2c08109119f068946eb60d93691a070ec890df98f2fe8  analytics/feasibility_execution.py
3842b736ca75775353027b5b941680daee51f918bbf98b14aee5edf029337a44  docs/DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md
b0ed2d102ebe66be30b60600e220af5ef3dad5ea3854121f08f26cdc25a75292  tests/contracts/test_d3b_execution_contract.py
```

The independent domain reviewer returned `DOMAIN COVERAGE REBIND ACCEPT`. The reviewer reproduced
138 focused tests, 1,097 complete contract tests and four serial native-grid tests; verified the
new mapping-cycle, resource-bound, exact-numeric, digest, price-basis, selector, run-posture and
technology-key controls; and confirmed that they were non-tautological and did not widen D3B.

The independent assurance reviewer returned `ASSURANCE COVERAGE REBIND ACCEPT`. The reviewer proved
that the added controls execute exactly these 15 previously missed production statements:

```text
181, 182, 246, 247, 257, 648, 659, 993,
1069, 1071, 1073, 1084, 1105, 1111, 1121
```

The reviewer also ran the controls in both orders, proved monkeypatch restoration against the
constructive one-call path, exercised real production container/text limits, reproduced all 138
focused tests and four serial native-grid tests, and verified an empty production-only diff.

Test Suite run `33387739842` then passed all six test shards, grid, quality, security, coverage and
test-summary jobs for exact commit `b6d50cb895acde505520d324c6e0f8e299bd922d`. Separate
exact-head FX run `33387739879`, Regression Smoke run `33387739818` and CodeQL check
`99474212143` also passed. The Test Suite run's combined coverage receipt was:

```text
TOTAL  30,981 statements  1,541 missed  95.03%
```

The prior 94.98% CI failure, the interrupted macOS xdist/OpenDSS attempt and the successful serial
native-grid recovery remain distinct evidence. None was relabelled. This receipt update and the
implementation-record status update are documentation only; their accuracy must be rebound before
merge and they cannot confer any finance, grade, evidence-sufficiency, professional, lender, Board,
package-release, circulation, deployment or HOLD authority.
