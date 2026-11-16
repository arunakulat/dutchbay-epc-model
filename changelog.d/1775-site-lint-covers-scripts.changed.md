- The no-site-literals lint from #1759 now also reads `scripts/`, `analysis_tools/`,
  `feasibility_reproduce/` and `monte_carlo/`, and it knows Kolonnawa, Sri Jayewardenepura
  Kotte, Battaramulla and Colombo (#1775, after the owner's 2026-11-16 ruling that all code
  must be available to any scenario). Every literal it finds there is fixed or allow-listed
  with the work item that removes it. The Blue Whale runners wait for U2 to U6, and the solar
  assessment report's site block waits for the solar follow-up. `scripts/process_era5_wind_data.py`
  no longer holds the DutchBay turbine positions or treats all 15 as DutchBay's. It reads the
  layout from a YAML argument (DutchBay's is `conf/dutchbay_wake_14_turbines.yaml`), processes
  the counted turbines and lists T2, the Blue Whale turbine, as skipped. The wake
  re-baseline's turbine role `dutchbay` is renamed `counted`, so the role names no site. Help
  text names `scenarios/example.yaml`, and two scripts now require the path they used to
  default to a site file. No engine, scenario or KPI figure moves.
