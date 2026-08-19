# HOW-TO — Reproduce the DutchBay 150 MW Wind Feasibility Offline

Every process, script and command used to produce the **full-stack** DutchBay wind feasibility,
so it can be regenerated **offline with only the repo `.venv`**. One-shot: `bash run_all.sh`.
This file is the step-by-step manual behind that orchestrator.

- **Engine:** DutchBay EPC model, `v15.3.1`, main @ `7e64d33` (incl. F5-01 COD-aligned operating FX, #1034/#1038).
- **Canonical scenario:** `scenarios/dutchbay_lendercase_2025Q4.yaml` (the 5th-gen canon).
- **Golden numbers (must reproduce):** project_irr `-0.001166233356501311` · equity_irr `−0.07853839579881527` · min_dscr `1.3` · project_npv `−$91.81 M`.
- **Architecture fact that drives this kit:** `run_full_pipeline_v14.py` computes production from `project.capacity_factor` and reads the **committed** `resource.aep_summary_path`; it does **not** re-run the wind/GIS/MC/sensitivity/grid modules. Those are fired **separately** here.

---

## 0. Prerequisites (one-time)

```bash
cd ~/Downloads/dutchbay-epc-model
python3.12 -m venv .venv                       # if not present
.venv/bin/pip install -r requirements.txt      # the pinned lock
.venv/bin/pip install -e '.[dev,feasibility]'  # everything run_all.sh needs, in one line
```

The `feasibility` extra composes wind (ERA5 → Weibull → PyWake), micrositing
(TopFarm), gis (rasterio/shapely), report (WeasyPrint) and adds mistune + SALib.

The `feasibility` extra now includes **`[grid]`** too (pandapower / andes /
opendssdirect), so every `run_all.sh` step — including the §7 grid screen — runs
from one environment.

That was not possible before the **Python 3.12 baseline migration**: pandapower's
scipy pin was irreconcilable with the lock on 3.11 (`pandapower==3.3.0` wanted
`scipy~=1.15`; 3.5.4 wants `<1.17` there), so installing it alongside `[dev]`
silently downgraded scipy off the lock and broke the mypy gate's stubs. On 3.12
pandapower 3.5.x wants `scipy~=1.18`, the lock pins `scipy==1.18.0`, and the three
resolve together cleanly. Effect: `tests/grid/` went from 576 passed / 19 skipped
to **595 passed / 0 skipped**.

**Python 3.12 is the qualified baseline** (`requires-python = ">=3.12"`; later minor
versions require their own compatibility gate before adoption).
Everything below uses `.venv/bin/python`. **No network is required** — the two online steps
(ERA5 retrieval, ERA5-grid GIS export) ship their results in `cache/` (§2, §9).

Optional online refresh needs a Copernicus CDS token in `~/.cdsapirc`.

---

## 1. Canon + baseline (finance)

```bash
.venv/bin/python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml \
    validation_mode=strict write_artifacts=true run_scoped=true export_dir=_run_out/canon
```
Assert `kpis.json` matches the golden numbers above (byte-identical to 1e-9). If it diverges,
STOP — the environment differs; do not proceed.

**Baseline the long way** — prove the full `bankable_aep` chain reproduces the committed AEP:
```python
from analytics.wind.aep_summary_builder import build_aep_summary_from_config
import yaml
s = build_aep_summary_from_config(yaml.safe_load(open("scenarios/dutchbay_lendercase_2025Q4.yaml")))
# → net_site_aep_gwh 464.36, capacity_factor 0.3322  (= committed 464.3 GWh / 0.332)
```

---

## 2. Wind provenance — fresh AEP + tornado + micro-siting + ERA5 climate/rose/trend

```bash
.venv/bin/python feasibility_reproduce/lib/wind_provenance.py
```
Runs offline:
- **fresh bankable AEP** — `analytics.wind.aep_summary_builder.build_aep_summary_from_config` → net P50 464.36 GWh, P75 432.8, P90 404.4, CF 0.3322, loss stack 14.49 %.
- **AEP tornado** — `analytics.wind.aep_tornado.tornado_from_config` → wind-speed bias ±5 % = ±20.5 % (dominant), power-curve −16 %, shear ±6.6 %, losses ±6.4 %.
- **micro-siting** — `wind_resource.layout_optimizer.optimize_layout` (DTU TopFarm on PyWake), baseline-polish → **+~1 % AEP** candidate (551.0 → ~558 GWh). Use `use_smart_start=False` (a smart-start reseed can land *below* baseline — a misleading negative uplift).

**ERA5 climate/rose/trend (cached; a fresh fetch is online).** The kit ships the computed ARCO
result in `cache/era5_arco_result.json` (mean 7.46 m/s 20-yr; prevailing **210° SW**; Mann-Kendall
**p = 0.0047** secular-stilling). To re-fetch (online, needs `~/.cdsapirc`):
```bash
ERA5_REQUEST_CONFIG=feasibility_reproduce/cache/era5_request_dutchbay.yaml \
    .venv/bin/python -m wind_resource.era5_retrieval > cache/era5_arco_result.json
```
⚠️ Multi-year ERA5 MUST use this ARCO single-point timeseries module; the *gridded* fetcher
(`scripts/run_wind_analysis_v14.py`) is rejected by CDS ("cost limits exceeded") for 20 years.

---

## 3. Scenario suite (8) — the returns range

```bash
for s in basecase equitycase optimistic pessimistic capex_sinohydro_lean \
         capex_eia_prudent hybrid_windsolar solar_only; do
  .venv/bin/python run_full_pipeline_v14.py config=scenarios/dutchbay_${s}_2025Q4.yaml \
      validation_mode=strict write_artifacts=true run_scoped=true export_dir=_run_out/suite/$s
done
```
→ equity IRR −9.44 % (EIA-prudent) … +4.90 % (optimistic); **every scenario NPV-negative**.

---

## 4. Monte-Carlo (2,500 trials)

```bash
.venv/bin/python feasibility_reproduce/lib/mc_run.py 2500 _run_out/mc
```
→ equity IRR P10/P50/P90 = −13.0 / −9.1 / −5.0 %; project NPV negative in 100 % of trials;
min-DSCR ≥ 1.217. 2,500 converges to within ~0.1 pp of a full 100k run.
**Gotcha:** the driver does `logging.disable(WARNING)` to stop the per-trial debt-INFO stdout
flood (~1.25 GB at 100k). **Never** `os.setsid()`/`SIG_IGN`-detach the process.

---

## 5. Global sensitivity (Sobol + PAWN + Morris)

```bash
.venv/bin/python feasibility_reproduce/lib/run_global_sa.py
```
`analytics.sensitivity.global_sa.run_sobol(n=512)` / `run_morris(n_trajectories=32)` /
`run_pawn(n=1024)`. → equity-IRR Sobol total-order: **tariff 0.47 (dominant)** > capex 0.19 > fx 0.12.

---

## 6. Capital-structure optimizer

```bash
.venv/bin/python analytics/cli/cli_capital_structure_optimize_hydra.py \
    config=scenarios/dutchbay_lendercase_2025Q4.yaml mode=debt_mix objective_key=equity_irr direction=max
.venv/bin/python analytics/cli/cli_capital_structure_optimize_hydra.py \
    config=scenarios/dutchbay_lendercase_2025Q4.yaml mode=capex_contingency objective_key=equity_irr direction=max \
    base_capex_usd=157206000
```
→ 36 debt-mix candidates, **all negative**; best (DFI 40 / USD 60) −6.21 %.

⚠️ `mode=capex_contingency` additionally requires `base_capex_usd=157206000`
(`capex.usd_total` 159.6M less the 2.394M contingency line) — the CLI raises
`ValueError` without it.

---

## 7. Grid screen (advisory, KPI-neutral)

The lender scenario keeps `grid.study_enabled: false`. `cache/lender_gridon.yaml` is a copy with it
flipped **true** (KPI-neutral — finance stays byte-identical):
```bash
.venv/bin/python run_full_pipeline_v14.py config=feasibility_reproduce/cache/lender_gridon.yaml \
    +emit_grid_screen=true write_artifacts=true run_scoped=true export_dir=_run_out/grid
```
→ SCR@POC 0.94 (weak, pandapower IEC-60909, screening-only), RMS ride-through 3 cases, IEEE-519.
Needs the `[grid]` extra (pandapower/andes/opendssdirect). Fixed by #930 (ride-through kwarg).

---

## 8. Report emitters

The pipeline reads exactly five emit flags. `emit_capital_risk_report` + `emit_executive_workbook`
are in the base conf (plain override); `emit_interaction_grid` / `emit_tech_comparison` /
`emit_grid_screen` are NOT, so they need Hydra `+append`:
```bash
# capital-risk (2000-trial MC report + npv_distribution PNG) + executive workbook
.venv/bin/python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml \
    emit_capital_risk_report=true capital_risk_report.n_trials=2000 emit_executive_workbook=true \
    write_artifacts=true run_scoped=true export_dir=_run_out/emitters/core
# tech-comparison (needs an explicit scenarios list)
.venv/bin/python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml \
    +emit_tech_comparison=true '+tech_comparison.scenarios=[{label:Wind,config:scenarios/dutchbay_lendercase_2025Q4.yaml},{label:HybridWindSolar,config:scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml},{label:SolarOnly,config:scenarios/dutchbay_solar_only_2025Q4.yaml}]' \
    write_artifacts=true run_scoped=true export_dir=_run_out/emitters/tech
# interaction-grid (needs a scenario declaring an interaction_grid block — shipped in cache/)
.venv/bin/python run_full_pipeline_v14.py config=feasibility_reproduce/cache/scenario_with_interaction_grid.yaml \
    +emit_interaction_grid=true write_artifacts=true run_scoped=true export_dir=_run_out/emitters/interaction
```

---

## 9. GIS (cached GeoTIFFs + boundary_clip)

The ERA5-grid export (WS150/CF/AEP GeoTIFFs) is online; its output is cached in `cache/gis/`.
`boundary_clip` (fixed by #929 — no more segfault) runs offline on a cached raster:
```python
import analytics.gis.boundary_clip as bc
poly=[[(79.73,8.25),(79.77,8.25),(79.77,8.29),(79.73,8.29),(79.73,8.25)]]
bc.clip_to_polygon("feasibility_reproduce/cache/gis/dutchbay_fine_ws150_mean.tif", poly, out_path="_run_out/gis/ws150_clipped.tif")
```
Online refresh: `GIS_EXPORT_CONFIG=wind_resource/config/gis_export_dutchbay.yaml .venv/bin/python -m analytics.gis.gis_export`.
The **GWA / Copernicus-DEM / ESA-WorldCover** terrain-suitability layers (`gwa_ingest`, `dem_ingest`,
`landcover_roughness`, `rix`, `mcdm_suitability`) need those external rasters and stay **honestly
blocked** offline — documented, not fabricated.

---

## 10. Build the deliverable PDFs (Acrobat-safe)

```bash
.venv/bin/python feasibility_reproduce/lib/build_study_pdf.py                 # 11-pp study
.venv/bin/python feasibility_reproduce/lib/build_md_pdf.py report/FEASIBILITY_COVERAGE.md report/DutchBay_Feasibility_Module_Coverage.pdf portrait  "Coverage"
.venv/bin/python feasibility_reproduce/lib/build_md_pdf.py report/MODULE_CATALOG.md        report/DutchBay_Module_Catalog.pdf                landscape "Catalog"
```
The builders swap emoji-only glyphs (🟢🟡⚪⭐⚠️) for CSS-colored `●○★▲` so weasyprint does **not**
embed the Apple Color Emoji font (which Adobe Acrobat cannot open).

---

## Verifying a run
Compare your `_run_out/**` outputs against the shipped `cache/expected/*.json` (MC percentiles,
Sobol indices, optimizer summary, grid screen, wind results). The finance canon must be byte-identical;
the MC/sensitivity converge to within sampling noise (seed 42 → deterministic).
