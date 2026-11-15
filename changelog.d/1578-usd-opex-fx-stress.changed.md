- FX stress and Monte Carlo draws now reach a USD opex share that has its own FX path
  (`opex.currency_split.usd_lkr_depreciation_pct`). Work item #1578 line L-12 (domain D-2; the
  #1557 review's DOM-4). Before, an override of `fx` moved the model FX curve but not that path,
  so an FX drift stress left the USD opex unchanged.
  - `finance/cashflow_v14_params.py`: `with_usd_opex_fx_reference` records the base `fx` block
    as `opex.currency_split.usd_fx_reference` when an override changed `fx`. The resolver
    validates the key: a mapping with a financial-close spot, and only beside an own USD path.
  - `finance/cashflow_v14.py`: with a reference, the engine compares the model curve with it,
    each relative to its own spot. When the shape changed (a drift stress or draw), the stressed
    model curve replaces the USD share's own path, so a drift of x runs the share at x, not at x
    on top of the authored rate (owner ruling, 2026-11-15). A spot-only or curve-neutral change
    keeps the own path, which already anchors on the merged spot.
  - `analytics/evaluation_v14.py` (`evaluate_with_overrides`, `evaluate_scenario_from_dict`) and
    `analytics/evaluate_scenario.py`: these Python override gateways, which the Monte Carlo and
    sensitivity tools use, call it after merging. The web API's `/run-pipeline` overrides
    (`api/pipeline_api.py`) do not yet, so an FX drift sent there still leaves the USD share on
    its own path; that is a follow-up on #1578.
  - No committed KPI moves: every scenario's base case is byte-identical, and an `fx` change that
    leaves the curve alone is too. Stress and Monte Carlo outputs on the Blue Whale wind project
    move: a 3%/yr drift stress now gives project IRR 9.50% (was 9.60%), and 5.89%/yr gives 6.35%
    (was 7.04%). A market-calibrated Monte Carlo drift, a nominal rate, replaces the path too,
    so it does not double count inflation. No VERSION bump (#1625).
  - These are cost-side stresses: the tariff's escalable O&M index (`tariff.om_indexation`, 70%
    weighted to LKR/USD depreciation at the same 2.44%/yr) is not moved by an `fx` override, so
    above 2.44%/yr the stressed IRRs are lower, and below it higher, than a stress that also
    moved the index would give. The neutral drift for the USD share is 2.44%/yr, not zero, so a
    drift near zero gives an IRR above the base case. Moving the index too is a separate owner
    decision.
  - The FX and tenor screening's engine-path status and notes now say the engine path exists,
    and the dated review document gains an addendum saying so; the screening still does not
    call the engine.
