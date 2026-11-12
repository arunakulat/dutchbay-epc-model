#!/usr/bin/env bash
# DutchBay EPC Model: November 2026 validation/reproduction orchestrator.
# Work item: https://github.com/arunakulat/dutchbay-epc-model/issues/1616
# Supplements the historical August run_all.sh; never overwrites it.
# No obsolete financial golden numbers. No confidential source data in Git.
# Full profile validates the current codebase and explicitly runs Blue Whale modules;
# none of its outcomes certify land, EIA, grid approval, turbine or lender bankability.
set -Eeuo pipefail
umask 077

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$KIT/.." && pwd -P)"
PROFILE=full; JOBS=4; REQUIRE_PRIVATE=0; ONLINE_SECURITY=0; STUDY=0; PLAN=0; OUT=""
MIN_FREE_GIB="${DUTCHBAY_NOV26_MIN_FREE_GIB:-8}"

usage() {
  cat <<'HELP'
Usage: bash feasibility_reproduce/run_all_NOV26.sh [options]
 --profile full|quick      full default; quick focused smoke
 --jobs N                  pytest workers; default 4, never auto
 --out DIR                 output outside the Git checkout
 --require-private         missing confidential inputs cause exit 3
 --online-security         run network-dependent make security (otherwise offline)
 --study                   run current full analytical-study extensions (very costly)
 --study-quick             run smoke-sized analytical-study extensions
 --plan                    show phases without executing
 -h, --help                show help

Private inputs, when available (kept outside repository):
 BLUE_WHALE_POWER_CURVE_CSV
 DUTCHBAY_MET_MAST_617725_SOURCE
 DUTCHBAY_NASA_POWER_DIR
 BLUE_WHALE_PRIVATE_ANCHORS_PATH

Outputs: receipt.tsv, manifest.txt, source inventory, scenario artifacts, JSON
summaries, JUnit XML and coverage data. The historical August feasibility
report is NOT automatically regenerated: it uses superseded 15-turbine figures.
HELP
}
die() { printf 'FATAL: %s\n' "$*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --profile) (($# >= 2)) || die "--profile requires a value"; PROFILE="$2"; shift 2 ;;
    --jobs) (($# >= 2)) || die "--jobs requires a value"; JOBS="$2"; shift 2 ;;
    --out) (($# >= 2)) || die "--out requires a value"; OUT="$2"; shift 2 ;;
    --require-private) REQUIRE_PRIVATE=1; shift ;;
    --online-security) ONLINE_SECURITY=1; shift ;;
    --study) STUDY=1; shift ;;
    --study-quick) STUDY=2; shift ;;
    --plan) PLAN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1";;
  esac
done
[[ "$PROFILE" == full || "$PROFILE" == quick ]] || die "profile must be full or quick"
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || die "jobs must be a positive integer"
[[ "$MIN_FREE_GIB" =~ ^[1-9][0-9]*$ ]] || die "MIN_FREE_GIB must be a positive integer"
if ((STUDY == 1 && MIN_FREE_GIB < 20)); then MIN_FREE_GIB=20; fi
if ((PLAN)); then
  cat <<'PLAN'
0. Verify checkout, pinned Python 3.12 environment, disk and source inventory.
1. Validate rules and independent current 14-turbine financial oracles.
2. Run targeted Blue Whale wind, GIS, solar, BESS and finance tests.
3. Reproduce current 14-turbine wake proxy, Blue Whale hourly dispatch.
4. Execute current DutchBay lender and separate Blue Whale financial scenarios.
5. [full] lint, mypy, entire regression suite with 95% six-package coverage.
6. [full] grid, stochastic and report qualification tests.
7. [full] Blue Whale unit, project, fixed-BESS Monte Carlo sizing CLIs.
8. Re-run private wind siting, met-mast transfer and CAPEX blend if supplied.
9. [opt-in] Current scenario suite, wind/AEP, Monte Carlo, global sensitivity,
             capital optimizer and report emitters (--study or --study-quick).
10. [opt-in] Online security auditing.
No PDF from the stale August 2026 kit is certified by this script.
PLAN
  exit 0
fi

cd "$REPO"
[[ -f requirements.txt && -f dutchbay_environment.py ]] || die "wrong checkout: $REPO"
command -v git >/dev/null || die "git missing"
command -v make >/dev/null || die "make missing"
SHA="$(git rev-parse HEAD)"; SHORT="${SHA:0:12}"
BRANCH="$(git branch --show-current)"
TRACKING="$(git rev-parse origin/main 2>/dev/null || printf unavailable)"
OUT="${OUT:-$HOME/Downloads/DutchBay_NOV26_runs/${SHORT}_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd -P)"
case "$OUT/" in "$REPO/"*) die "--out must be outside checkout";; esac
VENV="${DUTCHBAY_VENV:-$REPO/.venv}"
[[ "$VENV" == /* && -x "$VENV/bin/python" ]] ||
  die "configure governed Python with an absolute DUTCHBAY_VENV (or local .venv)"
PY="$VENV/bin/python"
export DUTCHBAY_VENV="$VENV"
export DUTCHBAY_FLOW_RULESET_CSV="$REPO/go_with_the_flow_rules_v3_0_clean.csv"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
export PATH="$VENV/bin:$PATH"
export COVERAGE_FILE="$OUT/.coverage"
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 12)' ||
  die "Python 3.12 required"
FREE_KIB="$(df -Pk "$OUT" | awk 'END {print $4}')"
((FREE_KIB >= MIN_FREE_GIB * 1024 * 1024)) ||
  die "free space below ${MIN_FREE_GIB} GiB: do not run large simulations"
if ((REQUIRE_PRIVATE)); then
  [[ -f "${BLUE_WHALE_POWER_CURVE_CSV:-/nonexistent}" ]] ||
    die "--require-private needs BLUE_WHALE_POWER_CURVE_CSV"
  [[ -f "${DUTCHBAY_MET_MAST_617725_SOURCE:-/nonexistent}" ]] ||
    die "--require-private needs DUTCHBAY_MET_MAST_617725_SOURCE"
  [[ -d "${DUTCHBAY_NASA_POWER_DIR:-/nonexistent}" ]] ||
    die "--require-private needs DUTCHBAY_NASA_POWER_DIR"
  [[ -f "${BLUE_WHALE_PRIVATE_ANCHORS_PATH:-/nonexistent}" ]] ||
    die "--require-private needs BLUE_WHALE_PRIVATE_ANCHORS_PATH"
fi

RECEIPT="$OUT/receipt.tsv"
printf 'stage\tstatus\tseconds\tnote\n' > "$RECEIPT"
printf 'repo=%s\ncommit=%s\nbranch=%s\nlocal_origin_main=%s\nprofile=%s\njobs=%s\nvenv=%s\nout=%s\n' \
  "$REPO" "$SHA" "${BRANCH:-detached}" "$TRACKING" "$PROFILE" "$JOBS" "$VENV" "$OUT" \
  > "$OUT/manifest.txt"
printf 'scope=software_only_not_external_bankability\n' >> "$OUT/manifest.txt"
printf 'validation_profile=%s\n' "$PROFILE" >> "$OUT/manifest.txt"
git ls-files '*.py' | LC_ALL=C sort > "$OUT/python_source_inventory.txt"
printf 'tracked_python_files=%s\n' "$(wc -l < "$OUT/python_source_inventory.txt" | tr -d ' ')" >> "$OUT/manifest.txt"
printf '\nDutchBay NOV26 | %s | %s | %s\n' "$SHORT" "$PROFILE" "$OUT"

BLOCKED=0
run_step() {
  local name="$1" start rc log elapsed
  shift; start=$SECONDS; log="$(mktemp "$OUT/.step.XXXXXXXX")"
  printf '\n== %s ==\n' "$name"
  if "$@" > "$log" 2>&1; then
    elapsed=$((SECONDS - start))
    printf '%s\tPASS\t%s\t-\n' "$name" "$elapsed" >> "$RECEIPT"
    printf 'PASS (%ss) %s\n' "$elapsed" "$name"
    rm -f "$log"
  else
    rc=$?; elapsed=$((SECONDS - start))
    printf '%s\tFAIL\t%s\texit_%s\n' "$name" "$elapsed" "$rc" >> "$RECEIPT"
    mv "$log" "$OUT/last_failure.log"
    tail -n 75 "$OUT/last_failure.log" >&2
    printf 'FAIL (%ss): %s, exit %s; log: %s\n' "$elapsed" "$name" "$rc" "$OUT/last_failure.log" >&2
    exit "$rc"
  fi
}
blocked_external() {
  BLOCKED=$((BLOCKED + 1))
  printf '%s\tBLOCKED_EXTERNAL\t0\t%s\n' "$1" "$2" >> "$RECEIPT"
  printf 'BLOCKED_EXTERNAL: %s — %s\n' "$1" "$2"
}
capture_json() {
  local target="$1"; shift
  "$@" > "$target" && "$PY" -m json.tool "$target" >/dev/null
}
scenario() {
  local slug="$1" cfg="$2"
  mkdir -p "$OUT/scenarios/$slug"
  "$PY" run_full_pipeline_v14.py "config=$cfg" validation_mode=strict \
    write_artifacts=true run_scoped=true "export_dir=$OUT/scenarios/$slug"
}
paths_exist() {
  local f
  for f in "$@"; do [[ -f "$f" ]] || { echo "missing: $f"; return 1; }; done
}
required=(
  scripts/run_dutchbay_wake_rebaseline_v14.py
  scripts/run_blue_whale_wind_siting_v14.py
  scripts/run_blue_whale_met_mast_transfer_v14.py
  scripts/run_blue_whale_solar_bess_v14.py
  scripts/run_blue_whale_pv_bess_sizing_v14.py
  scripts/run_blue_whale_capex_solar_resource_v14.py
  scenarios/dutchbay_lendercase_2025Q4.yaml
  scenarios/blue_whale_wind_lot5b_2026.yaml
  scenarios/blue_whale_solar_bess_lot5b_2026.yaml
  conf/dutchbay_wake_14_turbines.yaml tests/_canon.py
)
run_step "entrypoint-inventory" paths_exist "${required[@]}"
run_step "governed-environment" "$PY" dutchbay_environment.py
run_step "dependency-integrity" "$PY" -m pip check
run_step "GWTF-ruleset" "$PY" dutchbay_bootstrap_rules.py

run_step "current-14-turbine-oracles" "$PY" -m pytest -q \
  tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged \
  tests/finance/test_lendercase_expected_results.py \
  tests/wind/test_dutchbay_14_turbines.py
blue_tests=(
  tests/wind/test_blue_whale_wind_siting.py
  tests/wind/test_met_mast_transfer.py
  tests/wind/test_dutchbay_14_turbines.py
  tests/wind/test_wake_deficit_gap_1589.py
  tests/analytics/test_wake_counted_mask.py
  tests/solar/test_blue_whale_site_inputs.py
  tests/solar/test_pv_array_turbine_shading.py
  tests/solar/test_pv_bess_dispatch.py
  tests/solar/test_pv_bess_sizing.py
  tests/solar/test_solar_bess_project_sizing.py
  tests/finance/test_blue_whale_scenario_kpis.py
  tests/finance/test_tariff_indexation.py
  tests/finance/test_price_dates_1569.py
  tests/finance/test_opex_currency_split.py
  tests/gis/test_pv_array_layout.py
  tests/gis/test_shadow_flicker.py
)
run_step "blue-whale-focused-regression" "$PY" -m pytest -q -n "$JOBS" "${blue_tests[@]}"

run_step "dutchbay-14-wake-proxy" capture_json "$OUT/dutchbay_14_wake.json" \
  "$PY" scripts/run_dutchbay_wake_rebaseline_v14.py
run_step "blue-whale-solar-bess-dispatch" capture_json "$OUT/blue_whale_dispatch.json" \
  "$PY" scripts/run_blue_whale_solar_bess_v14.py
run_step "dutchbay-lendercase-finance" scenario lender scenarios/dutchbay_lendercase_2025Q4.yaml
run_step "blue-whale-wind-finance" scenario blue_whale_wind scenarios/blue_whale_wind_lot5b_2026.yaml
run_step "blue-whale-solar-bess-finance" scenario blue_whale_solar_bess scenarios/blue_whale_solar_bess_lot5b_2026.yaml

if [[ "$PROFILE" == full ]]; then
  run_step "ruff-black-isort" make lint
  run_step "mypy-typed-surface" make type
  run_step "full-pytest-six-package-95pct-coverage" env DUTCHBAY_TEST_MODE=full \
    "$PY" -m pytest -n "$JOBS" \
    --junitxml="$OUT/pytest_full.xml" \
    --cov=finance --cov=analytics --cov=wind_resource \
    --cov=api --cov=app --cov=solar_resource \
    --cov-report=term-missing --cov-fail-under=95
  run_step "grid-study" env DUTCHBAY_TEST_MODE=full "$PY" -m pytest \
    -n "$JOBS" -m grid --tb=short --junitxml="$OUT/pytest_grid.xml"
  run_step "stochastic-qualification" env DUTCHBAY_TEST_MODE=qualification \
    "$PY" -m pytest -n "$JOBS" -m stochastic_qualification \
    --tb=short --junitxml="$OUT/pytest_stochastic.xml"
  run_step "report-qualification" env DUTCHBAY_TEST_MODE=qualification \
    "$PY" -m pytest -n 2 tests/integration/test_lender_report_e2e.py \
    tests/integration/test_synthetic_qsts_finance_report.py \
    -m report_qualification --tb=short --junitxml="$OUT/pytest_report.xml"
  run_step "blue-whale-unit-monte-carlo" capture_json "$OUT/blue_whale_sizing_unit.json" \
    "$PY" scripts/run_blue_whale_pv_bess_sizing_v14.py
  run_step "blue-whale-project-monte-carlo" capture_json "$OUT/blue_whale_sizing_project.json" \
    "$PY" scripts/run_blue_whale_pv_bess_sizing_v14.py \
    --config-name blue_whale_solar_bess_project_sizing
  run_step "blue-whale-fixed-bess-monte-carlo" capture_json "$OUT/blue_whale_sizing_fixed.json" \
    "$PY" scripts/run_blue_whale_pv_bess_sizing_v14.py \
    --config-name blue_whale_solar_bess_fixed_bess_sizing
fi

# Optional historical-study capability replay against current files and current
# engine. These analytical outputs are NEW screening runs, NOT reproductions of
# the frozen August 2026 published KPI vector, PDF, or 294-module manifest.
# No fixed 15-turbine "goldens" are used; the 14-turbine oracle is tested above.
if ((STUDY)); then
  mkdir -p "$OUT/study/wind" "$OUT/study/mc" "$OUT/study/sa" "$OUT/study/optimizer"
  if ((STUDY == 2)); then
    study_trials=128
    sa_extra=(--quick)
  else
    study_trials=2500
    sa_extra=()
  fi
  printf 'study_status=screening_only_not_historical_reproduction\n' >> "$OUT/manifest.txt"
  for s in basecase equitycase optimistic pessimistic capex_sinohydro_lean \
           capex_eia_prudent hybrid_windsolar solar_only; do
    run_step "study-scenario-$s" scenario "$s" "scenarios/dutchbay_${s}_2025Q4.yaml"
  done
  run_step "study-wind-aep-synthetic-micrositing" \
    "$PY" "$KIT/lib/wind_provenance.py" "$OUT/study/wind"
  run_step "study-monte-carlo-$study_trials" \
    "$PY" "$KIT/lib/mc_run.py" "$study_trials" "$OUT/study/mc"
  run_step "study-sobol-morris-pawn" \
    "$PY" "$KIT/lib/run_global_sa.py" "$OUT/study/sa" "${sa_extra[@]}"
  run_step "study-debt-mix-optimizer" \
    "$PY" analytics/cli/cli_capital_structure_optimize_hydra.py \
    config=scenarios/dutchbay_lendercase_2025Q4.yaml mode=debt_mix \
    objective_key=equity_irr direction=max "output_dir=$OUT/study/optimizer"
  run_step "study-grid-advisory" "$PY" run_full_pipeline_v14.py \
    "config=$KIT/cache/lender_gridon.yaml" +emit_grid_screen=true \
    write_artifacts=true run_scoped=true "export_dir=$OUT/study/grid"
  run_step "study-executive-workbook-capital-risk" "$PY" run_full_pipeline_v14.py \
    config=scenarios/dutchbay_lendercase_2025Q4.yaml \
    emit_capital_risk_report=true capital_risk_report.n_trials=2000 \
    emit_executive_workbook=true write_artifacts=true run_scoped=true \
    "export_dir=$OUT/study/emitters"
fi

if [[ -f "${BLUE_WHALE_POWER_CURVE_CSV:-/nonexistent}" ]]; then
  run_step "blue-whale-private-wind-siting" capture_json "$OUT/blue_whale_siting.json" \
    "$PY" scripts/run_blue_whale_wind_siting_v14.py
else
  blocked_external "blue-whale-private-wind-siting" "confidential power curve not supplied"
fi
if [[ -f "${DUTCHBAY_MET_MAST_617725_SOURCE:-/nonexistent}" &&
      -d "${DUTCHBAY_NASA_POWER_DIR:-/nonexistent}" &&
      -f "${BLUE_WHALE_POWER_CURVE_CSV:-/nonexistent}" ]]; then
  run_step "blue-whale-private-met-mast-transfer" capture_json "$OUT/blue_whale_mast.json" \
    "$PY" scripts/run_blue_whale_met_mast_transfer_v14.py
else
  blocked_external "blue-whale-private-met-mast-transfer" \
    "mast export, NASA POWER cache and confidential power curve required"
fi
if [[ -f "${BLUE_WHALE_PRIVATE_ANCHORS_PATH:-/nonexistent}" ]]; then
  run_step "blue-whale-private-capex-solar" capture_json "$OUT/blue_whale_capex_solar.json" \
    "$PY" scripts/run_blue_whale_capex_solar_resource_v14.py \
    "private_anchors_path=$BLUE_WHALE_PRIVATE_ANCHORS_PATH"
else
  blocked_external "blue-whale-private-capex-solar" "private CAPEX anchors not supplied"
fi

if ((ONLINE_SECURITY)); then
  run_step "online-security-audit" make security
else
  printf 'online-security-audit\tNOT_RUN_OFFLINE\t0\tnetwork-dependent, opt-in\n' >> "$RECEIPT"
fi
if [[ "$PROFILE" == full ]]; then
  SCOPE=FULL_GOVERNED_SOFTWARE_SUITE
else
  SCOPE=FOCUSED_SMOKE_ONLY
fi
if ((BLOCKED)); then
  printf 'status=%s_EXTERNAL_ASSURANCE_INCOMPLETE\n' "$SCOPE" >> "$OUT/manifest.txt"
  printf '\n%s passed; %d private-input workflows BLOCKED (not bankable).\n' "$SCOPE" "$BLOCKED"
  if ((REQUIRE_PRIVATE)); then exit 3; fi
else
  printf 'status=%s_WITH_SUPPLIED_PRIVATE_PATHS_PASSED\n' "$SCOPE" >> "$OUT/manifest.txt"
fi
printf 'Receipts: %s\nSource inventory: %s\n' "$RECEIPT" "$OUT/python_source_inventory.txt"
printf 'This does NOT certify land, turbine suitability, grid, EIA or lender acceptance.\n'
