- The no-site-literals lint from #1759 now also reads `scripts/`, `analysis_tools/` and
  `feasibility_reproduce/` (and `monte_carlo/`, which holds no Python today), and it knows
  Kolonnawa, Sri Jayewardenepura Kotte, Battaramulla and Colombo (#1775, after the owner's
  2026-11-16 ruling that all code must be available to any scenario). Every literal it finds
  there is fixed or allow-listed with the work item that removes it. The Blue Whale runners
  wait for U2 to U6, and the solar assessment report's site block waits for #1784 and the
  financing questionnaire's scenario paths for #1783. Each file waived whole has its count of
  site literals pinned, so a new one fails. `scripts/process_era5_wind_data.py` no longer
  holds the DutchBay turbine positions or treats all 15 as DutchBay's. It reads the layout
  from a YAML argument (DutchBay's is `conf/dutchbay_wake_14_turbines.yaml`), processes the
  counted turbines and lists T2, the Blue Whale turbine, as skipped. Its hub height comes from
  `turbine.hub_height_m` beside the layout and is required, and its outputs are named
  `wind_hub_*.csv` with `ws_hub` columns. The wake re-baseline's turbine role `dutchbay` is
  renamed `counted`, so the role names no site. Help text names `scenarios/example.yaml` or no
  path, and two scripts now require the path they used to default to a site file. No engine,
  scenario or KPI figure moves.
