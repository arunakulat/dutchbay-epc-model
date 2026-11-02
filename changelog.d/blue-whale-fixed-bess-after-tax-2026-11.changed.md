- Blue Whale solar + BESS: the owner's 5 MW / 20 MWh battery, ranked on the after-tax project
  NPV (15.17.0 -> 15.18.0). Owner decisions of 1 Nov 2026 (#1353 comment 6563070978):
  "Fix 5 MW / 20 MWh", "After-tax project NPV (Recommended)" and "Keep ERA5, fix README
  (Recommended)".
  - `conf/blue_whale_solar_bess_project_sizing.yaml` ranks on the P50 of the engine's after-tax
    project NPV (through `evaluate_with_overrides`); PR 4's unit pre-tax NPV stays selectable and
    off by default. `solar_resource/pv_bess_sizing.py` records the objective's P50 and P90 at each
    choice and the metrics the config reports beside it (`objective.report_beside`).
  - New `conf/blue_whale_solar_bess_fixed_bess_sizing.yaml` (a Hydra child of the project config):
    BESS 5.0 MW / 20.0 MWh, PV AC 5.0 MW (reading A at its 10 MW limit), PV DC 134-191 tables;
    same seed and 256 trials. It chooses 151 tables (5.66552 MWp, DC/AC 1.1331): after-tax project
    NPV P50 USD -5,326,884, P90 -5,911,801; no project IRR.
  - The full grid, re-run under the new objective (every grid row identical to PR 6's run), gives
    the value-based size: 107 tables, 3.5 MW AC, 1.0 MW / 4.0 MWh (P50 -4,079,718, P90
    -4,321,796). The owner's battery costs USD 1,247,165 at P50 and 1,590,005 at P90.
  - Solar + BESS scenario v0.3: capex 8,270,743 (was 5,011,440); project NPV USD -4,992,409 (was
    -4,027,656); equity IRR -3.58% (was -11.32%); no project IRR. Wind and hybrid unchanged.
  - `inputs/solar_tmy/README.md` now names PVGIS-ERA5, not SARAH3 (#1540's finding), with the
    satellite figures as upside; no data file changed.
