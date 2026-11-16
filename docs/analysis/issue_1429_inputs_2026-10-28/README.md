# #1429 input inventory — local review candidate, 28 October 2026

This is an inventory and proposed follow-up register, not a migration or a claim that
programme #1429 is complete. Every production and scenario byte remains unchanged.
Claude retains queue, ready/review routing and merge authority. New PRs are held until
queue admission. No independent domain/assurance acceptance, full-suite acceptance,
release, lender/Board reliance, transaction or real-feeder authority is claimed.

## Source boundary and evidence

Inspected base: `c283565abd8c7a989daac4c7cfd70c7fb7c18d4d` (tree
`bb1d2abc3fe7f9067bdb47881b3f625e2c4171a4`). The denominator is **195 tracked Python
files** under `finance/`, `analytics/` and `constants.py`, including validators and
synthetic/example/sandbox modules inside those directories. Root scripts, `api/`, `app/`,
`wind_resource/` and YAML bodies are outside the Python census. Two committed scenarios
and current schema declarations were read separately to reconcile field names and guards.
`source_manifest.json` pins every inspected file by Git blob and SHA-256.

`migration_register.csv` contains **241 rows at 239 distinct source locations**, grouped
into 49 proposed dispositions. Each row records file, exact line/column, current literal
or expression, source statement locator, source hash, scenario-field/target proposal,
impact and owner/dependency. These counts include explicit exclusions and overlapping
references; they are **not counts of confirmed defects or approved migrations**. Target
fields marked proposed/pending/verify are design candidates, not installed schema claims.
Some groups give multiple reader aliases; the per-site field hint and source statement
identify which alias the row concerns.

The complete source-evidence ledgers are retained locally in
`/Users/aruna/Downloads/DutchBay_Codex_Next_Five_2026-10-28/`:

| Evidence | SHA-256 |
|---|---|
| `1429_candidate_catalog.csv` | `ff4d2a02cf3398a6e2cc14a36fb09499b7a96957bc7dcb33d051ed41fa0159f2` |
| `1429_numeric_literals.csv` | `c7ade163868ab01803827aba617fc6dbe0323d81986ea037bf1ea9c04ce100fb` |
| `1429_inventory_scan.py` | `5e55fb2c45dbfa5581d862e107712af211bbefd9f0020a478d948b91568e04bb` |

The candidate catalog contains 4,750 syntax records: 1,095 named assignments/constants,
1,287 `or` expressions, 806 argument defaults, 711 conditional else arms, 569 mapping
get/setdefault defaults, 50 attribute defaults, 150 keyword arguments whose name contains
`default`, and 82 recognized coercion defaults. The separate numeric ledger preserves
**all 4,886 numeric literals**. AST and independent lexical token counts agree in every
one of the 195 files. Neither catalog asserts that a syntactic default is silent,
reachable, project-specific or wrong. `or` also implements ordinary Boolean logic;
`None`, empty collections, zero/one identities, result sentinels and validation boundaries
must not be turned into authored business assumptions by a mechanical rewrite.

The scanner is a local analysis helper, not a product CLI. It imports no model code,
reuses pinned source, and reproduces the catalogs, source manifest and register byte for
byte. The human selection rules and schema observations are in
`1429_catalog_review.json`; it is part of the local evidence pack. These local files are
not remotely fetchable from GitHub. Future review/delivery must provide the reviewers
access to the same bytes or publish an authorized equivalent before acceptance.

## Reconciled named cases

- **Debt gearing:** five engine/coercion `0.70` sites plus the standalone capacity API
  default are recorded (D01). The original issue's line numbers are dated. Additional
  tenor, construction, rates, mix, fees, DSRA and balloon assumptions are retained in
  D02–D13 rather than treating its short list as exhaustive. The three registered debt
  specs (tenor, rate, gearing) have `required=False`: they validate when supplied, which
  is different from refusing absence.
- **DSCR/downside:** D06 records the `1.30` target fallbacks; D07 records the `0.80`
  downside fallbacks and the source selector. Moving a value unchanged into YAML does
  not authorize reconciling the target to another measured DSCR. That numerical decision
  remains separate under #962. P90/P50-derived downside and a fixed 0.80 proxy are
  different bases and must keep their provenance.
- **Project discount:** `DEFAULT_DISCOUNT_RATE = 0.10` remains in
  `analytics/core/metrics.py`, not `constants.py`. The enhanced pipeline can use an
  authored WACC when `drives_discount_rate` is true; a missing/non-driving WACC retains
  the fallback, with a warning for a present non-driving block. The `or` fallback also
  treats a computed zero as absent; N05 records that static observation without making
  a behavioral correction. `returns.project_discount_rate` exists in the inspected
  scenarios, but precedence/wiring is a decision, not something this inventory installs.
- **Equity/batch discount:** N02 distinguishes the direct batch-constructor fallback
  from the blessed batch CLI, whose configured discount is already required. N03 and
  E01/E05 distinguish the legacy low-level equity rate and contract/reader defaults.
  The distribution parser reads `project.project_life_years`, whereas the inspected
  scenarios use `project.life_years`; it can retain its 25-year parsed default, but that
  field is not used to size the annual-row distribution schedule. This is a source
  observation, not a demonstrated canonical horizon or KPI defect.
- **BESS:** #1401/#1463 remains the owned rating/energy/duration slice, with #1472 stacked
  for the ledger. B01–B06 record other economics/contract defaults. The 365-cycle revenue/
  LCOS and 400-cycle standalone-economics bases are distinct existing assumptions; do
  not unify them silently. Physical rating migration and changing a tariff/degradation/
  availability assumption are different decisions.
- **Refinance:** `resolve_refinance_terms` already requires the YAML tenor and premium,
  and strict preflight delegates to it. Two read-only negative controls removed one
  field at a time from an in-memory copy of the lender config; each was refused with
  its exact `constraints.refinancing.*` path. No source/config file or model KPI was
  changed. #1492 is merged at this base; #1396 itself is still OPEN and its old issue
  body is not a current canonical measurement. No issue closure is inferred.
- **Reference/downside cases:** #1403 is OPEN, reserved/deferred and requires owner case
  definitions. #1452 remains a draft dependency. No delayed-grid, connection-asset or
  tariff-reference scenario is created here. The inventory grants no line-cost,
  reimbursement, tariff-entitlement or canonical-input authority.
- **`constants.py`:** its nine numeric declarations are unit/time/calendar conventions,
  not project ratings, tariffs or financing assumptions (Z01). Numerical search bounds,
  precision tolerances, safety/resource limits, enums and immutable evidence identities
  have separate roles. Z02 records IRR solver defaults without migrating or retuning
  them. Fixed synthetic grid evidence is separately labelled G04; its compile-only and
  HOLD boundaries remain intact.

## Register groups

The CSV is the exact per-site record. This table is an index, not a second value store.
All OPEN/REVIEW dispositions remain proposals under coordinator ownership.

| ID | Group | Rows | Disposition |
|---|---|---:|---|
| D01 | Gearing ratio default | 6 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D02 | Tenor default | 6 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D03 | Construction period default | 7 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D04 | Construction phasing and draw placeholders | 12 | `WARNED_PLACEHOLDER_NOT_SILENT` |
| D05 | Debt rates and mix | 7 | `OPEN_DEFAULT_POLICY_REVIEW` |
| D06 | DSCR target | 3 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D07 | Downside factors and source selector | 4 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D08 | DSRA months | 1 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D09 | Balloon limit | 1 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| D10 | Balloon and amortization mode defaults | 5 | `OPEN_MODE_POLICY_REVIEW` |
| D11 | Optional credit-support fees | 2 | `OPTIONAL_ZERO_REQUIRES_OWNER_DISPOSITION` |
| D12 | Standalone capacity calculation assumptions | 4 | `OPEN_LOW_LEVEL_API_POLICY_REVIEW` |
| D13 | Dual-DSCR capacity-only discount default | 2 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| N01 | Project discount fallback | 1 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| N02 | Batch constructor discount | 1 | `LOW_LEVEL_DEFAULT_CLI_ALREADY_CONFIG_FIRST` |
| N03 | Legacy equity NPV rate | 1 | `OPEN_LOW_LEVEL_API_POLICY_REVIEW` |
| N04 | Prudential WACC spread | 3 | `OPEN_DEFAULT_POLICY_REVIEW` |
| E01 | Equity horizon/lockup/reserve/discount defaults | 4 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| E02 | Optional equity terminal and investment sentinels | 2 | `OPTIONAL_ZERO_REQUIRES_OWNER_DISPOSITION` |
| B01 | BESS cycles | 3 | `OPEN_DISTINCT_BASIS_DO_NOT_UNIFY_365_AND_400` |
| B02 | BESS efficiency/SoH/DoD | 4 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| B03 | LCOS SoH floor | 1 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| B04 | Standalone BESS optional charging efficiency | 1 | `OPEN_REQUIRED_INPUT_MIGRATION` |
| B05 | Optional BESS zero costs | 4 | `OPTIONAL_ZERO_REQUIRES_OWNER_DISPOSITION` |
| B06 | BESS availability rule constants | 2 | `OPEN_POLICY_PARAMETER_REVIEW` |
| R01 | Low-level AEP sensitivity physical inputs and analysis ranges | 5 | `LOW_LEVEL_DEFAULT_HIGH_LEVEL_OVERRIDE` |
| R02 | OEM reader hub fallback | 1 | `OPEN_SOURCE_METADATA_POLICY_REVIEW` |
| R03 | OEM generic loss defaults | 3 | `OPEN_LOW_LEVEL_API_POLICY_REVIEW` |
| R04 | Monte Carlo AEP scientific defaults | 6 | `OPEN_ANALYSIS_INPUT_POLICY_REVIEW` |
| R05 | Wind pipeline loss uncertainty defaults | 2 | `OPEN_ANALYSIS_INPUT_POLICY_REVIEW` |
| R06 | PySAM sandbox horizon/degradation | 4 | `NONCANONICAL_SANDBOX_DEFAULT_REVIEW` |
| X01 | FX shock fallback | 1 | `DISCLOSED_FALLBACK_NOT_SILENT` |
| X02 | FX low-level shock default | 1 | `OPEN_LOW_LEVEL_API_POLICY_REVIEW` |
| X03 | Currency/tranche fallback | 4 | `OPEN_CURRENCY_MAPPING_REVIEW` |
| X04 | FX drift tolerance | 1 | `ANALYSIS_OR_PROVENANCE_POLICY_REVIEW` |
| M01 | MC distribution fallback | 7 | `OPEN_SAMPLER_INPUT_POLICY_REVIEW` |
| M02 | Toy finance figures | 29 | `NONCANONICAL_TOY_BOUNDARY` |
| P01 | Default DSCR covenant risk/report | 3 | `OPEN_REPORT_POLICY_REVIEW` |
| P02 | Risk confidence fallback | 3 | `OPEN_ANALYSIS_INPUT_POLICY_REVIEW` |
| G01 | Frequency-response assumptions | 5 | `ADVISORY_GRID_PARAMETER_REVIEW` |
| G02 | Reactive/harmonic impedance fallbacks | 10 | `ADVISORY_GRID_PARAMETER_REVIEW` |
| G03 | Ride-through fixture defaults | 9 | `ADVISORY_GRID_STUDY_ARGUMENT_REVIEW` |
| G04 | Synthetic fixed evidence ratings | 8 | `EXCLUDED_FROZEN_SYNTHETIC_ORACLE` |
| Z01 | Universal conversion/calendar conventions | 9 | `EXCLUDED_UNITS_AND_CONVENTIONS` |
| Z02 | IRR numerical search/tolerance | 20 | `EXCLUDED_FROM_LITERAL_PRESERVING_INPUT_MIGRATION` |
| N05 | Falsy-zero project-discount fallback | 1 | `OPEN_ZERO_VERSUS_ABSENCE_POLICY_REVIEW` |
| E03 | Equity sweep and holdback defaults | 2 | `OPTIONAL_PERCENT_REQUIRES_OWNER_DISPOSITION` |
| E04 | Equity default enable/opt-out flags | 2 | `OPEN_MODE_POLICY_REVIEW` |
| E05 | Equity contract default declarations | 18 | `OPEN_LOW_LEVEL_CONTRACT_POLICY_REVIEW` |

## Proposed bounded follow-ups

Start with one module and one assumption family per PR after current queue admission:
(1) debt gearing requiredness and exact existing aliases; (2) debt DSCR/downside controls,
with numerical-target decisions separated; (3) tenor/construction and explicitly authored
phasing; (4) project discount source/precedence; (5) equity parser/contract inputs;
(6) BESS economics after its owned rating/ledger parents; (7) remaining FX, resource,
analysis/report and advisory-grid groups. Optional zero costs, opt-out flags and mode
choices need an owner disposition about explicit absence versus required zero. These
are proposals, not allocations or permission to edit another owner's work.

Every migration must first identify the public gateway and all direct API callers,
record its exact base/overlap, and obtain a fresh bounded lease. Move the existing value
unchanged; preserve units, alias precedence and the distinction between real zero and
absence. Pair strict missing-field refusal (with config path) with canonical byte-identical
KPI receipts and an independent responsiveness/oracle control. Any intended value,
method or precedence change is a separate consequential decision with its own impact
and version/provenance work. No such receipt is claimed by this inventory.

## Validation and remaining uncertainty

The four generated artifacts were reproduced with identical hashes. Every one of the
241 curated expressions was matched at its recorded AST source location. The manifest
covers exactly the tracked base-source set; no production, YAML, pin, version, dependency
or runtime installation changed. Governed Python 3.12.13 and 315-pin active-checkout
health passed. These are source-evidence and schema/refusal checks, not a full finance
suite, migration validation or independent semantic review.

The census is complete for the declared tracked files and syntax mechanisms. **Semantic
completeness remains unverified:** 49 curated groups are not a proof that all project
figures or fallback paths have been understood. Dynamic aliases, helper names outside
the enumerated set, computed defaults, direct API reachability and fields read outside
this denominator require follow-up call-path review. The uncurated catalog remains
available so those cases are not lost or silently classified as harmless. Strict guarding
for two refinance fields does not prove requiredness for every other input. Do not check
#1429's overall inventory/migration programme complete from this candidate.

This is R3 consequential inventory evidence requiring independent finance/analytics
and assurance review after freeze and queue admission. The source-evidence census and
curated proposals have not received those dispositions. #1110/F-5, release, transaction,
Board/lender and real-feeder HOLDs remain unchanged.
