# Issue #1332 D2 implementation record

## Scope and authority

D2 is the deterministic normalization and data-quality boundary between the D1 operational-
evidence envelope (#1331) and later post-COD analysis. It produces raw-evidence artifacts and QA
receipts; it does not calculate AEP, losses, availability-adjusted revenue, finance, lender or Board
outputs. Issue #1110 remains open and its reliance HOLD remains active.

OpenOA v3.2 at commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2` was used only as a
methodological comparator. OpenOA's exploratory frequency inference, gap handling and timezone
conveniences are intentionally not imported into this fail-closed boundary.

The sole-writer remediation lease governing this candidate is `L-1332-D2-008`, recorded in issue
#1332 comment `6184523127`; it expires when the candidate is frozen. It succeeds the rejected freeze
under `L-1332-D2-007` and retains the earlier narrow
D1 amendment (`6161711223`): portable timezone-key validation avoids host TZPATH lookup, and
calendar-month evidence rejects an offset-only frame that the evidence envelope cannot reconstruct.
The protected base is
`a1961ca26188645136723659fca4d3f12d67159c`.

## Contract invariants

1. Source CSV, ordered lineage artifacts and derivation-method bytes are immutable inputs. Their
   SHA-256 identities must reconcile with the D1 envelope before parsing.
2. Every source column is mapped once or explicitly excluded with a reason. Every excluded row is
   identified, reasoned and hashed. D2 performs no inferred mapping, unit conversion, imputation,
   exclusion, sorting or resampling.
3. Numeric parsing is independent of the process `Decimal` context. Accepted finite decimal
   literals are rendered losslessly with bounded representation length.
4. Fixed and calendar cadence QA is population-based and invariant to row order. Duplicate
   occurrences, expected-grid gaps, off-grid occurrences and source-order violations are reported
   separately. Calendar-month declared and observed populations use the same source-wall frame:
   UTC for `source_utc`, or the supplied TZif rules for `named_zone_to_utc`. QA continues after
   unrelated measurement-value defects.
5. Grouped time series require an `OperationalGroupUniverse` derived from a successfully normalized
   D1 asset roster. Missing, unexpected, incomplete and misaligned asset populations fail QA.
   Empty and all-excluded included populations cannot pass.
6. Named-zone conversion requires immutable caller-supplied TZif bytes. D2 validates the complete
   RFC 8536/9636 container in bounded linear time before using `ZoneInfo.from_file`, including both
   v2+ data blocks, transition/type/indicator references, the required UT-implies-standard relation,
   and its newline-terminated POSIX footer. Leap records require a non-negative first occurrence,
   actual leaps at UTC month ends, and unit correction steps; version 4 also admits start-truncated
   initial corrections and a final equal-correction expiration record. At consumption D2
   reconstructs the complete rules value to
   defend bypassed object construction, including closed zone/locator text and immutable bytes;
   receipts independently enforce closed provenance text. Parser and Python-datetime compatibility
   failures are contained by the closed timezone-normalization code. The payload SHA-256, declared
   zone and locator are bound into the method and receipt. Host
   TZPATH is not consulted. Four-digit RFC 3339 years are rendered independently of host `strftime`
   behavior, and timezone conversions outside Python's representable datetime range fail under the
   same closed code rather than being misclassified as non-finite measurements. The
   zone-to-payload relationship is explicitly
   `caller_attested_zone_payload`: D2 proves which bytes were used, not that an arbitrary payload is
   an authoritative publication for the declared IANA label.
7. RFC 3339's `-00:00` unknown-offset sentinel is rejected. Folds and nonexistent local times use
   only the D1-declared policy and the supplied TZif bytes; resolutions are counted.
8. Successful normalized rows, canonical LF CSV bytes, D1 evidence, source/lineage bytes, group
   universe, timezone rules, QA receipt and normalization-method digest reconcile at result
   construction. Construction deterministically replays normalization from those retained inputs,
   so possession of the private factory token plus a self-consistent replacement digest cannot
   substitute a measurement that contradicts the source artifact. Results are factory-only frozen
   artifacts.
9. Aggregation is a separate opt-in contract for complete fixed-cadence data. Interval energy uses
   exact rational summation. Interval-average power uses an explicit 12-decimal, signed
   round-half-even policy. The selected policy and bound are part of the method digest.
10. Aggregate results retain and reconcile their normalized source and exact aggregation spec, then
    recompute rows and method identity during construction. Partial or misaligned per-asset buckets
    fail closed.
11. Fixed/target intervals, numeric representations and bucket populations are bounded. Predictable
    parsing, range and arithmetic failures cross the public boundary only as closed CASPER
    `OperationalNormalizationError` codes.
12. Every artifact remains `raw_evidence_only=True` and exactly false for canonical-finance,
    bankable, lender and Board eligibility.

## Predictable failure surface

The closed codes distinguish source and lineage digest mismatch, invalid CSV, column and row
accounting, timezone normalization, group-universe failure, QA failure and aggregation-contract
failure. Once tabular inspection is possible, QA failures carry their deterministic receipt.
Findings identify rows, roles and groups but never echo measurement values.

## Deliberate limitations

- CSV bytes are the only transport. Filesystem, network, Excel, Parquet, database and telemetry
  adapters remain separately governed work.
- TZif zone semantics are caller-attested. A future authoritative zone/digest registry would require
  its own governed source and lifecycle.
- A single fold policy cannot distinguish repeated identical wall-time strings. Such evidence must
  carry offsets or be split under separately evidenced policies.
- Aggregation admits complete fixed-second buckets only. Calendar aggregation, interpolation, gap
  repair and irregular time weighting are outside D2. Calendar-month normalization supports
  source-UTC and supplied named-zone frames; offset-aware-only monthly evidence is rejected because
  D1 carries no stable named calendar frame.
- OpenOA remains a future optional adapter, not a dependency or authority.

## Verification receipt

This table is updated only with results from the final frozen candidate. Earlier WIP claims are
superseded.

| Check | Exact command | Final result |
|---|---|---|
| D1+D2 focused integration | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /workspace/dutchbay-epc-model/.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_operational_evidence_contract.py tests/contracts/test_operational_normalization.py tests/contracts/test_contracts_v14_import_surface.py` | 182 passed in 2.69 s; repeated after final receipt commit before freeze |
| Shared contract regression | same governed pytest invocation against `tests/contracts` | 1,575 passed in 182.21 s on final source/test content; the only subsequent mutation was this verification-receipt text |
| Strict source types | `/workspace/dutchbay-epc-model/.venv/bin/python -m mypy --no-incremental analytics/operational/normalization.py analytics/operational/contracts.py analytics/operational/__init__.py analytics/contracts_v14.py` | success; no issues in four source files; repeated after final receipt commit before freeze |
| Scoped Ruff and formatting | governed Ruff check and format-check against the seven changed Python paths | passed; seven files formatted; repeated after final receipt commit before freeze |
| Changed-file hooks | `/workspace/dutchbay-epc-model/.venv/bin/pre-commit run --files <nine allowlisted paths>` | passed; repeated after final receipt commit before freeze |
| Changelog | `/workspace/dutchbay-epc-model/.venv/bin/python scripts/compile_changelog.py --dry-run` | passed; D2 fragment rendered under Unreleased / Added |
| Rules bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /workspace/dutchbay-epc-model/.venv/bin/python dutchbay_bootstrap_rules.py` | passed; 75/75 active rules; repeated after final receipt commit before freeze |
| Whitespace/conflict check | `git diff --check` | passed; repeated after final receipt commit before freeze |
| Ordinary full suite + coverage | `make test PY=/workspace/dutchbay-epc-model/.venv/bin/python` | predecessor freeze `3b47a8a`: interrupted after 2,369 passed / 3 skipped / 2 failed in 929.05 s because both failures are shared-venv distribution-metadata assumptions; the same two isolated tests fail unchanged on protected `main`. Not represented as an exact-final-candidate green receipt; hosted CI is required |

The full-suite exceptions are `tests/app/test_ops_extras.py::test_an_unparseable_pyproject_degrades_to_metadata`
and `test_a_foreign_pyproject_does_not_answer_for_this_distribution`. In this managed shared venv,
neither checkout has installed DutchBay distribution metadata, so both return `spec_source="none"`
instead of `"metadata"`. The failures were reproduced on untouched protected `main` with the same
interpreter and are not changed or waived by D2. Hosted required CI remains authoritative and must
be green on the exact PR head before merge.

After these checks pass, the exact commit, tree, base and canonical Git-blob subject manifest are
frozen for two independent RECRUIT-01 reviews. A review or merge does not lift #1110's HOLD or grant
release, professional-review or reliance authority.
