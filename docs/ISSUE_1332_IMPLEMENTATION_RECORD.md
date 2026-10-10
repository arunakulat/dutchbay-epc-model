# Issue #1332 D2 implementation record

## Scope and source hierarchy

This dolphin implements the deterministic normalization and data-quality boundary between the D1
operational-evidence envelope (#1331) and later post-COD analyses. It is governed by issue #1332,
the current GWTF rules and RECRUIT-01 modules, and the repository's CASPER, CESSPIT and CCCDIR
definitions. It neither calculates operational AEP or losses nor mutates canonical finance,
scenario, KPI, report, lender or Board state.

OpenOA v3.2 at commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2` was inspected as a
methodological comparator. Its `openoa.utils.timeseries` and `openoa.utils.qa` helpers admit inferred
frequencies, gap filling and DST ambiguity shortcuts that are useful in exploratory analysis but do
not satisfy this repository's fail-closed evidence boundary. D2 therefore has no OpenOA import or
adapter. It uses Python's standard-library CSV, `Decimal`, `datetime` and PEP 495/`zoneinfo`
semantics, with an installed, versioned `tzdata` distribution required for named-zone conversion.

## Writer lease

- Lease: `L-1332-D2-001`; coordinator and sole writer `/root`.
- Worktree: `/workspace/dutchbay-operational-normalization`.
- Branch: `feature/operational-normalization-1332`.
- Initial base: `c43e7250dfa9f21398421f18650e4a0923910925`, tree
  `6d8c544477c8d5ab9d333b012ec5f489c5b25ab9`.
- Risk: `R2_LOAD_BEARING`; two distinct independent review lanes are required after subject freeze.
- Durable lease receipt: issue #1332 comment `6094158031`.
- Allowlist: the D2 module and tests, the operational and v14 export surfaces, this record, and the
  D2 changelog fragment. D1 contracts, analytical estimators, finance, reports and release state are
  outside the writer lease.

## Invariants

1. The caller supplies immutable UTF-8 CSV bytes and a valid D1 envelope. The source bytes are
   SHA-256 checked before parsing and are retained unchanged in a successful frozen result.
2. Derived-estimate inputs additionally supply the actual ordered upstream artifacts and derivation
   method bytes. Their hashes must exactly match the D1 lineage tuple and method digest. Observed or
   declared evidence cannot smuggle in derivation bytes.
3. Every source header is unique and accounted for exactly once by either a D1 column binding or an
   explicit, reason-bearing exclusion. D1 bindings carry the only admitted role/unit combinations;
   D2 performs no unit conversion.
4. Explicit row exclusions identify one-based data rows, carry reasons, and receive deterministic
   parsed-row hashes. Raw, included and excluded row counts reconcile exactly. Exclusions do not
   waive coverage or cadence QA.
5. UTC source timestamps use strict RFC 3339 `Z` form. Offset-aware timestamps must carry an
   explicit offset. Named-zone wall times require the D1 ambiguous/nonexistent policy and a recorded
   `tzdata` version; PEP 495 folds and round trips distinguish ambiguous from nonexistent times.
   Ambiguity is never silently forced to one side.
6. Canonical rows retain input order. Duplicate keys, non-monotonic observations, declared-versus-
   actual coverage, gaps, fixed-interval drift, calendar-month drift, non-finite numbers and invalid
   values produce a deterministic failed receipt. No defective normalized artifact is returned.
7. Calendar cadence is checked by year/month progression at local midnight on day one. A month is
   never reduced to 31 days. Fixed cadence and aggregation use exact integer-microsecond arithmetic,
   not floating elapsed-time comparisons.
8. Successful normalized CSV is deterministic: D1 role order, LF line endings, canonical UTC,
   canonical finite decimal spelling and a separate SHA-256 digest. The normalization-method digest
   binds all timezone, cadence, mapping, exclusion, lineage and timezone-database choices.
9. Aggregation is a separate opt-in function for already-passing fixed-cadence data. The caller must
   declare interval-start timestamps and either interval energy (summed) or interval-average power
   (arithmetic mean). Targets are exact integer multiples, UTC anchored, and every per-asset bucket
   must be complete and aligned; partial buckets fail.
10. Receipts and results are frozen and runtime self-validating. Authority flags are exact booleans:
    raw evidence only, never canonical-finance, bankable, lender or Board eligible.

## Predictable failure surface

`OperationalNormalizationError` exposes a closed code and, once tabular inspection is possible, the
completed QA receipt. The codes distinguish source digest, lineage, CSV shape, column accounting,
row accounting, timezone setup, quality and aggregation-contract failures. Receipt findings are
stable row/role/group facts and never include source measurement values.

## Comparator differences and limitations

- OpenOA remains an optional future adapter owned outside D2. Adding one later requires call-time
  dependency guards and differential/oracle tests; D2 itself remains dependency-free.
- D2 accepts CSV bytes only and performs no filesystem or network I/O. Excel, Parquet, database and
  telemetry transports require separately governed ingestion adapters.
- A single named-zone fold policy cannot truthfully distinguish two identical repeated wall-time
  strings. Such source data must carry explicit offsets (or be split under separately evidenced
  policies); otherwise duplicate/coverage/cadence checks fail closed.
- Aggregation supports complete fixed-second buckets only. Calendar-month inputs, time-weighted
  irregular power, interpolation and gap repair are deliberately out of scope.

## Authority and remaining work

D2 emits evidence artifacts, not assessment results. D3 (#1333) owns non-canonical operational AEP
and loss analysis, D4 (#1334) owns EYA reconciliation, and D5 (#1335) owns climate disclosure. Issue
#1110 remains OPEN and the Board/lender reliance HOLD remains active. This change grants no merge,
release, finance, professional-review or reliance authority.

## Writer verification receipt

| Check | Exact command | Result |
|---|---|---|
| D1+D2 focused integration | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /workspace/dutchbay-epc-model/.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_operational_evidence_contract.py tests/contracts/test_operational_normalization.py tests/contracts/test_contracts_v14_import_surface.py` | 132 passed in 2.13 s on the hook-normalized subject |
| Shared contract regression | same governed pytest invocation against `tests/contracts` | 1,525 passed in 168.55 s on the hook-normalized final subject |
| Strict types | `/workspace/dutchbay-epc-model/.venv/bin/python -m mypy analytics/operational/normalization.py analytics/operational/__init__.py` | success; no issues in two source files |
| Changed-file hooks | `/workspace/dutchbay-epc-model/.venv/bin/pre-commit run --files <seven allowlisted paths>` | passed after isort normalized one test import block |
| Changelog | `/workspace/dutchbay-epc-model/.venv/bin/python scripts/compile_changelog.py --dry-run` | passed; rendered the #1332 fragment under Unreleased / Added |
| Rules bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" /workspace/dutchbay-epc-model/.venv/bin/python dutchbay_bootstrap_rules.py` | passed; 74/74 active rules |
| Whitespace / conflict check | `git diff --check` | passed |

The first changed-file hook run made only the expected isort normalization to the v14 import-surface
test; the complete hook set then passed. No accepted verification failure is carried into the frozen
candidate.
