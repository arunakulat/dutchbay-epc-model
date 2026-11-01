- Blue Whale wind resource from met mast 617725 (15.14.0). On the owner's direction of 1 Nov
  2026 (#1353 comment 6556910250), the Kalpitiya met-mast record is transferred 26.7 km to the
  Blue Whale turbine and its yield re-derived. Not lender-grade: the met-mast package's HOLD on
  annual, P50/P90 and lender use stands.
  - New `analytics/wind/met_mast_transfer.py`, `conf/blue_whale_met_mast_transfer.yaml` and the
    Hydra CLI `scripts/run_blue_whale_met_mast_transfer_v14.py`: the private mast is
    hash-checked against the package's private-source manifest and the public NASA POWER /
    MERRA-2 hourly reference (2015-2025) against per-year data pins; mast clock established as
    UTC+05:30 from the S2 pressure tide and checked on every run; variance-ratio MCP at 120 m
    by 16 reference sectors (hourly R^2 0.610, daily r 0.881) reusing `wind_resource.mcp`;
    direction carried by the measured residual deciles; long-term 2015-2025 hour by hour;
    shear to 130 m by sector and day/night; transfer through the reference's turbine/mast
    cell ratio and veer.
  - Results, aggregates only, in `docs/blue_whale/met_mast_transfer_summary.json`, the 16-sector
    rose `docs/blue_whale/met_mast_wind_rose_130m.csv` and `.png`, and the methods note
    `docs/blue_whale/MET_MAST_TRANSFER_METHODS.md`: mean 8.243 m/s at 130 m, Weibull A 9.207,
    k 3.044; SW 26.6% of hours. Net AEP 40.57 GWh, CF 0.487560 (was 31.15 GWh, 0.374256 on
    #1530's ERA5 basis); P90 33.73 GWh (1 year), 33.92 GWh (20 years).
  - `analytics/gis/shadow_flicker.py` gains a yawed-rotor expected case; at the placeholder lot
    the west-edge midpoint falls from 1,816 to 826 expected h/yr (worst case 2,054).
  - Wind scenario v0.2 and the superseded hybrid v0.7 (wind block mirrored; project CF and
    tariff blend by their formulas). Wind project IRR 4.09% -> 7.80%; hybrid 4.26% -> 6.90%.
  - The met-mast package README records the promotion and the HOLD; its manifest pin is
    refreshed. Four existing Blue Whale tests are re-pointed under the coordinator's ruling:
    two KPI re-pins, PR 3's tariff oracle (now the blend formula, with PR 3's frozen value
    still reproduced) and #1530's private-curve check (now against the recorded ERA5 basis).
