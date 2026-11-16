- The equipment-cost parity analysis runs for any scenario that declares an
  `equipment_cost_parity` block (#1755, U5 of the owner's 2026-11-16 ruling that every
  scenario includes the site analyses; block contract #1754).
  - `analytics/wind/equipment_parity.py` holds the arithmetic with no site name, path or
    figure.
  - `scripts/run_equipment_parity_v14.py scenario=<path>` runs it, with the method inputs
    in `conf/equipment_parity.yaml`.
  - A scenario without the block reports "not applicable".
  - Result keys are site-neutral: `benchmark_*` and `site_*` replace the single-site names.
  - The single-site module and script now adapt their old config to the universal module
    and print byte-identical output.
  - The block-driven run reproduces the single-site result exactly under the key map.
  - No engine, scenario or KPI figure changes. The F-5 hold applies.
