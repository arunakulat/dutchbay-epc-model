# Grid Interconnection Interface Schema (`grid` + per-tech `grid`)

The design-stage grid-strength / interconnection screen (`analytics.grid`,
issue #872 D1 / #873 D2) reads a single **config-first** block. Like the
`resource.wind` handoff it is a strict, versioned contract validated at
pre-flight by the CESSPIT schema guard — no silent defaults.

> **ADVISORY & KPI-NEUTRAL.** This block feeds the grid SCREEN only; it never
> touches the finance engine. Every published KPI (project/equity IRR, NPV,
> DSCR) is byte-identical whether or not the block is present. The feature is
> **default-OFF** — `grid.study_enabled: false` keeps the whole screen dormant.
>
> **NOT a bankable grid study.** An in-house Python screen is never the
> utility-accepted connection study; CEB/NSCC require PSS/E or PowerFactory
> against their confidential grid base case. See the provenance gate below.

## Enforcement (opt-in / validate-when-present)

`validate_config_for_v14` adds the `"grid"` module **only when a top-level
`grid` block is present**, and runs the per-tech grid rules **only when a
`generation.technologies.<name>.grid` block is present**. A scenario with no
grid anywhere is untouched (byte-identical). A **present** block is strict.

```python
from analytics.schema_guard import validate_config_for_v14
validate_config_for_v14(parsed_config, "scenario.yaml", ["grid"])
```

## Top-level `grid` block

```yaml
grid:
  study_enabled: false          # master gate (strict bool; default-OFF)
  allow_unvalidated_grid: true  # opt-in — REQUIRED for a screening_estimate Thevenin

  # D1 flat core (the scalars the closed-form / pandapower screen consumes today)
  poc_voltage_kv: 33.0
  source_fault_level_mva: 900.0
  source_rx: 0.083
  connection_r_ohm: 0.6
  connection_x_ohm: 6.0
  plant_rating_mva: 159.6

  # D2 structured per-site interconnection block (#873)
  poc:
    bus_name: "Puttalam 220kV Substation"
    nominal_kv: 33.0
    plant_rated_mva: 159.6
  thevenin:
    short_circuit_mva_min: 700.0   # IEC-60909 MIN — GOVERNS the screen
    short_circuit_mva_max: 1100.0  # IEC-60909 MAX — context only
    x_r: 12.0
    assumption_basis: "screening_estimate"  # or "utility_provided"
  scr:
    gfl_min: 3.0
    gfl_comfortable: 5.0
  gridcode:
    pf_range: [-0.95, 0.95]
    voltage_control_mode: "voltage_droop"
    lvrt_hvrt_envelope: "ceb_grid_code_2023"
    rc_k_factor: 2.0
    freq_ride_through: "47.5-51.5Hz continuous"
    harmonic_allocation: "IEC 61000-3-6 stage-2 (pending CEB allocation)"
```

(Live example: `scenarios/dutchbay_lendercase_2025Q4.yaml`.)

### Fields & validation

| Field | Rule |
|---|---|
| `study_enabled` | strict `bool` (a truthy string is rejected) |
| `poc_voltage_kv` | number, `> 0` |
| `source_fault_level_mva` | number, `> 0` |
| `source_rx` | number, `>= 0` |
| `connection_r_ohm` / `connection_x_ohm` | number, `>= 0` |
| `plant_rating_mva` | number, `> 0` (the SCR denominator) |
| `poc.bus_name` | non-empty string |
| `poc.nominal_kv` | number, `> 0` |
| `poc.plant_rated_mva` | number, `> 0` |
| `thevenin.short_circuit_mva_min` | number, `> 0`; **must be `<=` max** (min case governs) |
| `thevenin.short_circuit_mva_max` | number, `> 0` |
| `thevenin.x_r` | number, `>= 0` |
| `thevenin.assumption_basis` | enum: `utility_provided` \| `screening_estimate` |
| `allow_unvalidated_grid` | strict `bool`; **required `true` for a `screening_estimate` basis** |

`scr.*` and `gridcode.*` are the lender-facing SCR thresholds and grid-code
envelope (descriptive; carried for the report, not range-gated here).

### Provenance gate (`assumption_basis` + `allow_unvalidated_grid`)

- `assumption_basis: utility_provided` — a CEB/NSCC-issued fault level. No opt-in
  needed.
- `assumption_basis: screening_estimate` — an in-house rule-of-thumb. It is **not
  bankable**, so the guard **REFUSES** it unless the block sets
  `allow_unvalidated_grid: true`. This mirrors `allow_unvalidated_flat_cf`
  (`finance.tech_types`): a user can never silently treat an estimate as
  bankable. The in-house screen is never bankable regardless
  (`GridStrengthResult.bankable is False`); this gate only governs whether an
  estimated input may feed it.

## Per-tech `generation.technologies.<name>.grid`

Opt-in per technology. A tech without a `grid` block is untouched. When present,
the tech must be a converter-interfaced class (`wind`, `solar`, `bess` —
`finance.grid.grid_types.MODELLED_GRID_TECHS`).

```yaml
generation:
  technologies:
    wind:
      capacity_mw: 159.6
      capacity_factor: 0.332
      grid:
        rated_mva: 168.0
        converter_type: "gfl"          # gfl | grid_following | gfm | grid_forming
        reactive_capability:
          pf_range: [-0.95, 0.95]
        transformer:
          impedance_pu: 0.10
        collector:
          impedance_pu: 0.02
        dynamic_model:                 # committed model => validated interface
          family: "REGC_A/REEC_A/REPC_A"
          params_ref: "tests/fixtures/grid/envision_enpcs01_gridcode.yaml"
          source: "Envision ENPCS01 PSS/E UDM V2"
        # allow_unvalidated_grid: true # REQUIRED if `dynamic_model` is omitted
```

| Field | Rule |
|---|---|
| `<tech>` | must be in `MODELLED_GRID_TECHS` (`wind`, `solar`, `bess`) |
| `grid.rated_mva` | number, `> 0` |
| `grid.converter_type` | enum: `gfl` \| `grid_following` \| `gfm` \| `grid_forming` |
| `grid.dynamic_model` | mapping `{family, params_ref, source}`; **if omitted the interface is enum-only and requires `allow_unvalidated_grid: true`** |

`transformer` / `collector` impedances and `reactive_capability` are carried for
the screen (descriptive). An **enum-only** interface (a bare `converter_type`
with no `dynamic_model`) is unvalidated and gated exactly like the estimated
Thevenin.

## Where it lives

- Schema + conditional rules: `analytics/grid/grid_interface_schema.py`
  (`validate_grid_block`).
- Type discriminators + opt-in gate: `finance/grid/grid_types.py`.
- Guard wiring: `analytics/schema_guard.py` (`_validate_grid_conditionals`, the
  present-only auto-enforce loop).
- Tests: `tests/grid/test_grid_config_d2.py` (D2) and
  `tests/grid/test_grid_scaffold.py` (D1 core).
