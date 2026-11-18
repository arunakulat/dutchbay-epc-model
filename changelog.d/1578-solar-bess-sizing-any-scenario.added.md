- The PV + BESS project sizing runs for any scenario that declares a `solar_storage_sizing`
  block (#1578 U3 of the owner's 2026-11-16 ruling that every scenario includes the site
  analyses; block contract #1754).
  - `solar_resource/pv_bess_sizing_runner.py` holds the run, its code digest (MRM-02) and its
    concise summary, moved from the single-site script with no site name. The concise
    summary's eligibility columns follow the readings' own names.
  - `scripts/run_solar_bess_sizing_v14.py scenario=<path>` runs it, with the Monte Carlo
    settings and the objective in `conf/solar_bess_sizing.yaml`. A scenario without the block
    reports "not applicable".
  - The block contract is rewritten to what the sizing reads (configs, unit overrides, search
    grid, readings, uncertainty, battery health, plant, curtailment, sensitivities, the recorded
    choice and the stated limitations); no scenario declared the old one.
  - `scenarios/blue_whale_solar_bess_lot5b_2026.yaml` carries the block, moved from
    `conf/blue_whale_solar_bess_project_sizing.yaml`. The engine does not read it. A reduced run
    through the block reproduces the single-site run point for point.
  - The single-site script keeps its output through the moved run; #1799 retires it.
  - #1725 review residuals: a reading may not be named `by_reading`, the module's comments
    drop the input-sheet cell, 10 MW and placeholder-lot wording, and the site-neutral tests
    pin the readings' config order and scan comments.
  - No engine, scenario KPI or committed figure changes.
