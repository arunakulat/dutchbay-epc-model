# Issue #1333 D3 implementation record

## Scope, authority, and source ingress

D3 adds one non-canonical operational-energy accounting boundary over immutable D1/D2
artifacts. It does not change D1/D2 normalization, canonical AEP, scenarios, finance, reports,
release state, or issue #1110. Every result is exactly false for canonical-finance,
bankability, lender, and Board eligibility. The Board/lender reliance HOLD remains active.

The initial writer lease `L-1333-D3-001` (comment `6201589355`) was revoked after interruption
(comment `6212320900`), and its exact seven changed files were preserved without semantic edits in
checkpoint `f292a07f335f1953d71349495726d6c85931e695` under persistence-only lease
`L-1333-D3-P001` (comment `6212327630`). The controlling recovery lease is `L-1333-D3-002`, comment
`6212341149`; it required the successor writer to treat the preserved code and 209 passing tests as
claims rather than acceptance. The capability profile is comment `6201394718`. The recovery writer
independently revalidated the checkpoint head/tree/base, merge base, clean state, eight allowlisted
hashes, worktree import path, and sole-writer state before mutation. It then read the complete
preserved D3 source, tests, and record; contract/harness ingress (`6201512739`); renewable-energy
ingress (`6201581582`); their named repository sources; D1/D2 contracts and predecessor records; and
the OpenOA v3.2 sources at commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2`:

| Comparator source | SHA-256 | Use |
|---|---|---|
| `openoa/analysis/aep.py` | `19afc5ddbaec4cd5a1bfc367aaaa2780446ddf9d66cc3752b9020f62d41e9441` | meter-plus-availability-plus-curtailment gross convention; annual/LTA distinction |
| `openoa/analysis/electrical_losses.py` | `1af2ddd127b093842fd6d14ae4234da5c3207ba8f3f52ecdc4bff0cda14d41ec` | matched turbine/meter energy and `1-M/T` electrical-loss fraction |
| `openoa/analysis/eya_gap_analysis.py` | `e0c161a34f6c1534d5613ff3341d6c4c72cc13a41950e8eef2dd8313d098d307` | later EYA-gap boundary only; no D4 calculation here |
| `openoa/analysis/turbine_long_term_gross_energy.py` | `604d8eb33b5b45e272ccde5770061b4d56cd6fbc835387f0dfc039671ee1bba3` | turbine-gross comparator and why D2 evidence alone cannot establish it |
| `openoa/analysis/wake_losses.py` | `c9d3e99a3b94cf2cbd7b5c9c8c20c2b5564a18481c57c8606eabe691bba5b927` | combined wake/performance potential boundary comparator |
| `openoa/plant.py` | `0686b8ad8e7ca732bdb00038ea084d3e98997038d0f809aa50e064ca900a790d` | source-category and complete turbine-population semantics |

OpenOA remains research software and a methodological comparator, not a runtime dependency,
source-acceptance authority, professional opinion, or bankability claim. D3 imports no OpenOA
code and adopts none of its stochastic paths. The recovery ingress downloaded all six comparator
files directly from that exact commit and independently reproduced every SHA-256 in the table.

Recovery lease `L-1333-D3-002` produced the first frozen candidate at commit
`a852214e6954488b67af1ec394a2932ac739590c`. Independent exact-object review rejected that
candidate with domain finding `D3-DOM-001` (comment `6213078877`, canonical receipt SHA-256
`7b2c056992bf340c5b9f7548ec6bd541451fa4b9c2030712d0bf2976f46dca03`) and assurance finding
`D3-ASSURANCE-001` (comment `6213083712`, canonical receipt SHA-256
`d9514f805d3d0c07645742468874c32b2529d380b4cbbb96b19307d717507286`). The findings respectively
showed that separate purpose windows could under-authorize the population emitted by D3 and that a
malformed retained D2 nested contract could leak a raw `AttributeError` before replay. Corrective
lease `L-1333-D3-003` was interrupted and revoked at comment `6219984076`; its exact partial source
bytes were preserved without semantic edits at checkpoint `f899c94c841d505ecdbdfacf5f175c9d4f06142a`
under persistence-only lease `L-1333-D3-P002` (comment `6219989366`). Lease `L-1333-D3-004`
(comment `6219998423`) owns the bounded completion of those two findings and no other scope.

The corrected exact object at commit `9159ae2250689bc507e391e3006547f90075becd` then received
fresh domain ACCEPT comment `6220566413` and assurance ACCEPT comment `6220573637`. Hosted CI
passed all six ordinary shards and the remaining required checks, but the combined coverage gate
reported 94.94% (35,965 statements, 1,819 missing) against the 95% floor; the D3 module itself was
88.38% (628 statements, 73 missing). Those accepts therefore lapsed when bounded corrective lease
`L-1333-D3-005-COVERAGE` (comment `6220896152`) authorized a test-and-record-only correction. Its
allowlist is exactly `tests/contracts/test_operational_aep.py` and this record; production source,
workflow, and configuration bytes remain frozen.

## Evidence and equation contract

The factory requires explicit logical-ID selectors and exactly one selected D2 result per logical
ID. The meter and turbine products must occur together in one D1 `electrical_losses` envelope;
the meter and availability/curtailment products must occur together in one D1 `long_term_aep`
envelope. All envelopes bind the same project. Every selected D2 series must independently resolve
to the same start and end-exclusive effective interval. Fixed-second interval-average power is
integrated as the exact rational `power_kw * interval_seconds / 3600`; interval energy is summed
exactly. Source-UTC and supplied-TZif calendar-month energy can share a boundary with complete
fixed-second turbine evidence.

Role selection is closed rather than inferred: meter energy is always the D1-required
`energy_kwh`, turbine energy is always integrated from the D1-required interval-average `power_kw`,
and each selected availability or curtailment product must itself carry both D1 loss roles. An
optional extra SCADA energy column cannot override turbine power, and partial loss products cannot
borrow D1 completeness from an unselected product. Before use, every selected D2 result is replayed
through `normalize_operational_csv` from its retained source, lineage, derivation, TZif, group
universe, and exclusion inputs; any row, normalized-byte, receipt, method, or provenance
substitution closes as `PROVENANCE_MISMATCH`.

The replay boundary reconstructs and type-validates the retained D1 evidence, column bindings,
quality receipt, and row exclusions before reading their identity fields or invoking D2 replay.
Predictable malformed nested-object and validation failures are translated into the closed D3
`PROVENANCE_MISMATCH` state; callers do not receive incidental `AttributeError`, `TypeError`, or
`ValueError` exceptions from hostile retained objects.

An immutable boundary attestation separately states that the meter is net export, SCADA covers the
complete turbine-terminal asset universe, losses are non-overlapping positive reductions, rows are
interval-start/end-exclusive, and import, storage, solar, and shared-POC flows are excluded. Its
source and method bytes are SHA-256 verified and its semantic claim digest enters the D3 source
manifest. These are caller attestations: D3 proves which bytes and assertions were used, not their
external authenticity.

For one matched population:

- `M` = non-negative net-export meter energy.
- `T` = non-negative complete turbine-terminal energy.
- `A` and `C` = non-negative, non-overlapping availability and curtailment loss energy.
- `E = T - M`; `M > T` fails even when inside the declared tolerance. No negative loss is clipped.
- meter loss-restored gross is `M + A + C`, matching the OpenOA operational-AEP convention.
- turbine-known gross is `T + A + C = M + E + A + C`.
- optional `R` is separately provenance-bound upstream resource/potential gross.
- optional `W` is separately provenance-bound combined wake/performance loss.
- `U = R - (M + E + A + C + W)` only when both `R` and `W` exist. A negative residual fails;
  no mismatch is silently absorbed.

All quantities and ratios are reduced integer fractions. No float or process `Decimal` context
participates. The explicit absolute kWh tolerance and exact residuals are method-bound. Available
zero carries a value and evidence IDs; unavailable carries neither, so missing evidence can never
be serialized as zero.

Source bindings use a closed role vocabulary: the four mandatory D2 bindings require normalized
artifact digests and no scalar claim, while optional `R`/`W` bindings require provenance-bound
scalar-claim digests and no normalized artifact. Receipt construction independently validates
temporal basis, complete-year bounds, exact quantity types, unique mandatory bindings, and every
residual against tolerance. D1 assessment claim hashing sorts datasets by logical ID, so semantically
equivalent tuple ordering cannot change the source manifest or method identity.

D1 assessment bounds are inclusive interval-start labels, whereas the D3 population has one
end-exclusive interval. All selected D2 products must first prove the same effective start and
end-exclusive bound. The earliest retained selected-product final label is then the coarsest
interval family that reaches that common end and therefore the maximal common inclusive D1
authorization end. Both the `electrical_losses` and `long_term_aep` envelopes must exactly equal
that single global window. Neither purpose can lend a narrow, shifted, or otherwise different
authorization to the broader population emitted by D3.

## Temporal, uncertainty, and authority boundaries

Only `observed_period_total` and a strictly complete UTC `actual_calendar_year` are accepted
temporal labels. Long-term-average energy is always unavailable in this checkpoint. Annual and
long-term-average uncertainty are separate structural fields; both are
`unavailable_not_estimated`, have no basis, and have separate empty exceedance tuples. Reanalysis
presence never creates resource gross, LTA, P50, P90, or uncertainty. A future LTA or uncertainty
result requires a separately governed method, covariance/input contract, deterministic oracle,
and new review.

The result retains all inputs and is factory-only. Construction reconstructs the D3 specification,
boundary attestation, and supplemental evidence at the consumption boundary, then replays D2 and
all D3 components, ratios, source-manifest identity, method identity, reconciliation residuals,
uncertainty state, and hard authority flags. Possession of the module-private factory token cannot
authorize a substituted result. Model dumps omit retained source and method bytes.

## Independent fixture and hostile controls

The independently hand-derived four-interval fixture has two turbines at 500 kW for four 15-minute
intervals, meter energy 237.5 kWh per interval, availability 25 kWh per interval, curtailment
12.5 kWh per interval, separately evidenced `R=1250 kWh`, and `W=80 kWh`. The exact oracle is
`T=1000`, `M=950`, `A=100`, `C=50`, `E=50`, meter loss-restored gross `1100`, turbine-known gross
`1150`, and `U=20`. Exact ratios include `E/T=1/20`, `M/R=19/25`, and `U/R=2/125`.

The focused suite also covers evidenced zero versus unavailable; source-UTC and retained-TZif
calendar-month/fixed-day matched bounds; same-process and fresh-process Decimal-context
independence; assessment, dataset, D2-result, and supplemental input-order invariance; bounded
property scaling; split/merge intervals; equal meter/turbine increments; named-loss increments;
selector absence/duplication; partial-product completeness attacks; project/window/ID mismatch;
under-authorizing or disagreeing D1 purpose windows for fixed-day, UTC calendar-month, and retained
named-zone calendar populations; malformed nested D2 evidence, receipt, column, and row-exclusion
objects before identity selection or replay;
attestation-versus-D2-bound conflict; negative electrical, named, and residual loss; huge,
non-finite, and wrong-type tolerance values; D2 row replay and D3 result substitution; provenance
size/digest/binding-role attacks; serialization; temporal/LTA/uncertainty laundering; hard authority
flags; zero denominators; and resource-only, wake-only, and no-supplement anti-inference.

## Predecessor finding matrix

| Finding family | D3 disposition |
|---|---|
| D1 product isolation, cadence/calendar declaration, timezone policy, epistemic status, derived lineage, portable zone keys, digest-role separation, runtime errors, and authority fences | `CLOSED` by consuming only exact D1 evidence objects retained in verified D2 results and matched D1 envelopes; D3 does not loosen D1 |
| D2 context-independent numeric parsing and aggregation | `CLOSED` by retaining D2 objects and using a separate exact `Fraction` implementation; no float/global Decimal context |
| D2 population/group completeness, row/byte replay, timezone/TZif binding, interval/resource bounds, and predictable failures | `CLOSED` for selected inputs by independently replaying every retained D2 result at D3 consumption and requiring the complete SCADA group universe |
| D2 RFC 9636 leap/indicator/start-truncation chain, including first correction zero | `NOT_APPLICABLE_WITH_REASON`: D3 consumes normalized UTC rows and does not parse or alter TZif bytes; retained named-zone calendar rules are replayed by D2 and used only to establish the next end-exclusive month boundary |
| Missing resource gross, wake/performance, unknown residual, LTA, and uncertainty evidence | `CLOSED` by explicit unavailable states; `R/W/U` become available only under the supplemental provenance rules above |
| Canonical finance, lender, Board, release, professional, publication, issue-closure, and HOLD authority | `CLOSED` by hard-false flags and explicit non-authority; #1110 remains OPEN/HOLD |

The first frozen candidate's two D3-specific findings are separately replayed here:

| Finding | Corrective disposition |
|---|---|
| `D3-DOM-001` | `CLOSED` in the corrective candidate by deriving one maximal common inclusive D1 interval-start window from the common D2 end-exclusive population and requiring both purpose envelopes to match it; hostile fixed-day and calendar tests reject narrow, shifted, and disagreeing authorization |
| `D3-ASSURANCE-001` | `CLOSED` in the corrective candidate by reconstructing and validating exact nested D1/D2 contracts before any identity dereference or replay and translating predictable malformed-object failures to `PROVENANCE_MISMATCH`; hostile evidence, receipt, column, row-exclusion, and wrong-runtime-object tests exercise the boundary |

## Deliberate limitations

- Boundary evidence is caller-attested; D3 does not authenticate an operator, meter, asset roster,
  resource model, or wake method.
- D3 supports only the D1/D2 CSV normalization contract. It performs no file, network, database,
  OpenOA, interpolation, gap repair, imputation, or unit conversion.
- Combined wake/performance is one explicit scalar category. Separating wake, turbine performance,
  blade degradation, or resource-model bias needs new evidence and contracts.
- Availability/curtailment exclusivity is attested, not inferred from status/event overlap.
- Replaying selected D2 results is intentionally fail-closed and adds bounded CPU cost proportional
  to the retained selected CSV artifacts; it performs no I/O.
- The result is a matched observed-period energy account, not a canonical AEP, P-value, capacity
  factor, EYA reconciliation, finance input, or evidence-grade assessment.

## Verification receipt

This table is updated from commands run against the final checkpoint. Hosted exact-head CI and two
independent R3 exact-object reviews remain coordinator-owned delivery gates.

| Check | Exact command | Result |
|---|---|---|
| Recovery ingress focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q` on D1, D2, preserved D3, and v14 import surface | 209 passed in 1.86 s; starting diagnostic only |
| Freeze-1 D1-D3 focus | same command on `test_operational_evidence_contract.py`, `test_operational_normalization.py`, `test_operational_aep.py`, and v14 import surface | 235 passed in 2.28 s; superseded by independent-review rejection |
| Corrective D1-D3 focus | same command on those four contract modules after closing `D3-DOM-001` and `D3-ASSURANCE-001`, including the coverage-only hostile validation additions | 245 passed in 5.17 s on the final test bytes |
| Shared contract suite | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts` | 1638 passed in 103.50 s |
| D3 targeted coverage | governed Python `pytest` on `tests/contracts/test_operational_aep.py` with coverage for `analytics/operational/aep.py` | 62 passed; D3 increased from 88.38% (73 missing) to 93.47% (41 missing), covering 32 additional source statements without production-source changes |
| Fresh six-shard ordinary suite | exact CI `pytest-split` groups with `-n auto` and per-shard coverage data | shards 1 and 2 completed at 1516 passed/5 skipped and 1514 passed/7 skipped respectively, with only four known local-environment residual invocations; after the environment repair the exact residual family passed 6/6. Shards 3–6 then completed cleanly at 1519 passed/5 skipped, 1521 passed/3 skipped, 1520 passed/4 skipped, and 1517 passed/6 skipped. Shards 1–2 did not retain distinct coverage files, so no local combined-floor claim is made; hosted exact-head coverage is the decision receipt |
| Hosted pre-correction exact head | required checks on commit `9159ae2250689bc507e391e3006547f90075becd` | all six hosted shards, Grid Study, code quality, security, Fastlane, FX, and CodeQL passed; combined coverage alone failed at 94.94%, and Test Summary failed only as its aggregate consequence |
| Strict source types | governed Python `-m mypy --no-incremental analytics/operational/aep.py analytics/operational/contracts.py analytics/operational/normalization.py analytics/operational/__init__.py analytics/contracts_v14.py` | success; no issues in five source files |
| Public docstring ratchet | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/lint/test_docstring_coverage.py` | 12 passed in 3.38 s |
| Ruff lint/format | governed `ruff check` and `ruff format --check` over all six allowlisted Python paths | all checks passed; six files already formatted |
| Exact-file pre-commit | governed `pre-commit run --files` over the corrective three-path allowlist | Black formatted the corrective test on the first pass; the second and final pass passed every hook |
| Coverage-correction pre-commit | governed `pre-commit run --files tests/contracts/test_operational_aep.py docs/ISSUE_1333_IMPLEMENTATION_RECORD.md` | every hook passed; neither allowlisted file was rewritten |
| Changelog dry-run | governed Python `scripts/compile_changelog.py --dry-run` | passed and rendered pending fragments without repository mutation |
| GWTF bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD"` plus governed Python `dutchbay_bootstrap_rules.py` | final 75/75 active rules loaded |
| Main synchronization | compare live `refs/heads/main`, local `origin/main`, and candidate merge base | all three resolve to `03aab5e051e633d51b0d55bb93719ca17968adae` before the coverage-correction checkpoint |
| Diff/status hygiene | `git diff --check`; allowlist/status inspection | passed; only allowlisted paths differ from the persistence checkpoint; final clean status follows checkpoint commit |

The local environment residuals were removed without changing repository source or configuration.
The current worktree was installed editable into the existing shared cloud `.venv`, restoring
distribution metadata for tests that deliberately make the repository `pyproject.toml` unusable.
A workspace-local Linux child-subreaper launcher now adopts and promptly reaps orphaned watchdog
descendants in this container, whose PID 1 does not otherwise do so. The exact metadata case plus
all five process-reaping cases pass together (`6 passed in 9.18 s`) under that repaired environment.
Neither the repair nor the coverage-only tests change #1110 OPEN/HOLD or any canonical, finance,
release, lender, Board, professional, publication, or issue authority.
