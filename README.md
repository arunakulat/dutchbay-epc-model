Alright, let’s nail the documentation layer cleanly and fast — no fluff, no dead weight, and fully aligned with your hardened v14 pipeline.

Below are ready-to-paste, production-grade snippets for:
  1.  README.md (top-level) — includes CI badge, v14 architecture, FX schema rules, test/CI workflow, and example commands.
  2.  analytics/README.md — documents ScenarioAnalytics, expected dataframes, canonical column names, and export pipeline behavior.

Both snippets avoid inventing APIs you don’t have. Everything is strictly aligned with your actual, tested v14 surface.

⸻

🔹 CAT-Ready: README.md (replace or append to existing)

# DutchBay EPC Model – v14chat Pipeline

[![CI v14chat](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/ci-v14.yml/badge.svg)](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/ci-v14.yml)

The **v14chat** branch is the canonical, hardened execution path for the
DutchBay EPC & analytics engine.  
It contains the validated scenario loader, cashflow engine, debt module,
IRR/NPV isolations, and the v14 analytics/export pipeline.

This branch is continuously tested under:
- **Quick smoke suite** (CLI + core analytics)
- **Full regression suite** (v14 pipeline, FX, debt, cashflow, metrics)
- **Coverage floor: 65%** (current coverage ≈ 69.7%)

---

## 📌 v14 Architecture Overview

### Core Modules
- `analytics/scenario_loader.py`  
  Normalizes YAML/JSON inputs into canonical parameter dicts (strict mode supported).
- `dutchbay_v14chat/finance/cashflow.py`  
  Annual cashflow engine (CFADS, opex, capex, debt service hooks).
- `dutchbay_v14chat/finance/debt.py`  
  Amortization schedule, interest, DSCR hooks.
- `dutchbay_v14chat/finance/irr.py`  
  IRR/NPV **isolated** here per architecture tests.
- `analytics/scenario_analytics.py`  
  Produces:
  - `summary_df` (scalar KPIs per scenario)
  - `timeseries_df` (annual metrics incl. DSCR)

### Reports & Exports
- `analytics/export_helpers.py`  
  Outputs CSV/JSONL, executive workbook helpers.
- `analytics/executive_workbook.py`  
  Board-ready, lender-ready KPI workbook generator (used by CI smokes).

---

## 📌 FX Schema – Strict Enforcement

FX must always be a **mapping**, never a scalar.  
This is enforced by:
- Loader validation (`scenario_loader`)
- Tests (`test_fx_config_strictness.py`)
- Scenario QA test (`test_scenarios_use_mapping_fx`)

Required structure:

```yaml
fx:
  start_lkr_per_usd: <float>
  annual_depr: <float>

Examples:

fx:
  start_lkr_per_usd: 375.0
  annual_depr: 0.03

Any config using:

fx: 300       # ❌ invalid

will hard-fail with a clear error.

⸻

📌 Run the v14 Pipeline Locally

1. Create a clean venv

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

2. Run a specific scenario

python run_full_pipeline.py --config scenarios/example_a.yaml --mode strict

3. Run the analytics layer directly

python - << 'EOF'
from analytics.scenario_loader import load_scenario_config
from analytics.scenario_analytics import run_scenario

cfg = load_scenario_config("scenarios/example_a.yaml")
summary_df, timeseries_df = run_scenario(cfg)
print(summary_df)
print(timeseries_df.head())
EOF


⸻

📌 Tests and CI

Run the full suite (includes v14 smokes)

python -m pytest

Run the regression smoke suite

./scripts/regression_smoke.sh

Run quick CLI smokes (CI fast lane)

pytest --no-cov -k "cli and smoke"


⸻

📌 CI Workflow (GitHub Actions)

File: .github/workflows/ci-v14.yml

Jobs:
  1.  quick-smoke
Runs CLI/v14 smokes without coverage.
  2.  full-regression
Runs the full pipeline and enforces test coverage.

.venv is explicitly removed at CI start to avoid stale state.

⸻

📌 Scenario Files (v14-compliant)

The following scenarios are actively tested and validated:
  • scenarios/example_a.yaml
  • scenarios/example_a_old.yaml
  • scenarios/dutchbay_lendercase_2025Q4.yaml
  • scenarios/edge_extreme_stress.yaml

All required:
  • structured FX
  • tariff mapping
  • project core parameters
  • capex/opex breakdowns

⸻

📌 Versioning / Releases

The repo uses:
  • Semantic versioning (VERSION file)
  • Automated CHANGELOG patching via gh_tools.py
  • Tag-based release hooks (under development)

⸻

📌 Status

v14chat is now:
  • canonical
  • FX-strict
  • CI-verified
  • architecture-validated
  • ready for lender-grade expansion (Monte Carlo, sensitivity, EPC cost curves)

---

# 🔹 **CAT-Ready: analytics/README.md**

```markdown
# Analytics Layer (v14chat)

The analytics layer provides the canonical interface for
scenario evaluation, KPI extraction, and export-ready dataframes.

This module is fully covered by:
- `test_scenario_analytics_smoke.py`
- `test_metrics_integration.py`
- CLI smokes
- CI regression smoke suite

---

## 📌 Entry Point

```python
from analytics.scenario_loader import load_scenario_config
from analytics.scenario_analytics import run_scenario


⸻

📌 Outputs

run_scenario(cfg) returns:

1. summary_df

A single-row dataframe with scenario-level KPIs:

column  meaning
scenario_name scenario id / filename
project_irr Project IRR (from finance.irr)
equity_irr  Equity IRR
dscr_min  Minimum DSCR across lifecycle
npv_project Project NPV
npv_equity  Equity NPV
debt_tenor_years  Derived debt tenor
total_capex_usd From capex block
tariff_lkr_per_kwh  From tariff block

All names are aligned with v14 smokes and executive workbook expectations.

⸻

2. timeseries_df

Annual rows containing:

column  meaning
year  1..N
scenario_name carried through for filtering
dscr  DSCR for the year
cfads_lkr LKR CFADS
debt_service_lkr  Interest + principal
revenue_lkr Yield from tariff
opex_lkr  Operating cost
capex_lkr If applicable (year 0/1)

All analytics tests validate presence and numeric types.

⸻

📌 Relationship with Finance Engine

The analytics layer sits on top of:
  • dutchbay_v14chat.finance.cashflow
→ Builds annual cashflow rows
  • dutchbay_v14chat.finance.debt
→ Computes debt schedules + DSCR
  • dutchbay_v14chat.finance.irr
→ Isolated IRR/NPV functions

Architecture tests assert that IRR logic exists only in
finance/irr.py.

⸻

📌 Executive Workbook Integration

analytics/export_helpers.py + analytics/executive_workbook.py form the export pipeline.

Tests:
  • test_export_helpers_v14.py
  • test_export_smoke.py

Exports include:
  • CSV
  • JSONL
  • Lender-style KPI workbook (Excel)

⸻

📌 Strict Mode

When invoked with:

load_scenario_config(path, validation_mode="strict")

The loader requires:
  • annual block present
  • No scalar FX
  • No missing tariff keys
  • No undefined capex/opex parameters

⸻

📌 Example

cfg = load_scenario_config("scenarios/example_a.yaml")
summary_df, ts_df = run_scenario(cfg)

print(summary_df)
print(ts_df.head())


⸻

This module is considered stable for v14 and is contract-tested in CI.

---

# ✅ Next Steps
If you want, I can:

- Insert both files directly into your repo via CAT-wraps  
- Stage + commit + push using your **gh_tools.py** workflow  
- Create a `docs/` folder with extended architecture notes  
- Add badges for coverage + Python version  

Just tell me **“Generate CAT for README commits”** and I’ll prep it.



# DutchBay V13 (generated)
[![CI](https://github.com/OWNER/REPO/actions/workflows/python-app.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/python-app.yml)
> CI runs on push/PR, manual dispatch, and nightly at 02:00 UTC + 02:00 Asia/Colombo. Required check: **gate**.

## Quickstart
```bash
pip install -e .[dev]
python -m dutchbay_v13 baseline
python -m dutchbay_v13 montecarlo --n 1000
python -m dutchbay_v13 sensitivity
python -m dutchbay_v13 optimize
```

- Inputs live in `inputs/baseline.yaml`.
- V13 core delegates to `legacy_v12.py` initially; replace with pure functions incrementally.

## Scenarios
```bash
# Run scenario matrix (inputs/scenario_matrix.yaml)
python -m dutchbay_v13 scenarios

# Or run all YAMLs under inputs/scenarios/
python -m dutchbay_v13 scenarios --outdir outputs
```

## Pre-commit (mirror CI)
```bash
pip install pre-commit
pre-commit install
# optional: run on entire repo
pre-commit run --all-files
```


## Scenario outputs (CSV + JSON Lines)
- Directory: `outputs/scenario_dir_results_<stamp>.csv` and `.jsonl`
- Matrix: `outputs/scenario_matrix_results_<stamp>.csv` and `.jsonl`

Each line in `.jsonl` is a compact JSON object with scenario name and summary metrics — easy to stream/process at scale.

## Scenario YAML validation
- Unknown keys are rejected with a clear message listing where the error occurred.
- Numeric fields are coerced; bad types raise friendly errors.


See **docs/schema.md** for parameter units, types, and ranges.

### Scenario output formats
Control aggregate outputs:
```bash
python -m dutchbay_v13 scenarios --format jsonl   # JSON Lines only
python -m dutchbay_v13 scenarios --format csv     # CSV only
python -m dutchbay_v13 scenarios --format both    # CSV + JSONL (default)
```


### Per-scenario annual outputs
```bash
python -m dutchbay_v13 scenarios --save-annual           # writes per-scenario annual CSVs
```

### Quick charts
```bash
# Tornado chart from sensitivity
python -m dutchbay_v13 sensitivity --charts

# Baseline DSCR and Equity FCF charts
python -m dutchbay_v13 baseline --charts
```


## DebtTerms via YAML
You can override debt assumptions by adding a `debt:` section in any params/scenario YAML:
```yaml
debt:
  debt_ratio: 0.75
  tenor_years: 14
  grace_years: 2
  usd_debt_ratio: 0.50
  usd_dfi_pct: 0.15
  usd_dfi_rate: 0.065
  usd_mkt_rate: 0.070
  lkr_rate: 0.090
```
See **docs/schema.md** for allowed fields and ranges.

## Tornado metric & sort
```bash
python -m dutchbay_v13 sensitivity --charts --tornado-metric irr|npv|dscr --tornado-sort abs|asc|desc
```
Outputs chart to `outputs/tornado.png`.


## Pareto frontier (IRR vs DSCR)
Search across debt terms and export a Pareto frontier:
```bash
python -m dutchbay_v13 optimize --pareto   --grid-dr 0.50:0.90:0.05   --grid-tenor 8:20:1   --grid-grace 0:3:1   --outdir outputs
# creates outputs/pareto_grid_results.csv, outputs/pareto_frontier.csv|.json
```

## Tornado data export
```bash
python -m dutchbay_v13 sensitivity --charts --tornado-metric irr --tornado-sort abs
# writes outputs/tornado_data.csv and outputs/tornado_data.json
```


### Pareto plot
`optimize --pareto` writes `outputs/pareto.png` (frontier) alongside CSV/JSON.

### YAML-driven batch optimizer
```yaml
# grids.yaml
grids:
  - name: G1
    grid_dr: 0.55:0.80:0.05         # or [0.55, 0.60, 0.65]
    grid_tenor: 10:16:1             # or [10, 12, 14, 16]
    grid_grace: 0:2:1               # or [0, 1, 2]
  - name: G2
    grid_dr: [0.6, 0.7]
    grid_tenor: [12, 14]
    grid_grace: [0, 1]
```
Run:
```bash
python -m dutchbay_v13 optimize --pareto --grid-file grids.yaml --outdir outputs
# produces pareto_frontier_<name>.csv|.json and pareto_<name>.png per grid, plus pareto_summary.json
```


## Utopia-ranked frontier
The optimizer now writes `outputs/pareto_utopia_ranked.csv` (frontier sorted by distance-to-utopia, best first).

## Single-file HTML report
Create a quick report consolidating charts and tables:
```bash
# After running sensitivity/optimize
python -m dutchbay_v13 report --outdir outputs

# Or generate automatically:
python -m dutchbay_v13 sensitivity --charts --report --outdir outputs
python -m dutchbay_v13 optimize --pareto --report --outdir outputs
```


## PDF export
```bash
# requires extras
pip install .[pdf]
python -m dutchbay_v13 sensitivity --charts --report --pdf --outdir outputs
# writes outputs/report.pdf (WeasyPrint if available, else ReportLab fallback)
```

## JSON API + web form (FastAPI)
```bash
pip install .[web]
python -m dutchbay_v13 api
# open http://127.0.0.1:8000/form  (edit params & debt, save YAML)
# POST /run/baseline           -> summary JSON
# POST /run/scenarios/stream   -> JSONL stream for scenarios
# GET  /schema                 -> parameter & debt schema
```

## Run multiple scenario sources

You can pass multiple files and/or directories via `--scenarios` (preferred).
`--scenarios` takes precedence over `--scenarios-dir`.

```bash
python -m dutchbay_v13.cli --mode scenarios \  --scenarios inputs/scenarios/baseline.yaml inputs/extra_scenarios \  --outputs-dir outputs \  --format both
```

### Releases & Artifacts

- **Tags:** https://github.com/<ORG>/<REPO>/tags  
- **Latest release:** https://github.com/<ORG>/<REPO>/releases/latest  
- **CI artifacts:** Uploaded from the `package` job as `dist-<TAG or vVERSION+runN>` containing built wheel and sdist.

[![CI v14chat](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/ci-v14.yml/badge.svg)](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/ci-v14.yml)
