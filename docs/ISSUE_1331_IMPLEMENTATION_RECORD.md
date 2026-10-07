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
- Semantic-provenance lease: `L-1331-D1-003`; the same sole writer, opened after the refreshed
  domain review rejected insufficient timezone-policy and derived-lineage declarations.
- Worktree: `/workspace/dutchbay-operational-contract`.
- Branch: `feature/operational-evidence-contract-1331`.
- Current base after the recorded origin/main refresh:
  `3b352034f74254af8b8baeb4d8cf9181ad252cb2`.
- Risk: `R2_LOAD_BEARING`; two independent reviews are required after freeze.
- Durable lease receipts: issue #1331 comments `6031969446`, `6032236120`, and `6043958655`.
- Historical predecessor reviews: `docs/PR1336_D1_DOMAIN_REVIEW_R1.md` and
  `docs/PR1336_D1_ASSURANCE_REVIEW_R1.md`. The first disposition was `REJECT`; both review lanes
  must restart on the successor because remediation changes subject bytes.
- Refreshed historical reviews: `docs/PR1336_D1_DOMAIN_REVIEW_R2.md` and
  `docs/PR1336_D1_ASSURANCE_REVIEW_R2.md`. Assurance accepted with two D2 deferrals; domain made
  those same representational gaps blocking, so the union disposition was `REJECT`.

## Invariants

1. Dataset kind, analysis purpose, evidence class, timezone treatment, observation status,
   interval basis, semantic role and unit vocabularies are closed and runtime validated.
   Named-zone treatment also binds an available IANA timezone and explicit ambiguous/nonexistent
   local-time policies; other treatment classes reject those inapplicable declarations.
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
6. Epistemic status is independent where the domain requires it. Curtailment evidence may be
   observed, operator-declared or a derived estimate. A derived estimate binds both upstream source
   digests and a derivation-method digest. Mixed-status logical datasets are not representable and
   must be split or normalized into one explicitly derived artifact before satisfying D1.
7. Raw evidence is hard-fenced from canonical finance, bankability, lender and Board eligibility.
8. The contract is immutable, serializable and dependency-free. It performs no I/O, conversion,
   imputation, resampling, estimation, reporting or finance mutation.

The fixed-seconds monthly ceiling is 31 days only as a declared maximum cadence. D2 must inspect
actual timestamps and reject gaps, duplicates, misleading cadence declarations or incomplete
calendar coverage; perform and verify the declared timezone/DST policy; and verify the declared
source/derivation lineage. D1 does not infer or execute those operations from metadata.

## Authority and remaining work

This contract does not validate source-file bytes against the declared digest; D2 (#1332) owns
controlled ingestion and QA receipts. It does not calculate AEP or losses (#1333), reconcile an EYA
(#1334), or render climate disclosures (#1335). Issue #1110 remains OPEN and the Board/lender
reliance HOLD remains active.

## Writer verification receipt

| Check | Exact command | Result |
|---|---|---|
| Focused contract tests | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /workspace/dutchbay-epc-model/.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_operational_evidence_contract.py tests/contracts/test_contracts_v14_import_surface.py` | 78 passed in 1.28 s |
| Shared contract regression | same governed pytest invocation against `tests/contracts` | 1,471 passed in 106.71 s |
| Strict types | `/workspace/dutchbay-epc-model/.venv/bin/python -m mypy analytics/operational/contracts.py analytics/operational/__init__.py` | success; no issues in two source files |
| Changed-file hooks | `/workspace/dutchbay-epc-model/.venv/bin/pre-commit run --files <nine allowlisted paths>` | passed |
| Changelog | `/workspace/dutchbay-epc-model/.venv/bin/python scripts/compile_changelog.py --dry-run` | passed; rendered the #1331 fragment under Unreleased / Added |
| Whitespace / conflict check | `git diff --check` | passed |

The predecessor's first focused run returned two fixture `KeyError`s before hostile inputs reached
the contract. Those fixtures were corrected before the initial freeze. The successor remediation
completed without an accepted test failure.
