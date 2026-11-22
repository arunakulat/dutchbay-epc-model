- **Blue Whale wake loss from the DutchBay turbines, as a labelled sensitivity (#1887)**:
  `scripts/run_neighbour_wake_sensitivity_v14.py` (Hydra, site-free; its inputs and labels in
  `conf/neighbour_wake_sensitivity.yaml`) runs the turbine at T2 as the only counted
  turbine, waked by every DutchBay turbine, on Blue Whale's long-term 130 m resource with a
  proxy machine. Results, pinned by SHA-256 to their inputs, are in
  `docs/blue_whale/wake_from_dutchbay_1887_summary.json` and cited in
  `docs/blue_whale/STATUS.md`. Nothing is applied: no scenario input, budget value or KPI
  changes.
