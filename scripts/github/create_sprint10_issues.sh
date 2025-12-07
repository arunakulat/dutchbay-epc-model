#!/usr/bin/env zsh
set -euo pipefail

# Milestone configuration – must exist in GitHub (adjust the name if needed)
MILESTONE="Sprint 10 – Wind → AEP → EPC Integration"

# Map label → color (GitHub hex without #)
typeset -A LABEL_COLORS
LABEL_COLORS=(
  P0          "d73a4a"   # red
  P1          "fbca04"   # yellow
  P2          "0e8a16"   # green
  AEP         "1d76db"   # blue
  Wind        "5319e7"
  OEM         "cfd3d7"
  v14         "0052cc"
  loader      "5319e7"
  schema_guard "5319e7"
  Finance     "0e8a16"
  provenance  "5319e7"
  DFI         "bfd4f2"
  audit       "c2e0c6"
  GIS         "0366d6"
  NetCDF      "d876e3"
  Refactor    "c5def5"
  Raster      "0e8a16"
  QGIS        "0e8a16"
  Boundaries  "0e8a16"
  Analytics   "1d76db"
  Losses      "1d76db"
  MonteCarlo  "1d76db"
  Sensitivity "1d76db"
  DataLake    "cfd3d7"
  Cleanup     "cfd3d7"
  Maintenance "cfd3d7"
  Docs        "cfd3d7"
)

ensure_label() {
  local label="$1"
  local color="${LABEL_COLORS[$label]:-cfd3d7}"
  # Try to create; if it already exists, ignore the error
  if ! gh label list --limit 200 | cut -f1 | grep -qx "$label"; then
    echo "Creating missing label: $label"
    gh label create "$label" --color "$color" --description "Auto-created for Sprint 10" || true
  fi
}

# Helper for issue creation
create_issue() {
  local title="$1"
  local body="$2"
  local labels_csv="$3"

  local labels=("${(@s:,:)labels_csv}")

  # Ensure all labels exist
  for l in "${labels[@]}"; do
    ensure_label "$l"
  done

  local args=()
  for l in "${labels[@]}"; do
    args+=("--label" "$l")
  done

  gh issue create \
    --title "$title" \
    --body "$body" \
    --milestone "$MILESTONE" \
    "${args[@]}"
}

echo "Creating Sprint 10 issues in CURRENT repo (milestone: $MILESTONE)..."


# ─────────────────────────────
# P0 – OEM curve integration
# ─────────────────────────────
create_issue \
  "Sprint 10 – Integrate OEM Envision power curve into AEP pipeline" \
  $'P0 – Replace the placeholder NREL 5MW curve with the actual Envision OEM curve and regenerate AEP.\n\n- Parse Envision 5–6 MW power curve (CSV/XLS/PDF OCR) into a canonical {wind_speed_ms, power_kw} table.\n- Implement cubic/monotonic interpolation helper.\n- Swap placeholder NREL curve → OEM curve in the AEP pipeline.\n- Regenerate the 3×3 grid stats and site AEP for 150m hub height.\n- Save outputs under Curated/GIS/DutchBay/AEP/OEM/ and update DataLake_Manifest_All.json with proper derived_from and checksums.\n- Produce OEM vs ECMWF/NREL comparison CSV + short summary for lenders.' \
  "P0,AEP,Wind,OEM,v14"

# ─────────────────────────────
# P0 – Resource loader for AEP summary
# ─────────────────────────────
create_issue \
  "Sprint 10 – Build EPC resource loader for AEP summary CSV" \
  $'P0 – Wire the DutchBay AEP summary CSV directly into the v14 pipeline.\n\n- Implement load_aep_from_summary() in the analytics/loader layer.\n- Read Curated/Finance/ModelInputs/DutchBay_AEP_Summary_for_EPCModel_v01.csv.\n- Normalize fields into internal config: capacity_factor, net_site_AEP_GWh, n_turbines, rated_power_kw, source_id, source_type.\n- Attach normalized block under config[\"resource\"][\"aep_normalized\"].\n- Add schema_guard tests to fail if CSV missing, malformed, or checksum mismatch vs DataLake_Manifest_All.json.\n- Ensure run_full_pipeline_v14 logs the AEP source_id for traceability.' \
  "P0,v14,loader,schema_guard,Finance"

# ─────────────────────────────
# P0 – Provenance enforcement
# ─────────────────────────────
create_issue \
  "Sprint 10 – Enforce AEP provenance chain in v14 outputs" \
  $'P0 – Make AEP provenance lender-grade and test-enforced.\n\n- Add provenance.aep block to v14 outputs (JSON/CSV/summary): aep_source_id, derived_from IDs.\n- Wire provenance to the Data Lake manifest entry (DB-AEP-SUM-… etc.).\n- Add tests that fail if AEP source_id in config does not exist in the manifest.\n- Add tests that flag placeholder source_type when an OEM curve is available.\n- Document the provenance pattern in the developer docs.' \
  "P0,provenance,DFI,audit,v14"

# ─────────────────────────────
# P0 – Formal NetCDF → ws150 → stats pipeline
# ─────────────────────────────
create_issue \
  "Sprint 10 – Formalize NetCDF → ws150 → stats pipeline" \
  $'P0 – Turn the ad-hoc ECMWF ws150 derivation into a reusable GIS pipeline.\n\n- Implement gis_netcdf_profile() helper to capture CRS, bounds, dims, variables, time range.\n- Implement ws150_from_10_100(ds) with alpha estimation and clipping (0.0–0.5).\n- Implement a generic grid_stats helper to produce per-cell mean/std tables.\n- Refactor current ws150 / stats scripts to use these helpers.\n- Emit curated metadata JSON for each stats CSV and register in the manifest.' \
  "P0,GIS,Wind,NetCDF,Refactor"

# ─────────────────────────────
# P1 – GeoTIFF exports
# ─────────────────────────────
create_issue \
  "Sprint 10 – Export WS150 / CF / AEP GeoTIFFs for QGIS" \
  $'P1 – Make Dutch Bay wind and AEP layers GIS-ready.\n\n- Rasterize the 3×3 grids to GeoTIFFs: ws150_mean, capacity_factor, AEP_per_turbine.\n- Set CRS to EPSG:4326 and correct georeferencing.\n- Save under Curated/GIS/DutchBay/Rasters/.\n- Add entries to DataLake_Manifest_All.json with gis.extent, gis.resolution and variables.\n- Smoke-test loading in QGIS.' \
  "P1,GIS,Raster,QGIS"

# ─────────────────────────────
# P1 – Project polygon + clipping
# ─────────────────────────────
create_issue \
  "Sprint 10 – Add Dutch Bay project polygon and clip wind/AEP" \
  $'P1 – Introduce site boundary support and clipped wind/AEP metrics.\n\n- Store DutchBay_ProjectArea.geojson in Curated/GIS/Boundaries/.\n- Implement clip_to_polygon() utility for rasters/grids.\n- Compute ws150, capacity_factor and AEP for the clipped project polygon.\n- Save clipped stats CSVs and register in the manifest.\n- Add basic tests that clipped stats differ from full 3×3 domain where expected.' \
  "P1,GIS,Boundaries,Analytics"

# ─────────────────────────────
# P1 – Standardize GIS → EPC schema
# ─────────────────────────────
create_issue \
  "Sprint 10 – Standardize GIS → EPC wind interface schema" \
  $'P1 – Define a stable schema for passing wind/AEP from GIS to EPC model.\n\n- Define a resource.wind schema: ws150_mean_ms, ws150_std_ms, capacity_factor, aep_gwh, source_id, source_type.\n- Add schema_guard rules and tests for the new block.\n- Update developer docs with an example snippet from dutchbay_lendercase_2025Q4.yaml.\n- Ensure cashflow/metrics modules only depend on the normalized schema, not raw CSVs.' \
  "P1,schema,v14,Analytics"

# ─────────────────────────────
# P1 – Losses model
# ─────────────────────────────
create_issue \
  "Sprint 10 – Implement AEP losses model (wake, availability, electrical)" \
  $'P1 – Integrate a simple but explicit losses model on top of gross AEP.\n\n- Add a resource.losses block (wake, electrical, availability, curtailment, other).\n- Compute net_capacity_factor and net_site_AEP_GWh from gross values + losses.\n- Expose losses and net AEP in the lender KPI outputs / summary JSON.\n- Add tests covering at least two loss scenarios (low / high) for the same gross AEP.' \
  "P1,AEP,Losses,Finance"

# ─────────────────────────────
# P2 – Monte Carlo AEP
# ─────────────────────────────
create_issue \
  "Sprint 10 – Monte Carlo AEP from ECMWF-derived Weibull" \
  $'P2 – Provide a simple Monte Carlo AEP distribution for Dutch Bay.\n\n- Fit Weibull parameters A,k for ws150 from ECMWF at each grid cell.\n- Generate synthetic wind years and run OEM curve to compute AEP.\n- Derive P50, P75, P90, P99 and write a DutchBay_AEP_MC_Summary.csv.\n- Add a fast regression test with reduced sample size.' \
  "P2,Wind,MonteCarlo,Analytics"

# ─────────────────────────────
# P2 – AEP tornado sensitivity
# ─────────────────────────────
create_issue \
  "Sprint 10 – AEP tornado sensitivities (wind, losses, curve)" \
  $'P2 – Show lenders how sensitive AEP is to key assumptions.\n\n- Implement AEP sensitivity runs for: ±wind speed bias, ±shear exponent, ±losses, OEM vs NREL curve.\n- Write results to a tornado-ready CSV and optionally generate a tornado plot.\n- Add a basic test to ensure the pipeline runs and outputs all expected metrics.' \
  "P2,Analytics,Sensitivity,AEP"

# ─────────────────────────────
# P2 – Data lake cleanup
# ─────────────────────────────
create_issue \
  "Sprint 10 – Data lake cleanup and archive of legacy wind/model files" \
  $'P2 – Tidy up the DutchBay Data Lake around wind and AEP.\n\n- Identify duplicate or superseded cashflow_v14 and wind stats files.\n- Move obsolete artifacts into an Archive zone with preserved manifest lineage.\n- Ensure current pipelines and manifests refer only to v10+ canonical assets.\n- Document the cleanup in a short CHANGELOG entry.' \
  "P2,DataLake,Cleanup,Maintenance"

# ─────────────────────────────
# P2 – Wind → AEP chain-of-custody docs
# ─────────────────────────────
create_issue \
  "Sprint 10 – Document Wind → AEP chain of custody for lenders" \
  $'P2 – Produce an annex documenting the full wind → AEP data chain.\n\n- Describe NetCDF source, ws150 derivation, shear handling and clipping.\n- Document the OEM power curve source and validation.\n- Explain the AEP calculation, losses, and the linkage to DutchBay_EPC_Model.\n- Cross-reference DataLake_Manifest_All.json IDs and checksums.\n- Export to a lender-ready PDF/Markdown annex.' \
  "P2,Docs,DFI,Audit"

echo "Done. Sprint 10 issues created (assuming gh CLI is configured and milestone exists)."
