- The wind battery options run for any scenario that declares a `storage_options` block
  (#1578 U2 of the owner's 2026-11-16 ruling that every scenario includes the site analyses;
  block contract #1754).
  - `analytics/wind/wind_bess_options_runner.py` holds the evaluation with no site name, path
    or figure. `scripts/run_wind_bess_options_v14.py scenario=<path>` runs it, with the method
    inputs in `conf/wind_bess_options.yaml`. A scenario without the block reports "not
    applicable".
  - The `storage_options` contract gains what the options read: turbine air density and
    losses, battery prices and reserve, the hourly-profile reference, an operation per option,
    the cross-check tariff lines and adjustment weights, the export-cap readings and ramp limit,
    the firming supplier's prices and the wind-yield uncertainty.
  - `scenarios/blue_whale_wind_lot5b_2026.yaml` carries the block, moved from
    `conf/blue_whale_wind_bess_options.yaml`, and an `equipment_cost_parity` block moved from
    `conf/blue_whale_equipment_parity.yaml` (#1755). The engine reads neither.
  - The single-site script is a shim over the runner. Its output is byte-identical, and the
    block-driven run reproduces every figure. `docs/blue_whale/wind_bess_options_summary.json`
    is regenerated for the new scenario digest only.
  - The wind options doc and the review follow-up fragment now say the bottom-up swap of two
    middle-ranked options depends on where the all-in factor is calibrated, and that the flat
    price is a floor for the short units only. The ranking test pins only what holds under both
    calibrations.
  - No engine, scenario KPI or committed figure changes. The F-5 hold applies.
