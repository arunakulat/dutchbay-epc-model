# Deterministic hourly BESS feasibility ledger

Issue #1402 implements the input and feasibility stages of roadmap P1.4. The
ledger follows supplied instructions; it does not choose dispatch, value energy,
establish dispatch rights or produce a network study. It has no cashflow apply
path. CEB dispatch control or a quoted price is not permission to optimize a
merchant strategy.

The API is standalone and default-off. The financial evaluation gateway does not
call it. A caller explicitly invokes
`analytics.storage_dispatch.evaluate_chronological_dispatch(config)`; an absent
`chronological_dispatch` block, or an explicitly disabled block, returns `None`.
An enabled block requires a complete `inputs` mapping. Unknown block/input fields
are refused. Price-only input is unsupported: an authorized instruction schedule
must be supplied, rather than inferred from prices.

## Complete authored envelope

`analytics.contracts_v14.ChronologicalDispatchInput` is the central immutable
contract. `from_mapping()` copies YAML lists into tuples; direct construction
requires immutable tuples. All fields below are required when enabled. There are
no implicit size, efficiency, SOC, outage, charge-source or envelope defaults.

| Field | Meaning and boundary |
|---|---|
| `sizing` | Shared #1401 ratings: required `power_mw`, `duration_h`; optional `energy_mwh` derives or reconciles under that contract. The dedicated mapping accepts only these rating fields. |
| `timestamps_utc`, `step_h` | Nonempty, consecutive UTC hour starts and explicitly `1.0` hour. Gaps, duplicates, local time inference and other step sizes fail. |
| `wind_generation_mwh`, `solar_generation_mwh` | Available AC energy before the supplied outage masks; nonnegative hourly sequences. Generation losses already reflected in these inputs must not be entered again as outage losses. |
| `dispatch_instruction_mw` | Signed hourly AC request: negative charges, positive discharges, zero is idle. No optimization objective is derived. |
| `poc_limit_mw`, `poc_outage` | Hourly shared power limit and explicit POC outage mask. A zero limit is valid. An outage makes grid import/export zero while allowing internal renewable charging. |
| `wind_outage`, `solar_outage`, `bess_outage` | Explicit boolean hourly masks. Generation in an outage is assigned to named outage energy; an unavailable battery neither charges nor discharges. |
| `charge_source` | Each charging hour explicitly selects `renewable` or `grid`; noncharging hours select `none`. Grid energy is never relabelled renewable. |
| `charge_efficiency`, `discharge_efficiency` | Separate authored one-way factors in `(0,1]`. No square-root decomposition of a round-trip value. |
| `soh_fraction` | Explicit static fraction in `(0,1]`, used by the existing #879 SOC model. No cycle aging or augmentation is inferred. |
| `minimum_soc_fraction`, `maximum_soc_fraction` | Authored operating window in `[0,1]`, minimum below maximum. Fractions refer to nameplate energy times static SoH, using the existing SOC accounting basis. |
| `initial_soc_fraction`, `final_soc_fraction` | Initial state and required final target inside the operating window. The target is tested, never manufactured by a balancing adjustment. |
| `poc_flow_basis` | Must explicitly select `gross_sum`: grid charging imports plus all exports share the POC limit. This is conservative and does not represent net-metered trading or infer contractual netting. |
| `allocation_policy` | Must explicitly select `charge_then_generation_then_discharge`: meet feasible charging instructions, export available generation, then discharge into remaining POC space. No alternative priority is silently selected. |
| `tariff_terms`, `ld_terms`, `provenance` | Required nonempty source/limitation text. A caller must identify terms or explicitly state why they are inapplicable/unmodelled. The strings are retained as evidence context, never converted into remuneration or LD cashflow. |

All hourly sequences must match the timeline. Boolean/string coercion to numeric
values, nonfinite values, numeric overflow, incompatible ratings and unknown
fields fail with field-specific `ValueError`s. The shared rating contract retains
its existing authored-energy tolerance; this ledger does not redefine it.

## Physical accounting

Each interval records wind/solar energy separately as outage energy, energy sent
to the battery, energy delivered at the POC or curtailment. Renewable charging and
export use pro-rata source attribution. That split is bookkeeping; it is not an
economic priority or an optimization result. Grid charging has its own custody
field. Available generation and battery discharge cannot each claim the same POC
capacity. Charging and discharging cannot occur together.

Battery charge/discharge headroom comes from the pre-existing
`analytics.grid.capabilities.bess_soc.bess_soc_state()` model. The dynamic state
uses its nameplate-equivalent stored-energy basis; the input/output AC terminal
flows account explicitly for one-way conversion losses. A battery with lower
static SoH has less usable energy. No independent second SOC-window model is
introduced.

For the whole ledger, in MWh:

```text
wind input + solar input + grid import
  = POC delivery + change in stored energy
    + charge loss + discharge loss
    + wind/solar curtailment + wind/solar outage energy
```

The receipt validates each source's custody, stored-energy continuity, conversion
losses, requests and power/SOC/POC/outage bounds independently of its feasibility
flag. This balance is an accounting identity, not independent validation of the
input data or dispatch rights. Independent tests include a hand-derived rational
two-hour example, the pre-existing static SOC oracle and hostile seeded
chronologies. A zero residual alone proves no bankability claim.

An infeasible instruction is bounded by power, headroom, source availability and
POC capacity. The unserved part remains in `unmet_charge_mwh` or
`unmet_discharge_mwh`. `feasible` is true only when every instruction and the final
SOC target are met. Final mismatch remains visible in `final_soc_error_mwh`.
Numerical comparisons use a declared absolute tolerance of `1e-8 MWh`; only
floating-point boundary round-off is bounded, and instruction shortfalls remain
reported. Invalid authored states are refused rather than clamped.

`DispatchLedger.model_dump()` emits JSON-native input provenance, the input
SHA-256, hourly flows, feasibility and limitations. Serialization revalidates the
immutable inputs/receipt, including hostile mutation through Python internals.
`bankable` is always false; there are no revenue, IRR, DSCR or merchant-value
fields.

## Limits and later work

This hourly feasibility model does not resolve sub-hour transients, electrical
network losses, grid acceptance, self-discharge, dynamic SoH, augmentation, cycle
costs or financial consequences. Gross POC accounting may refuse a schedule that
a separately evidenced netting arrangement could allow. A different convention
requires an explicit contract extension and independent review, rather than a
quiet assumption change.

LP/MILP optimization, cashflow linkage and merchant/do-nothing comparisons remain
outside this issue. No committed scenario is enabled by this change. The
canonical lender case and financial KPIs retain their existing evaluation path.
#1110's Board/lender circulation HOLD and F-5 remain unchanged.
