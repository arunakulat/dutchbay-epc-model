- FX stress and Monte Carlo draws now reach a USD opex share that has its own FX path
  (`opex.currency_split.usd_lkr_depreciation_pct`). Work item #1578 line L-12 (domain D-2; the
  #1557 review's DOM-4). Before, an override of `fx` moved the model FX curve but not that path,
  so an FX drift stress left the USD opex unchanged.
  - `finance/cashflow_v14_params.py`: `with_usd_opex_fx_reference` records the base `fx` block
    as `opex.currency_split.usd_fx_reference` when an override changed `fx`. The resolver
    validates the key: a mapping with a financial-close spot, and only beside an own USD path.
  - `finance/cashflow_v14.py`: with a reference, the USD path is multiplied year by year by the
    model curve's ratio to the reference curve, each relative to its own spot, so a spot change
    (which the path already anchors on) is not counted twice.
  - `analytics/evaluation_v14.py` (`evaluate_with_overrides`, `evaluate_scenario_from_dict`) and
    `analytics/evaluate_scenario.py`: every override gateway calls it after merging.
  - `analytics/mc/engine.py`: a market-calibrated FX driver (`distribution: fx_calibrated`)
    with `drive_drift` on is refused on a scenario whose USD share has its own FX path. Its
    drift is a nominal, history-derived rate, and compounding it on the path's own rate would
    count the inflation differential twice. `drive_drift: false` (spot only) still runs.
  - No committed KPI moves: every scenario's base case is byte-identical, and an `fx` change that
    leaves the curve alone is too. Stress and Monte Carlo outputs on the Blue Whale wind project
    move: a 3%/yr drift stress now gives project IRR 8.98% (was 9.60%). No VERSION bump (#1625).
  - The FX and tenor screening's engine-path status and notes now say the engine path exists,
    and the dated review document gains an addendum saying so; the screening still does not
    call the engine.
