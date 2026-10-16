# Issue #1333 D3 implementation record

## Scope, authority, and source ingress

D3 adds one non-canonical operational-energy accounting boundary over immutable D1/D2
artifacts. It does not change D1/D2 normalization, canonical AEP, scenarios, finance, reports,
release state, or issue #1110. Every result is exactly false for canonical-finance,
bankability, lender, and Board eligibility. The Board/lender reliance HOLD remains active.

The controlling implementation lease is `L-1333-D3-001`, recorded in issue #1333 comment
`6201589355`; the capability profile is comment `6201394718`. The writer independently read the
contract/harness ingress (`6201512739`), renewable-energy ingress (`6201581582`), their named
repository sources, the complete D1/D2 implementation records and predecessor reviews, and the
OpenOA v3.2 sources at commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2`:

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
code and adopts none of its stochastic paths.

## Evidence and equation contract

The factory requires explicit logical-ID selectors and exactly one selected D2 result per logical
ID. The meter and turbine products must occur together in one D1 `electrical_losses` envelope;
the meter and availability/curtailment products must occur together in one D1 `long_term_aep`
envelope. All envelopes bind the same project. Every selected D2 series must independently resolve
to the same start and end-exclusive effective interval. Fixed-second interval-average power is
integrated as the exact rational `power_kw * interval_seconds / 3600`; interval energy is summed
exactly. Source-UTC and supplied-TZif calendar-month energy can share a boundary with complete
fixed-second turbine evidence.

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

## Temporal, uncertainty, and authority boundaries

Only `observed_period_total` and a strictly complete UTC `actual_calendar_year` are accepted
temporal labels. Long-term-average energy is always unavailable in this checkpoint. Annual and
long-term-average uncertainty are separate structural fields; both are
`unavailable_not_estimated`, have no basis, and have separate empty exceedance tuples. Reanalysis
presence never creates resource gross, LTA, P50, P90, or uncertainty. A future LTA or uncertainty
result requires a separately governed method, covariance/input contract, deterministic oracle,
and new review.

The result retains all inputs and is factory-only. Construction replays components, ratios,
source-manifest identity, method identity, reconciliation residuals, uncertainty state, and hard
authority flags. Model dumps omit retained source and method bytes.

## Independent fixture and hostile controls

The independently hand-derived four-interval fixture has two turbines at 500 kW for four 15-minute
intervals, meter energy 237.5 kWh per interval, availability 25 kWh per interval, curtailment
12.5 kWh per interval, separately evidenced `R=1250 kWh`, and `W=80 kWh`. The exact oracle is
`T=1000`, `M=950`, `A=100`, `C=50`, `E=50`, meter loss-restored gross `1100`, turbine-known gross
`1150`, and `U=20`. Exact ratios include `E/T=1/20`, `M/R=19/25`, and `U/R=2/125`.

The focused suite also covers evidenced zero versus unavailable, calendar-month/fixed-day matched
bounds, Decimal-context independence, input-order invariance, exact scaling, split/merge interval
invariance, selector ambiguity, project/window/ID mismatch, negative electrical and residual loss,
huge/non-finite/wrong-type tolerance values, provenance substitution, factory replay,
serialization, temporal/LTA/uncertainty laundering, authority flags, and resource-without-wake
anti-inference.

## Predecessor finding matrix

| Finding family | D3 disposition |
|---|---|
| D1 product isolation, cadence/calendar declaration, timezone policy, epistemic status, derived lineage, portable zone keys, digest-role separation, runtime errors, and authority fences | `CLOSED` by consuming only exact D1 evidence objects retained in verified D2 results and matched D1 envelopes; D3 does not loosen D1 |
| D2 context-independent numeric parsing and aggregation | `CLOSED` by retaining D2 objects and using a separate exact `Fraction` implementation; no float/global Decimal context |
| D2 population/group completeness, row/byte replay, timezone/TZif binding, interval/resource bounds, and predictable failures | `CLOSED` for selected inputs by requiring successful factory-bound D2 results and a complete SCADA group universe |
| D2 RFC 9636 leap/indicator/start-truncation chain, including first correction zero | `NOT_APPLICABLE_WITH_REASON`: D3 consumes normalized UTC rows and does not parse or alter TZif bytes; retained named-zone calendar rules are used only to establish the next end-exclusive month boundary |
| Missing resource gross, wake/performance, unknown residual, LTA, and uncertainty evidence | `CLOSED` by explicit unavailable states; `R/W/U` become available only under the supplemental provenance rules above |
| Canonical finance, lender, Board, release, professional, publication, issue-closure, and HOLD authority | `CLOSED` by hard-false flags and explicit non-authority; #1110 remains OPEN/HOLD |

## Deliberate limitations

- Boundary evidence is caller-attested; D3 does not authenticate an operator, meter, asset roster,
  resource model, or wake method.
- D3 supports only the D1/D2 CSV normalization contract. It performs no file, network, database,
  OpenOA, interpolation, gap repair, imputation, or unit conversion.
- Combined wake/performance is one explicit scalar category. Separating wake, turbine performance,
  blade degradation, or resource-model bias needs new evidence and contracts.
- Availability/curtailment exclusivity is attested, not inferred from status/event overlap.
- The result is a matched observed-period energy account, not a canonical AEP, P-value, capacity
  factor, EYA reconciliation, finance input, or evidence-grade assessment.

## Verification receipt

This table is updated from commands run against the final checkpoint. Hosted exact-head CI and two
independent R3 exact-object reviews remain coordinator-owned delivery gates.

| Check | Exact command | Result |
|---|---|---|
| Initial D3/import focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_operational_aep.py tests/contracts/test_contracts_v14_import_surface.py` | 32 passed in 1.20 s after calendar fixture |
| Strict source types | governed Python `-m mypy --no-incremental analytics/operational/aep.py analytics/operational/contracts.py analytics/operational/normalization.py analytics/operational/__init__.py analytics/contracts_v14.py` | success; no issues in five source files |
| Final D1-D3 focus | pending final checkpoint | pending |
| Shared contract suite | pending final checkpoint | pending |
| Complete ordinary suite / six shards | pending final checkpoint | pending |
| Public docstring ratchet | pending final checkpoint | pending |
| Ruff lint/format | pending final checkpoint | pending |
| Exact-file pre-commit | pending final checkpoint | pending |
| Changelog dry-run | pending final checkpoint | pending |
| GWTF bootstrap | initial preflight passed 75/75; final rerun pending | pending final rerun |
| Diff/status hygiene | pending final checkpoint | pending |

