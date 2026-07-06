# DutchBay EPC Model – 150MW Wind Farm Financial Model

[![Test Suite](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/test-suite.yml/badge.svg)](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/test-suite.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Production-grade financial modeling suite for renewable energy project development, DFI/Lender analysis, and EPC evaluation.**

---

## 🚀 Quick Start

See [QUICK_START.md](QUICK_START.md) for setup and the four routines. The
governance ruleset is [go_with_the_flow_rules_v3_0_clean.csv](go_with_the_flow_rules_v3_0_clean.csv).

### For Developers

```bash
# Clone repository
git clone https://github.com/arunakulat/dutchbay-epc-model.git
cd dutchbay-epc-model

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (requirements.txt = the pinned reproducibility lock;
# pyproject.toml is the abstract source of truth — see the [dev] extra for tooling)
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run the canonical lender-case pipeline (Hydra CLI — key=value, not --flags)
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
```

---

## 🏛️ Architecture Overview

### v14 Status

The canonical, hardened execution path (`main`) features:

- ✅ **Validated scenario loader** with strict YAML/JSON parsing
- ✅ **Annual cashflow engine** (CFADS, OpEx, CapEx, debt service)
- ✅ **Debt modeling** (dual-DSCR sizing, DSCR/LLCR/PLCR, balloon treatment)
- ✅ **Isolated IRR/NPV** (`finance/irr.py`) and build-up WACC (`finance/wacc_v14.py`)
- ✅ **Analytics** — sensitivity tornado, Monte Carlo (`analytics/mc/`), optimization
- ✅ **Multi-tech generation** — wind / solar producers + BESS storage + enum-recognised generation
  types (tidal / hydro / …) via a config `type` enum (`finance/tech_types.py`; hybrid-capable)
- ✅ **Wind resource** — ERA5 → Weibull → PyWake bankable AEP (P50/P75/P90), wind rose, micro-siting
- ✅ **GIS siting** — GeoTIFF/GWA/DEM/land-cover/RIX/exclusion/MCDM toolchain (opt-in `[gis]`)
- ✅ **Grid screening** — advisory design-stage SCR/reactive/ride-through study (opt-in `[grid]`, default-off)
- ✅ **Export infrastructure** (CSV, Excel, JSON) + HTML/PDF lender report (`app/reports/`)
- ✅ **CI/CD** — gated `Test Summary` + `fastlane` + `smoke`, mypy, framework-compliance lints

### Core Modules

```
analytics/                    # Analytics & scenario evaluation
  ├── evaluation_v14.py      # The single evaluation gateway (evaluate_with_overrides)
  ├── pipeline_v14_enhanced.py  # Lender-grade pipeline orchestration (run_v14_pipeline)
  ├── scenario_loader.py     # YAML/JSON config parser
  ├── core/metrics.py        # Canonical KPI computation
  ├── sensitivity/           # Sensitivity analysis (tornado, global SA, interaction, optimizer)
  ├── mc/                    # Monte Carlo engine (analytics.mc.engine)
  ├── wind/                  # Wind-rose (wind_rose.py) + AEP-summary builder for reports
  ├── gis/                   # GIS-for-wind siting stack (opt-in [gis]/[micrositing]; see below)
  ├── grid/                  # Grid interconnection SCREENING study (opt-in [grid]; advisory)
  ├── dashboard/             # Streamlit sensitivity dashboard (streamlit_app.py; [dashboard])
  ├── cost/                  # Bottom-up capex/opex cost engine
  └── fx/                    # FX calibration (BIS/CBSL) + Monte Carlo FX drift

finance/                      # Financial calculation engine
  ├── cashflow_v14.py        # Cash flow projections
  ├── debt_v14.py            # Debt modeling & DSCR
  ├── irr.py                 # Isolated IRR/NPV (ARCH-02 canonical source)
  ├── wacc_v14.py            # WACC (ARCH-02 canonical source)
  └── cashflow_v14_tax.py    # Tax (SL plant/civil split, TLCF, interest WHT)

wind_resource/                # Wind pipeline: ERA5 -> Weibull -> PyWake -> bankable AEP
  ├── wind_pipeline.py       # Orchestrates the assessment (via scripts/run_wind_analysis_v14.py)
  ├── weibull_fit.py         # Weibull (k, A) fit from ERA5 time series
  ├── bankable_aep.py        # Gross AEP + PyWake wake loss + uncertainty budget (P50/P75/P90)
  └── layout_optimizer.py    # DTU TopFarm micro-siting optimizer (opt-in [micrositing])
solar_resource/               # pvlib solar producer (hybrid multi-tech; optional [solar] extra)
api/                          # FastAPI endpoints (pipeline, sensitivity)
app/                          # Web service, async jobs, and report rendering
  └── reports/               # HTML (Jinja2) + PDF (WeasyPrint, [report]) lender report,
                             #   incl. per-tech comparison + interaction-grid chapters

# Coverage gate spans finance + analytics + wind_resource + api + app + solar_resource (>=95%, .coveragerc).

scenarios/                    # Scenario configuration files
  ├── dutchbay_lendercase_2025Q4.yaml   # Canonical lender case
  ├── dutchbay_basecase_2025Q4.yaml
  ├── dutchbay_optimistic_2025Q4.yaml
  └── dutchbay_pessimistic_2025Q4.yaml

exports/                      # Generated outputs (git-ignored)
  ├── *.csv
  ├── *.xlsx
  └── *.png

tests/                        # Test suite
  ├── contracts/             # Contract tests
  ├── analytics/             # Analytics tests
  └── integration/           # Integration tests

docs/                         # Documentation
  ├── PIPELINE_ARCHITECTURE.md    # Technical architecture
  ├── ANALYTICS_INTEGRATION.md    # Analytics module details
  └── CASPER_MC_INTEGRATION.md    # Monte Carlo / tail-risk integration
```

---

## 📊 Key Features

### Financial Modeling
- **Debt Structuring**: Multi-tranche debt (USD DFI, USD commercial, LKR local) with grace periods
- **Cash Flow Analysis**: CFADS, debt service coverage, operating cash flows
- **Returns Calculation**: Project IRR, Equity IRR, NPV (project & equity)
- **Risk Metrics**: DSCR (minimum, average), break-even analysis

### Analytics Capabilities
- **Scenario Analysis**: Compare base, optimistic, pessimistic cases
- **Sensitivity Analysis**: Tornado charts for key drivers
- **Monte Carlo Simulation**: Probabilistic modeling (shipped; LHS engine + CASPER tail-risk)
- **Parameter Validation**: Strict YAML schema enforcement

### Export & Reporting
- **CSV/Excel**: Timestamped exports, never overwrites
- **Executive Workbooks**: Board-ready KPI summaries (`analytics/executive_workbook.py`)
- **JSON/JSONL**: Machine-readable outputs for pipelines
- **Charts**: Matplotlib-based visualizations
- **Lender report**: HTML (Jinja2, core dep) + PDF (WeasyPrint, opt-in `[report]`) rendered
  from `app/reports/`, with a per-technology headline-KPI **comparison chapter**
  (`app/reports/tech_comparison_emit.py`) and a two-factor **sensitivity interaction grid**
  (`app/reports/interaction_grid_emit.py`). The PDF backend degrades gracefully — the HTML
  report always renders; PDF raises a clear `ReportDependencyError` when WeasyPrint is absent.

### Wind Resource & Bankable AEP
- **ERA5 → bankable AEP pipeline** (`wind_resource/`, opt-in `[wind]`): ERA5/Copernicus
  ingestion → Weibull (k, A) fit → gross AEP → PyWake wake loss → uncertainty budget →
  **P50 / P75 / P90** energy. Driven by `scripts/run_wind_analysis_v14.py`; the finance stack
  consumes a frozen wind-export JSON, so lender runs need no Copernicus credentials.
- **Wind rose** (`analytics/wind/wind_rose.py`): per-sector directional frequency, consumed
  by the bankable-AEP wake model and the layout optimizer.
- **Micro-siting layout optimizer** (`wind_resource/layout_optimizer.py`, opt-in
  `[micrositing]`): DTU **TopFarm** on PyWake proposes an AEP-maximising candidate layout
  from a boundary + exclusion mask + wind rose. The optimizer only *proposes* — it is
  **KPI-neutral**; no headline result depends on it.

### GIS-for-Wind Siting (opt-in `[gis]`)
A raster/vector siting toolchain under `analytics/gis/` — all imports CASPER-guarded, so the
base install needs no GDAL/GIS stack. See [docs/GIS_GEOTIFF_EXPORT.md](docs/GIS_GEOTIFF_EXPORT.md).
- **GeoTIFF export** (`geotiff_export.py`) — QGIS-ready EPSG:4326 rasters + a data-lake manifest.
- **Global Wind Atlas** ingest (`gwa_ingest.py`) — ~250 m GWA reference layers.
- **Copernicus GLO-30 DEM** (`dem_ingest.py`) — 30 m elevation + terrain derivatives.
- **ESA WorldCover → roughness (z₀)** (`landcover_roughness.py`) — ~10 m land-cover to z₀.
- **Boundary clip** (`boundary_clip.py`) — clip wind/AEP rasters to a project polygon.
- **RIX / ΔRIX** (`rix.py`) — terrain-ruggedness envelope diagnostic.
- **Exclusion mask** (`exclusion_mask.py`) — setback-buffered constraints → buildable-area raster.
- **GIS-MCDM suitability** (`mcdm_suitability.py`) — AHP-weighted Weighted-Linear-Combination surface.

### Grid Interconnection Screening (opt-in `[grid]`, advisory)
An in-house **design-stage** grid study under `analytics/grid/` (SCR@POC via pandapower
IEC 60909, ANDES LVRT ride-through, reactive/voltage screen). Default-**off** and additive,
so committed scenarios stay byte-identical (**KPI-neutral**), and its results are **advisory**.
> **Honesty boundary (stated in the code):** this is **SCREENING / DESIGN-STAGE ONLY — NOT the
> utility-accepted bankable grid-connection study.** CEB/NSCC require PSS/E or PowerFactory run
> against their confidential grid base case; the OEM `.dyr/.dll/.pfd` binaries feed *that* study.
> HVRT / frequency-response cases are reported as honest **NOT-RUN** where the model cannot assert them.

See [docs/GRID_INTERFACE_SCHEMA.md](docs/GRID_INTERFACE_SCHEMA.md) for the config schema.

---

## 🔧 Development Standards

### "Go With The Flow" Rules

These non-negotiable principles ensure production-grade quality:

1. **Config-Driven**: All parameters in YAML with validation
2. **Batch-Friendly**: No hardcoded paths, CLI-compatible
3. **Stateless**: Reproducible results, no mutable globals
4. **Test-First**: Contract tests for all analytics
5. **Type-Safe**: Full mypy compliance

See [go_with_the_flow_rules_v3_0_clean.csv](go_with_the_flow_rules_v3_0_clean.csv) (GWTF v3.0, 64 rules) for the complete standards.

### Code Quality

```bash
# Type checking (the same strict, full-surface gate CI runs — no --ignore-missing-imports;
# every untyped third-party dep is declared per-module in mypy.ini)
mypy finance/ analytics/ wind_resource/ solar_resource/ api/ app/ analysis_tools/ \
  run_full_pipeline_v14.py run_scenario_analytics_v14.py \
  dutchbay_bootstrap.py dutchbay_bootstrap_rules.py constants.py

# Linting (ruff replaced flake8 in the consolidated toolchain, #610)
ruff check analytics/ finance/
black --check analytics/ finance/
isort --check-only analytics/ finance/

# Testing with coverage (the 6 engine packages CI gates at >=95%)
pytest --cov=finance --cov=analytics --cov=wind_resource --cov=api --cov=app --cov=solar_resource --cov-report=html
```

### CI/CD Pipeline

- **Quick Smoke**: CLI + core analytics (fast feedback)
- **Full Regression**: Complete v14 pipeline + coverage
- **Coverage**: the six engine packages (`finance`, `analytics`, `wind_resource`, `api`, `app`, `solar_resource`; untestable CLI/viz/worker infra excluded via `.coveragerc`) are gated at **≥95%**. The **`--cov-fail-under=95`** floor is enforced where the full suite actually runs — the CI test step (`.github/workflows/test-suite.yml`) and `make test` — so coverage cannot silently regress. (As of #439 `pytest.ini`/`pytest.ci.ini`/`tox.ini` were retired; `pyproject.toml` `[tool.pytest.ini_options]` is the single pytest config and `.coveragerc` the single coverage config.)
- **FX Schema**: Strict enforcement (mapping-only, no scalars)

---

## 📝 Usage Examples

### Basic Scenario Run

```bash
# Hydra CLI: override config with key=value (no --flags)
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
```

### Sensitivity Analysis

```bash
# Canonical Hydra entrypoint (run as a module so `analytics` is importable)
python -m analytics.cli.cli_sensitivity_hydra \
  config=scenarios/dutchbay_lendercase_2025Q4.yaml \
  output_dir=_out/sensitivity
```

### Python API

```python
from analytics.evaluation_v14 import evaluate_with_overrides

# The single evaluation gateway (ARCH-04): returns a flat KPI dict.
kpis = evaluate_with_overrides(
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    overrides={"Financing_Terms.debt_ratio": 0.55},  # optional dotted overrides
)

print(f"Project IRR: {kpis['project_irr']:.2%}")
print(f"Min DSCR: {kpis['min_dscr']:.2f}")
```

### Export to Excel

```python
from analytics.executive_workbook import build_executive_workbook

# Board-ready workbook from the canonical v14 frames.
build_executive_workbook(
    summary_df=summary_df,
    cashflow_df=cashflow_df,
    debt_df=debt_df,
    ratios_df=ratios_df,
    scenario_summary_df=scenario_summary_df,
    output_path="exports/executive_summary.xlsx",
)
```

---

## 📚 Documentation

### For Developers
- [Architecture Overview](docs/PIPELINE_ARCHITECTURE.md) - Pipeline / technical design
- [Analytics Integration](docs/ANALYTICS_INTEGRATION.md) - Analytics module details
- [CASPER / Monte Carlo](docs/CASPER_MC_INTEGRATION.md) - Tail-risk & MC integration
- [FX / WACC / Equity](docs/FX_WACC_EQUITY_INTEGRATION_v14.md) - Multi-currency + discounting
- [GIS GeoTIFF Export](docs/GIS_GEOTIFF_EXPORT.md) - Raster export for QGIS
- [Wind Interface Schema](docs/WIND_INTERFACE_SCHEMA.md) - Wind-export contract + [AEP provenance](docs/AEP_PROVENANCE.md)
- [Grid Interface Schema](docs/GRID_INTERFACE_SCHEMA.md) - Grid-screening config schema (advisory study)

### For Project Managers
- [Changelog](CHANGELOG.md) - Version history
- [Release Process](RELEASING.md) - How to create releases
- [Security](SECURITY.md) - Security policy

---

## 🛣️ Roadmap

### Phase 2: Interactive Analytics (Mostly Complete ✅)
- [x] Streamlit dashboard for scenario exploration (`analytics/dashboard/streamlit_app.py`)
- [x] REST API for sensitivity/Monte Carlo (`api/sensitivity_api.py`, `api/pipeline_api.py`)
- [ ] Real-time parameter validation UI

### Phase 3: Advanced Reporting (Mostly Complete ✅)
- [x] Automated Excel report generation (`analytics/executive_workbook.py`)
- [x] Chart export (PNG/SVG) (`analytics/export_helpers.py`)
- [ ] Health/audit tracking

### Phase 4: Optimization (Mostly Complete ✅)
- [x] Scenario comparison tools (per-tech report chapter, `app/reports/tech_comparison_emit.py`)
- [x] Multi-objective optimizer (NSGA-II Pareto search, `analytics/sensitivity/optimizer.py`, opt-in `[pareto]`)
- [ ] Version control for scenarios

### Phase 5: Stakeholder Deliverables (Planned 📋)
- [ ] DFI/Lender presentation mode
- [ ] Board presentation templates
- [ ] Risk dashboards

---

## ⚙️ Technical Requirements

- **Python**: 3.11+
- **Dependencies**: `pyproject.toml` (abstract source of truth) + `requirements.txt` (pinned lock for CI/reproducibility)
- **Dev Tools**: the `[dev]` extra — `pip install -e ".[dev]"`
- **Environment**: macOS, Linux, or Windows with WSL

### Optional install extras

The base install runs the finance engine + Hydra CLI with no heavy scientific stack. Each
capability below is an **opt-in extra** whose imports are CASPER-guarded (they fail loud with an
actionable message only when the capability is actually invoked without the extra installed):

| Extra | Installs | Powers |
| --- | --- | --- |
| `[dev]` | ruff/black/isort, mypy + stubs, bandit, pip-audit, pytest stack, hypothesis, build | The full CI gate |
| `[api]` | fastapi, uvicorn | The HTTP API (`api/`, `app/`) |
| `[dashboard]` | streamlit | Sensitivity dashboard (`analytics/dashboard/streamlit_app.py`) |
| `[wind]` | cdsapi, xarray, netcdf4, windpowerlib, turbine-models, py-wake | ERA5 → bankable-AEP wind pipeline |
| `[micrositing]` | topfarm | Micro-siting layout optimizer (DTU TopFarm on PyWake) |
| `[solar]` | pvlib | Solar producer for hybrid multi-tech |
| `[pareto]` | pymoo | NSGA-II multi-objective Pareto search |
| `[gis]` | rasterio, shapely | GIS-for-wind siting raster/vector toolchain |
| `[report]` | weasyprint, reportlab, geopandas, contextily | PDF lender report + location/context maps |
| `[jobs]` | arq, redis | Durable cross-process async job worker |
| `[grid]` | pandapower==3.3.0, andes, opendssdirect.py | Grid interconnection **screening** study (advisory) — install with `PIP_CONSTRAINT=constraints.txt pip install -e ".[grid]"` |

---

## 🤝 Contributing

### Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes following "Go with the Flow" rules
3. Run tests: `pytest tests/`
4. Run quality checks: `ruff`, `black`, `isort`, `mypy`
5. Commit: `git commit -am "feat: Your feature description"`
6. Push: `git push origin feature/your-feature`
7. Create Pull Request

### Before Committing

```bash
# Install pre-commit hooks
pre-commit install

# Run all checks
pre-commit run --all-files
```

---

## 📎 Project Information

- **Project**: Dutch Bay 150MW Wind Farm
- **Location**: Sri Lanka
- **Technology**: Onshore wind energy
- **Capacity**: 150 MW
- **Status**: Financial modeling & development phase

---

## 📝 License

Proprietary - All Rights Reserved

---

## 👥 Team & Support

- **Repository**: [arunakulat/dutchbay-epc-model](https://github.com/arunakulat/dutchbay-epc-model)
- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Documentation**: See `docs/` directory for detailed guides

---

**Last Updated**: July 6, 2026
**Version**: see the `VERSION` file (single source of truth; currently 15.3.0)
