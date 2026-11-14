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
MIN_INTERNAL_GIB="${DUTCHBAY_NOV26_MIN_INTERNAL_GIB:-8}"

usage() {
  cat <<'HELP'
Usage: bash feasibility_reproduce/run_all_NOV26.sh [options]
 --profile full|quick      full default; quick focused smoke
 --jobs N                  pytest workers; default 4, never auto
 --out DIR                 output outside the Git checkout; may be an external drive.
                           Every output, Hydra run dir and test cache goes under it;
                           an existing DIR must be owned by the invoking user
 --require-private         exit 3 before any stage if a confidential input is missing
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
[[ "$MIN_INTERNAL_GIB" =~ ^[1-9][0-9]*$ ]] || die "MIN_INTERNAL_GIB must be a positive integer"
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

# --require-private: a missing confidential input exits 3, before any stage or any write,
# so a caller can tell "private inputs missing" (3) from "a stage failed" (its exit code)
# and from any other refusal (1).
die_private() { printf 'FATAL: %s\n' "$*" >&2; exit 3; }
if ((REQUIRE_PRIVATE)); then
  [[ -f "${BLUE_WHALE_POWER_CURVE_CSV:-/nonexistent}" ]] ||
    die_private "--require-private needs BLUE_WHALE_POWER_CURVE_CSV"
  [[ -f "${DUTCHBAY_MET_MAST_617725_SOURCE:-/nonexistent}" ]] ||
    die_private "--require-private needs DUTCHBAY_MET_MAST_617725_SOURCE"
  [[ -d "${DUTCHBAY_NASA_POWER_DIR:-/nonexistent}" ]] ||
    die_private "--require-private needs DUTCHBAY_NASA_POWER_DIR"
  [[ -f "${BLUE_WHALE_PRIVATE_ANCHORS_PATH:-/nonexistent}" ]] ||
    die_private "--require-private needs BLUE_WHALE_PRIVATE_ANCHORS_PATH"
fi

CALLER_PWD="$PWD"
cd "$REPO"
[[ -f requirements.txt && -f dutchbay_environment.py ]] || die "wrong checkout: $REPO"
command -v git >/dev/null || die "git missing"
command -v make >/dev/null || die "make missing"
SHA="$(git rev-parse HEAD)"; SHORT="${SHA:0:12}"
BRANCH="$(git branch --show-current)"
TRACKING="$(git rev-parse origin/main 2>/dev/null || printf unavailable)"
OUT="${OUT:-$HOME/Downloads/DutchBay_NOV26_runs/${SHORT}_$(date +%Y%m%d_%H%M%S)}"
# Resolve --out physically WITHOUT creating it, refuse it inside the checkout, then
# refuse to reuse a directory another user owns (its contents could be swapped mid-run).
case "$OUT" in /*) ;; *) OUT="$CALLER_PWD/$OUT" ;; esac
OUT_PROBE="$OUT"; OUT_REST=""
while [[ ! -d "$OUT_PROBE" ]]; do
  OUT_REST="/$(basename "$OUT_PROBE")$OUT_REST"; OUT_PROBE="$(dirname "$OUT_PROBE")"
done
OUT="$(cd "$OUT_PROBE" && pwd -P)$OUT_REST"
case "$OUT/" in "$REPO/"*) die "--out must be outside checkout";; esac
if [[ -e "$OUT" && ! -O "$OUT" ]]; then
  die "--out exists and is not owned by the invoking user: $OUT"
fi
if [[ -d "$OUT" ]] && [[ -n "$(find "$OUT" -maxdepth 0 \( -perm -020 -o -perm -002 \) -print)" ]]; then
  die "--out exists and is writable by group or others: $OUT"
fi
mkdir -p "$OUT"
VENV="${DUTCHBAY_VENV:-$REPO/.venv}"
[[ "$VENV" == /* && -x "$VENV/bin/python" ]] ||
  die "configure governed Python with an absolute DUTCHBAY_VENV (or local .venv)"
PY="$VENV/bin/python"
export DUTCHBAY_VENV="$VENV"
export DUTCHBAY_FLOW_RULESET_CSV="$REPO/go_with_the_flow_rules_v3_0_clean.csv"
# Bind imports ONLY to this checkout. Never carry a prior checkout from an
# already-activated shell; ENV-01 rejects foreign worktree paths by design.
export PYTHONPATH="$REPO"
export PYTHONDONTWRITEBYTECODE=1
# Private per-run scratch made with mktemp is removed on any exit.
TOOL_BIN=""; TMP_PRIVATE=""
cleanup_private_dirs() {
  [[ -z "$TOOL_BIN" ]] || rm -rf "$TOOL_BIN"
  [[ -z "$TMP_PRIVATE" ]] || rm -rf "$TMP_PRIVATE"
}
trap cleanup_private_dirs EXIT
# The security negative controls exercise .ONESHELL and GNUMAKEFLAGS, both
# unavailable in Apple's GNU Make 3.81. Prepend a runner-local gmake alias
# (without changing users' shell PATH, homebrew links, or origin/main).
# The shim directory is a fresh private mktemp dir, never a reused path under --out, so
# nothing another user wrote can be put first on PATH.
if command -v gmake >/dev/null 2>&1; then
  TOOL_BIN="$(mktemp -d "${TMPDIR:-/tmp}/dutchbay-nov26-bin.XXXXXXXX")"
  ln -s "$(command -v gmake)" "$TOOL_BIN/make"
  export PATH="$TOOL_BIN:$VENV/bin:$PATH"
else
  export PATH="$VENV/bin:$PATH"
fi
MAKE_VERSION="$(make --version | head -n 1)"
MAKE_MAJOR="$(printf '%s\n' "$MAKE_VERSION" | sed -n 's/.* \([0-9][0-9]*\)\..*/\1/p')"
if [[ "$PROFILE" == full ]]; then
  [[ "$MAKE_MAJOR" =~ ^[0-9]+$ ]] && ((MAKE_MAJOR >= 4)) ||
    die "full security regression requires GNU Make 4+; found $MAKE_VERSION (brew install make)"
fi
export COVERAGE_FILE="$OUT/.coverage"
# A space in TMPDIR breaks shell-scripted security watchdog fixtures and
# sshd Include-token tests. Keep large artifacts/caches external, but use a
# small, local, whitespace-free pytest/subprocess scratch directory when
# the external volume is named with spaces (e.g. /Volumes/Data backup).
if [[ "$OUT" == *[[:space:]]* ]]; then
  # A fresh private directory per run, removed on exit, never a fixed shared path.
  TMP_PRIVATE="$(mktemp -d /tmp/dutchbay-nov26-tmp.XXXXXXXX)"
  TMP_WORK="$TMP_PRIVATE"
else
  TMP_WORK="$OUT/tmp"
fi
[[ "$TMP_WORK" != *[[:space:]]* ]] || die "TMP_WORK must not contain whitespace"
mkdir -p "$TMP_WORK" "$OUT/cache/matplotlib" "$OUT/cache/numba"
export TMPDIR="$(cd "$TMP_WORK" && pwd -P)/"
export TMP="$TMPDIR" TEMP="$TMPDIR"
export MPLCONFIGDIR="$OUT/cache/matplotlib"
export NUMBA_CACHE_DIR="$OUT/cache/numba"
# Keep test caches out of the checkout: pytest's cache provider and Hypothesis's example
# database would otherwise write .pytest_cache/ and .hypothesis/ under $REPO.
export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:+$PYTEST_ADDOPTS }-p no:cacheprovider"
export HYPOTHESIS_STORAGE_DIRECTORY="$OUT/cache/hypothesis"
# Every Hydra entry point gets its run directory under $OUT (otherwise Hydra writes
# outputs/<date>/<time>/ into the checkout).
hydra_dir() { printf 'hydra.run.dir=%s/hydra/%s' "$OUT" "$1"; }
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 12)' ||
  die "Python 3.12 required"
OUT_FREE_KIB="$(df -Pk "$OUT" | awk 'END {print $4}')"
INTERNAL_FREE_KIB="$(df -Pk "$HOME" | awk 'END {print $4}')"
((OUT_FREE_KIB >= MIN_FREE_GIB * 1024 * 1024)) ||
  die "output volume free space below ${MIN_FREE_GIB} GiB: $OUT"
((INTERNAL_FREE_KIB >= MIN_INTERNAL_GIB * 1024 * 1024)) ||
  die "internal SSD free space below ${MIN_INTERNAL_GIB} GiB; refuse even with external --out"
printf 'Destination volume: %s (free %.1f GiB)\nInternal SSD: %s (free %.1f GiB)\n' \
  "$(df -Pk "$OUT" | awk 'END {print $1}')" \
  "$(awk -v kb="$OUT_FREE_KIB" 'BEGIN {print kb/1048576}')" \
  "$(df -Pk "$HOME" | awk 'END {print $1}')" \
  "$(awk -v kb="$INTERNAL_FREE_KIB" 'BEGIN {print kb/1048576}')"

RECEIPT="$OUT/receipt.tsv"
printf 'stage\tstatus\tseconds\tnote\n' > "$RECEIPT"
printf 'repo=%s\ncommit=%s\nbranch=%s\nlocal_origin_main=%s\nprofile=%s\njobs=%s\nvenv=%s\nout=%s\n' \
  "$REPO" "$SHA" "${BRANCH:-detached}" "$TRACKING" "$PROFILE" "$JOBS" "$VENV" "$OUT" \
  > "$OUT/manifest.txt"
printf 'scope=software_only_not_external_bankability\n' >> "$OUT/manifest.txt"
printf 'internal_free_kib=%s\noutput_free_kib=%s\nwork_tmpdir=%s\nmake_version=%s\n' \
  "$INTERNAL_FREE_KIB" "$OUT_FREE_KIB" "$TMPDIR" "$MAKE_VERSION" >> "$OUT/manifest.txt"
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
    printf '%s\tPASS\t%s\t%s\n' "$name" "$elapsed" "${STEP_NOTE:--}" >> "$RECEIPT"
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
    "$(hydra_dir "scenario-$slug")" \
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
  "$PY" scripts/run_dutchbay_wake_rebaseline_v14.py "$(hydra_dir dutchbay-14-wake-proxy)"
run_step "blue-whale-solar-bess-dispatch" capture_json "$OUT/blue_whale_dispatch.json" \
  "$PY" scripts/run_blue_whale_solar_bess_v14.py "$(hydra_dir blue-whale-solar-bess-dispatch)"
run_step "dutchbay-lendercase-finance" scenario lender scenarios/dutchbay_lendercase_2025Q4.yaml
run_step "blue-whale-wind-finance" scenario blue_whale_wind scenarios/blue_whale_wind_lot5b_2026.yaml
run_step "blue-whale-solar-bess-finance" scenario blue_whale_solar_bess scenarios/blue_whale_solar_bess_lot5b_2026.yaml

if [[ "$PROFILE" == full ]]; then
  run_step "ruff-black-isort" make lint
  run_step "mypy-typed-surface" make type
  # CI's second mypy gate (test-suite.yml): scripts/ has no __init__.py, so it is a
  # separate invocation that `make type` does not cover. All Blue Whale CLIs live there.
  run_step "mypy-scripts" "$PY" -m mypy scripts/ --ignore-missing-imports \
    --allow-untyped-defs --allow-untyped-calls --allow-any-generics
  run_step "full-pytest-six-package-95pct-coverage" env DUTCHBAY_TEST_MODE=full \
    "$PY" -m pytest tests/ -n "$JOBS" \
    --ignore=tests/grid/test_base_candidate_physical_receipt.py \
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
    "$PY" scripts/run_blue_whale_pv_bess_sizing_v14.py "$(hydra_dir blue-whale-unit-monte-carlo)"
  run_step "blue-whale-project-monte-carlo" capture_json "$OUT/blue_whale_sizing_project.json" \
    "$PY" scripts/run_blue_whale_pv_bess_sizing_v14.py \
    --config-name blue_whale_solar_bess_project_sizing \
    "$(hydra_dir blue-whale-project-monte-carlo)"
  run_step "blue-whale-fixed-bess-monte-carlo" capture_json "$OUT/blue_whale_sizing_fixed.json" \
    "$PY" scripts/run_blue_whale_pv_bess_sizing_v14.py \
    --config-name blue_whale_solar_bess_fixed_bess_sizing \
    "$(hydra_dir blue-whale-fixed-bess-monte-carlo)"
fi

# Optional analytical-study screening runs against current files and the current
# engine. These are NEW screening runs, NOT reproductions of the frozen August 2026
# published KPI vector, PDF, or 294-module manifest. Every financial stage below runs a
# current committed scenario (DutchBay is 14 turbines, #1587). The one exception is the
# synthetic micrositing wiring check, which uses its own synthetic 15-turbine site and
# says so in its receipt note. The August grid-on lender fork in $KIT/cache is not run:
# it predates the 14-turbine layout and main's AEP reconciliation guard refuses it.
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
  STEP_NOTE="synthetic 15-turbine wiring check, not the DutchBay layout" \
    run_step "study-wind-aep-synthetic-micrositing" \
    "$PY" "$KIT/lib/wind_provenance.py" "$OUT/study/wind"
  run_step "study-monte-carlo-$study_trials" \
    "$PY" "$KIT/lib/mc_run.py" "$study_trials" "$OUT/study/mc"
  # ${a[@]+"${a[@]}"}: an empty array under set -u is an error before bash 4.4 (macOS 3.2).
  run_step "study-sobol-morris-pawn" \
    "$PY" "$KIT/lib/run_global_sa.py" "$OUT/study/sa" ${sa_extra[@]+"${sa_extra[@]}"}
  run_step "study-debt-mix-optimizer" \
    "$PY" analytics/cli/cli_capital_structure_optimize_hydra.py \
    config=scenarios/dutchbay_lendercase_2025Q4.yaml mode=debt_mix \
    objective_key=equity_irr direction=max "output_dir=$OUT/study/optimizer" \
    "$(hydra_dir study-debt-mix-optimizer)"
  run_step "study-executive-workbook-capital-risk" "$PY" run_full_pipeline_v14.py \
    config=scenarios/dutchbay_lendercase_2025Q4.yaml \
    emit_capital_risk_report=true capital_risk_report.n_trials=2000 \
    emit_executive_workbook=true write_artifacts=true run_scoped=true \
    "export_dir=$OUT/study/emitters" "$(hydra_dir study-executive-workbook)"
fi

if [[ -f "${BLUE_WHALE_POWER_CURVE_CSV:-/nonexistent}" ]]; then
  run_step "blue-whale-private-wind-siting" capture_json "$OUT/blue_whale_siting.json" \
    "$PY" scripts/run_blue_whale_wind_siting_v14.py "$(hydra_dir blue-whale-private-wind-siting)"
else
  blocked_external "blue-whale-private-wind-siting" "confidential power curve not supplied"
fi
if [[ -f "${DUTCHBAY_MET_MAST_617725_SOURCE:-/nonexistent}" &&
      -d "${DUTCHBAY_NASA_POWER_DIR:-/nonexistent}" &&
      -f "${BLUE_WHALE_POWER_CURVE_CSV:-/nonexistent}" ]]; then
  run_step "blue-whale-private-met-mast-transfer" capture_json "$OUT/blue_whale_mast.json" \
    "$PY" scripts/run_blue_whale_met_mast_transfer_v14.py \
    "$(hydra_dir blue-whale-private-met-mast-transfer)"
else
  blocked_external "blue-whale-private-met-mast-transfer" \
    "mast export, NASA POWER cache and confidential power curve required"
fi
if [[ -f "${BLUE_WHALE_PRIVATE_ANCHORS_PATH:-/nonexistent}" ]]; then
  run_step "blue-whale-private-capex-solar" capture_json "$OUT/blue_whale_capex_solar.json" \
    "$PY" scripts/run_blue_whale_capex_solar_resource_v14.py \
    "private_anchors_path=$BLUE_WHALE_PRIVATE_ANCHORS_PATH" \
    "$(hydra_dir blue-whale-private-capex-solar)"
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
else
  printf 'status=%s_WITH_SUPPLIED_PRIVATE_PATHS_PASSED\n' "$SCOPE" >> "$OUT/manifest.txt"
fi
printf 'Receipts: %s\nSource inventory: %s\n' "$RECEIPT" "$OUT/python_source_inventory.txt"
printf 'This does NOT certify land, turbine suitability, grid, EIA or lender acceptance.\n'
