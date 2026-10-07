# Issue #1331 D1 implementation record

## Scope and source hierarchy

This dolphin adds only the frozen, dependency-free input contract for post-COD operational
evidence. It is governed by issue #1331, the current GWTF rules and RECRUIT-01 modules, and the
repository's CASPER, CESSPIT and CCCDIR definitions. OpenOA v3.2 is a methodological comparator,
not a dependency or authority source.

OpenOA v3.2 `ANALYSIS_REQUIREMENTS` was read from its tagged source. The DutchBay contract maps its
minimum evidence categories and roles for long-term AEP, turbine gross energy, electrical losses,
and SCADA- or tower-based wake losses into closed, unit-bearing DutchBay names. Differences are
deliberate and visible: the contract records evidence metadata only and does not construct an
OpenOA `PlantData` object or run an analysis.

## Writer lease

- Initial lease: `L-1331-D1-001`; coordinator and sole writer `/root`.
- Remediation lease: `L-1331-D1-002`; the same sole writer, opened after the initial domain
  review rejected the frozen candidate.
- Worktree: `/workspace/dutchbay-operational-contract`.
- Branch: `feature/operational-evidence-contract-1331`.
- Base: `93823d55d60496a74936643c5038714b0df876f9`.
- Risk: `R2_LOAD_BEARING`; two independent reviews are required after freeze.
- Durable lease receipts: issue #1331 comments `6031969446` and `6032236120`.
- Historical predecessor reviews: `docs/PR1336_D1_DOMAIN_REVIEW_R1.md` and
  `docs/PR1336_D1_ASSURANCE_REVIEW_R1.md`. The first disposition was `REJECT`; both review lanes
  must restart on the successor because remediation changes subject bytes.

## Invariants

1. Dataset kind, analysis purpose, evidence class, timezone treatment, observation status,
   interval basis, semantic role and unit vocabularies are closed and runtime validated.
2. Every source is bound to a lowercase SHA-256, a non-empty locator and an explicit UTC coverage
   interval. Timeseries evidence declares either a positive fixed-seconds interval or an explicit
   calendar-month basis; asset metadata declares both time treatment and sampling as not applicable.
   A calendar month is never misrepresented as a fixed number of seconds.
3. Purpose-specific dataset, role and cadence minima follow the tagged OpenOA v3.2 requirements:
   long-term AEP is monthly or finer; turbine gross energy is daily or finer; electrical-loss SCADA
   is daily or finer and meter data monthly or finer; wake-loss inputs are hourly or finer.
4. The declared assessment window must lie inside every required dataset's coverage.
5. Every required kind has at least one individually complete logical dataset. Roles from unrelated
   products or digests cannot be unioned to manufacture a complete input.
6. Raw evidence is hard-fenced from canonical finance, bankability, lender and Board eligibility.
7. The contract is immutable, serializable and dependency-free. It performs no I/O, conversion,
   imputation, resampling, estimation, reporting or finance mutation.

The fixed-seconds monthly ceiling is 31 days only as a declared maximum cadence. D2 must inspect
actual timestamps and reject gaps, duplicates, misleading cadence declarations or incomplete
calendar coverage; D1 does not infer a real calendar from metadata.

## Authority and remaining work

This contract does not validate source-file bytes against the declared digest; D2 (#1332) owns
controlled ingestion and QA receipts. It does not calculate AEP or losses (#1333), reconcile an EYA
(#1334), or render climate disclosures (#1335). Issue #1110 remains OPEN and the Board/lender
reliance HOLD remains active.

## Writer verification receipt

| Check | Exact command | Result |
|---|---|---|
| Focused contract tests | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /workspace/dutchbay-epc-model/.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_operational_evidence_contract.py tests/contracts/test_contracts_v14_import_surface.py` | 47 passed after the JSON-serialization positive surface was added |
| Shared contract regression | same governed pytest invocation against `tests/contracts` | 1,439 passed in 102.77 s before the final additive JSON test; focused rerun covers the added test |
| Strict types | `/workspace/dutchbay-epc-model/.venv/bin/python -m mypy analytics/operational/contracts.py analytics/operational/__init__.py` | success; no issues in two source files |
| Changed-file hooks | `/workspace/dutchbay-epc-model/.venv/bin/pre-commit run --files <seven allowlisted paths>` | passed after isort formatted the allowlisted import-surface test |
| Changelog | `/workspace/dutchbay-epc-model/.venv/bin/python scripts/compile_changelog.py --dry-run` | passed; rendered the #1331 fragment under Unreleased / Added |
| Whitespace / conflict check | `git diff --check` | passed |

The first focused run returned two fixture `KeyError`s before hostile inputs reached the contract.
The fixtures were corrected, after which the boundary emitted the intended
`OperationalEvidenceError`; these were test-harness defects, not accepted failures.
