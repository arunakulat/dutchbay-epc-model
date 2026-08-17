# MANIFEST — provenance & expected outputs

## Engine / environment
- Repo: `arunakulat/dutchbay-epc-model`, engine **v15.3.1**, main @ **7e64d33**
  (includes F5-01 COD-aligned operating FX #1034/#1038; grid fixes #929 `boundary_clip` segfault + #930 `ride_through` kwarg).
- Python **3.11** (`.venv`). Extras: `[grid]` (pandapower 3.3.0 / andes 2.0.0 / opendssdirect 0.9.4),
  `[wind]` (py_wake / topfarm / SALib / rasterio / geopandas / xarray), plus `weasyprint` + `mistune`.
- Canonical scenario: `scenarios/dutchbay_lendercase_2025Q4.yaml`.

## Golden numbers — finance canon (MUST reproduce byte-identically, 1e-9)
| KPI | Value |
|---|---|
| project_irr | -0.001166233356501311 |
| equity_irr | −0.07853839579881527 |
| min_dscr | 1.3 |
| project_npv | −91,810,995 (−$91.81 M) |

## Expected outputs (deterministic, seed 42) — see `cache/expected/`
| Step | Key result |
|---|---|
| Fresh AEP (long-way baseline) | net P50 464.36 GWh / CF 0.3322 (= committed 464.3 / 0.332) |
| ERA5 ARCO (cached) | mean 7.46 m/s (20-yr); prevailing 210° SW; Mann-Kendall p=0.0047 (secular stilling) |
| AEP tornado | wind-speed bias ±20.5 % dominant; power-curve −16 %; shear ±6.6 %; losses ±6.4 % |
| Micro-siting | baseline 551.0 → ~558 GWh (+~1 % candidate, KPI-neutral) |
| Scenario suite (8) | equity IRR −9.44 % … +4.90 %; every scenario NPV-negative |
| Monte-Carlo (2,500) | equity IRR P10/P50/P90 −13.0/−9.1/−5.0 %; NPV negative in 100 %; min-DSCR ≥1.217; 0 toy-fallbacks |
| Sobol total-order (equity IRR) | tariff 0.47 (dominant) > capex 0.19 > fx 0.12 > cf 0.12 |
| Optimizer | 36 debt-mix candidates, all negative; best −6.21 % (DFI40/USD60) |
| Grid screen | SCR@POC 0.94 (weak, screening-only); ride-through 3 cases; KPI byte-identical |
| Emitters | capital-risk + executive-workbook + tech-comparison + interaction-grid all fire |

## Re-baseline scope (2026-08-17, F5-01 #1034/#1038)

The F5-01 correction aligns the operating FX path to COD. It moves the **finance** layer only, so
this pass regenerated the canon run, the 8-scenario suite, the 2,500-trial Monte-Carlo, both
optimizer modes and the study Markdown/PDF against engine `v15.3.1` (`7e64d33`).

Carried forward unchanged (inputs to finance, unaffected by an FX-timing correction, and in two
cases network-bound): the fresh-AEP baseline, cached ERA5 ARCO, AEP tornado, micro-siting, GIS
layers, grid screen, and the Sobol/PAWN global-sensitivity indices. `report/MODULE_CATALOG.md` and
`report/FEASIBILITY_COVERAGE.md` remain pinned to the commit their inventory was taken at
(`v15.3.0` @ `a50b0bfce8e8`) — the module inventory did not change, and restamping the version
without re-deriving it would be a false claim.

## Network dependency
Only the ERA5 retrieval (§2) and the ERA5-grid GIS export (§9) need the Copernicus CDS. Their
outputs are shipped in `cache/`, so `run_all.sh` is fully offline. The GWA / DEM / landcover terrain
layers are honestly **blocked offline** (external rasters absent) — flagged, not fabricated.

## Coverage of the module universe
Of the 294 source modules, this run fires the ~110 feasibility-relevant ones (finance spine, wind/GIS
stack, MC, sensitivity, optimizer, grid, emitters). The rest are out of scope for a wind feasibility
(web-service #788, BESS track, CI/tooling, legacy) — see `report/MODULE_CATALOG.md` +
`report/FEASIBILITY_COVERAGE.md`.
