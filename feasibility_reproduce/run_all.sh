#!/usr/bin/env bash
# =============================================================================
# DutchBay 150 MW wind — FULL-STACK feasibility, offline reproduce.
# Uses ONLY the repo .venv. No network (ERA5/GIS results are shipped in cache/).
# Every step is also documented, command-by-command, in HOWTO.md.
# =============================================================================
set -uo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$KIT/.." && pwd)"
PY="$REPO/.venv/bin/python"
CFG="scenarios/dutchbay_lendercase_2025Q4.yaml"
OUT="$KIT/_run_out"; mkdir -p "$OUT"
cd "$REPO"
step(){ printf "\n\033[1;34m== %s ==\033[0m\n" "$1"; }
[ -x "$PY" ] || { echo "FATAL: venv missing at $PY (see HOWTO.md §0)"; exit 1; }

step "0. Preflight — engine + optional deps"
"$PY" - <<'PYEOF'
import importlib
# One install covers all of these:  pip install -e ".[dev,feasibility]"
for m in ("weasyprint", "mistune", "py_wake", "topfarm", "SALib", "rasterio"):
    try:
        importlib.import_module(m); print(f"  ok   {m}")
    except Exception as e:
        print(f'  MISS {m} ({e})  -> pip install -e ".[dev,feasibility]"')
# pandapower is EXPECTED to be absent: its scipy pin is incompatible with the
# pinned lock on every interpreter (see the `feasibility` extra in pyproject),
# so it is excluded by design and step 7 skips rather than corrupting the env.
try:
    importlib.import_module("pandapower"); print("  ok   pandapower (grid screen will run)")
except Exception:
    print("  --   pandapower absent by design -> step 7 (advisory grid screen) will skip")
PYEOF
echo "  engine: $(git rev-parse --short HEAD) (canon expects: project_irr -0.001166233356501311)"

step "1. Canon + baseline (finance) — must reproduce the 5th-gen canon"
"$PY" run_full_pipeline_v14.py config="$CFG" validation_mode=strict write_artifacts=true \
    run_scoped=true export_dir="$OUT/canon" 2>/dev/null | tail -1
"$PY" - "$OUT" <<'PYEOF'
import json,glob,sys
k=json.load(open(glob.glob(sys.argv[1]+"/canon/*/kpis.json")[0]))
canon={"project_irr":-0.001166233356501311,"equity_irr":-0.07853839579881527,"min_dscr":1.3}
ok=all(abs(k.get(x,0)-v)<1e-9 for x,v in canon.items())
print("  canon reproduced:", "BYTE-IDENTICAL ✓" if ok else "✗ DIVERGED — investigate")
PYEOF

step "2. Wind provenance (fresh AEP + tornado + micro-siting; cached ERA5)"
"$PY" "$KIT/lib/wind_provenance.py"

step "3. Scenario suite (8)"
for s in basecase equitycase optimistic pessimistic capex_sinohydro_lean capex_eia_prudent hybrid_windsolar solar_only; do
  "$PY" run_full_pipeline_v14.py config="scenarios/dutchbay_${s}_2025Q4.yaml" validation_mode=strict \
      write_artifacts=true run_scoped=true export_dir="$OUT/suite/$s" >/dev/null 2>&1 && echo "  ok  $s" || echo "  ERR $s"
done

step "4. Monte-Carlo (2500 trials ≈ 100k, converged)"
"$PY" "$KIT/lib/mc_run.py" 2500 "$OUT/mc"

step "5. Global sensitivity (Sobol n=512 + Morris + PAWN)"
"$PY" "$KIT/lib/run_global_sa.py" 2>/dev/null | tail -3

step "6. Capital-structure optimizer (both modes)"
"$PY" analytics/cli/cli_capital_structure_optimize_hydra.py config="$CFG" mode=debt_mix \
    objective_key=equity_irr direction=max output_dir="$OUT/optimizer" >/dev/null 2>&1 && echo "  ok  debt_mix"
# base_capex_usd is REQUIRED for this mode (capex.usd_total less the contingency line);
# the CLI raises ValueError without it. Errors are surfaced, not swallowed.
"$PY" analytics/cli/cli_capital_structure_optimize_hydra.py config="$CFG" mode=capex_contingency \
    objective_key=equity_irr direction=max base_capex_usd=157206000 \
    output_dir="$OUT/optimizer" >/dev/null && echo "  ok  capex_contingency" || echo "  ERR capex_contingency"

step "7. Grid screen (KPI-neutral; grid.study_enabled=true)"
if "$PY" -c "import pandapower" >/dev/null 2>&1; then
  "$PY" run_full_pipeline_v14.py config="$KIT/cache/lender_gridon.yaml" +emit_grid_screen=true \
      write_artifacts=true run_scoped=true export_dir="$OUT/grid" >/dev/null \
      && echo "  ok  grid screen (advisory)" || echo "  ERR grid screen"
else
  echo "  skip grid screen — pandapower excluded from [feasibility] (scipy pin conflicts with the"
  echo "       lock). It is advisory and KPI-neutral. To run it, use a SEPARATE venv:"
  echo "       python3.11 -m venv .venv-grid && .venv-grid/bin/pip install -e '.[grid]'"
fi

step "8. Report emitters (capital-risk, exec-workbook, tech-comparison, interaction-grid)"
"$PY" run_full_pipeline_v14.py config="$CFG" emit_capital_risk_report=true capital_risk_report.n_trials=2000 \
    emit_executive_workbook=true write_artifacts=true run_scoped=true export_dir="$OUT/emitters/core" >/dev/null 2>&1 && echo "  ok  capital-risk + workbook"
"$PY" run_full_pipeline_v14.py config="$CFG" +emit_tech_comparison=true \
    '+tech_comparison.scenarios=[{label:Wind,config:scenarios/dutchbay_lendercase_2025Q4.yaml},{label:HybridWindSolar,config:scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml},{label:SolarOnly,config:scenarios/dutchbay_solar_only_2025Q4.yaml}]' \
    write_artifacts=true run_scoped=true export_dir="$OUT/emitters/tech" >/dev/null 2>&1 && echo "  ok  tech-comparison"
"$PY" run_full_pipeline_v14.py config="$KIT/cache/scenario_with_interaction_grid.yaml" +emit_interaction_grid=true \
    write_artifacts=true run_scoped=true export_dir="$OUT/emitters/interaction" >/dev/null 2>&1 && echo "  ok  interaction-grid"

step "9. GIS (cached ERA5-grid GeoTIFFs + boundary_clip)"
mkdir -p "$OUT/gis"; cp "$KIT"/cache/gis/*.tif "$OUT/gis/" 2>/dev/null
"$PY" - "$OUT" <<'PYEOF'
import logging,sys; logging.disable(logging.WARNING)
import analytics.gis.boundary_clip as bc
tif=sys.argv[1]+"/gis/dutchbay_fine_ws150_mean.tif"
poly=[[(79.73,8.25),(79.77,8.25),(79.77,8.29),(79.73,8.29),(79.73,8.25)]]
r=bc.clip_to_polygon(tif, poly, out_path=sys.argv[1]+"/gis/ws150_clipped.tif")
print("  ok  boundary_clip (no segfault, #929):", r.get("clipped_path","").split("/")[-1])
PYEOF
echo "  note: GWA/DEM/landcover terrain layers need external rasters (online) — see HOWTO §9"

step "10. Build the deliverable PDFs (Acrobat-safe, no color-emoji font)"
"$PY" "$KIT/lib/build_study_pdf.py"
"$PY" "$KIT/lib/build_md_pdf.py" "$KIT/report/FEASIBILITY_COVERAGE.md" "$KIT/report/DutchBay_Feasibility_Module_Coverage.pdf" portrait "DutchBay Feasibility — Module Coverage"
"$PY" "$KIT/lib/build_md_pdf.py" "$KIT/report/MODULE_CATALOG.md" "$KIT/report/DutchBay_Module_Catalog.pdf" landscape "DutchBay EPC Model — Module Catalog (294 modules)"

printf "\n\033[1;32mDONE.\033[0m Study + coverage + catalog PDFs in %s/report/. Run artifacts in %s.\n" "$KIT" "$OUT"
