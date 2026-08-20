# DutchBay EPC Model

[![Test Suite](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/test-suite.yml/badge.svg)](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/test-suite.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A lender and DFI-grade project-finance model for a 150 MW onshore wind farm (with optional
BESS and hybrid solar) in Sri Lanka. The model computes a full cashflow waterfall, sizes
multi-tranche debt against DSCR covenants, applies the Sri Lanka tax regime, runs Monte Carlo
and global sensitivity analysis, and drives an ERA5 to Weibull to AEP to finance pipeline. It
emits CSV, Excel, and JSON artifacts and an HTML or PDF lender report.

## Quick start

```bash
git clone https://github.com/arunakulat/dutchbay-epc-model.git
cd dutchbay-epc-model

python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

make setup                           # pip install -r requirements.txt + pip install -e ".[dev]"

# Run the canonical lender-case pipeline (Hydra CLI: key=value, not --flags)
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
```

See [QUICK_START.md](QUICK_START.md) for the four routines and
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full development guide.

### Codex task context

Every new Codex task, regardless of subject, must be created from the `DutchBay_EPC_Model`
project. Its
durable project folder is `/Users/aruna/Downloads/Dutchbay_EPC_Model`, and Codex must use the
persistent Python 3.12 environment at
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`. Repository commands still run from this
checkout or the task's dedicated worktree; invoke the project environment by absolute path so
it persists independently of worktree cleanup. See GWTF rule `THREAD-01` and [AGENTS.md](AGENTS.md).

## Architecture overview

The canonical, hardened execution path is v14. It provides:

- A validated scenario loader with strict YAML/JSON parsing and a schema guard.
- An annual cashflow engine (CFADS, opex, capex, statutory charges, tax, debt service).
- Debt modelling: multi-tranche (USD DFI, USD commercial, LKR local), dual-DSCR sizing,
  DSCR/LLCR/PLCR covenants, interest during construction, and balloon treatment.
- Isolated IRR/NPV (`finance/irr.py`) and build-up WACC (`finance/wacc_v14.py`).
- Analytics: sensitivity tornado, global sensitivity (Sobol/Morris/PAWN), Monte Carlo
  (`analytics/mc/`), and optimization.
- Multi-technology generation: wind, solar, and BESS producers plus enum-recognised
  generation types via a config `type` discriminator (`finance/tech_types.py`).
- Wind resource: ERA5 to Weibull to PyWake bankable AEP (P50/P75/P90), wind rose, and
  micro-siting (opt-in `[wind]`/`[micrositing]`).
- GIS-for-wind siting (opt-in `[gis]`) and grid interconnection screening (opt-in `[grid]`,
  advisory, default-off).
- Export infrastructure (CSV, Excel, JSON) and an HTML/PDF lender report (`app/reports/`).

### Repository layout

```
run_full_pipeline_v14.py       Canonical single-scenario Hydra CLI (wind-to-finance)
run_scenario_analytics_v14.py  Batch scenario-comparison CLI (lighter, snapshot basis)
constants.py                   Immutable physical constants and unit conversions only

analytics/                     Analytics, evaluation gateway, and scenario orchestration
  evaluation_v14.py            The single evaluation gateway (evaluate_with_overrides)
  contracts_v14.py             Centralized result contracts (the CCCDIR single source)
  pipeline_v14_enhanced.py     Lender-grade pipeline orchestration (run_v14_pipeline)
  scenario_loader.py           YAML/JSON config parser
  schema_guard.py              Strict pre-flight config validation
  core/                        Canonical KPI, return, and risk primitives
  mc/                          Monte Carlo engine (the actual MC code)
  sensitivity/                 Tornado, global SA (Sobol/Morris/PAWN), optimizer
  casper/                      Lender risk-block orchestration (P50/P90/P95, breach prob)
  fx/                          FX calibration (BIS/CBSL) and Monte Carlo FX drift
  wind/  gis/  grid/           Wind analytics bridge, GIS siting, grid screening
  cost/  portfolio/            Bottom-up cost engine and hybrid multi-tech aggregation

finance/                       Deterministic financial calculation engine
  irr.py                       Isolated IRR/NPV (ARCH-02 canonical source)
  wacc_v14.py                  Build-up WACC (ARCH-02 canonical source)
  cashflow_v14.py              Core annual cashflow engine (+ tax/fx/production helpers)
  debt_v14.py                  Debt modelling, tranche sizing, and DSCR

wind_resource/                 ERA5 to Weibull to PyWake bankable AEP pipeline (opt-in [wind])
solar_resource/                pvlib solar producer for hybrid multi-tech (opt-in [solar])
app/                           Web service (FastAPI), async jobs (arq/Redis), lender report
api/                           Legacy standalone FastAPI routers (predecessor to app/api/)
scripts/                       Operational, CI, build, and analysis tooling
scenarios/  conf/  config/     Scenario configs, Hydra defaults, and default parameters
tests/                         Test suite (unit, contract, integration, lint/architecture)
docs/                          Documentation (see the index below)
```

Notes on the layout:

- The top-level `monte_carlo/` directory holds Monte Carlo scenario YAML files, not engine
  code; the engine is `analytics/mc/`.
- Generated outputs (CSV, Excel, PNG, JSON) are written to a git-ignored `exports/`- or
  `_out/`-style directory; those are runtime artifacts, not source.
- There are two FastAPI surfaces: the current web service under `app/api/`, and a legacy
  standalone `api/` package retained for backward compatibility.

For a complete, per-module reference (purpose, design reasoning, and academic grounding for
every package), see [docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md).

## Key features

### Financial modelling

- Multi-tranche debt (USD DFI, USD commercial, LKR local) with grace periods and interest
  during construction.
- Cash flow analysis: CFADS, debt service coverage, and operating cash flows.
- Returns: project IRR, equity IRR, and project and equity NPV, with a robust IRR solver that
  returns no value rather than a fabricated one on non-convergence.
- Risk metrics: DSCR (minimum, average), LLCR, PLCR, and break-even analysis.
- Sri Lanka tax: 30% corporate income tax, plant/civil split depreciation, tax-loss
  carry-forward, and interest and dividend withholding.

### Analytics

- Scenario analysis across base, optimistic, and pessimistic cases.
- Sensitivity: single-factor tornado and variance-based global sensitivity (Sobol first-order
  and total, Morris elementary effects, PAWN) via SALib.
- Monte Carlo: Latin Hypercube baseline with optional Sobol QMC, optional rank correlation
  (Iman-Conover) and Gaussian copula, and CASPER lender risk blocks (P50/P90/P95, CVaR,
  breach probability).

### Wind and solar resource

- Wind: ERA5/Copernicus ingestion to Weibull (k, A) fit to gross AEP to PyWake wake loss to an
  IEC 61400-15-2 uncertainty budget yielding P50/P75/P90 energy. The finance stack consumes a
  frozen wind-export JSON, so lender runs need no Copernicus credentials.
- Solar: a pvlib chain (clear-sky, transposition, cell temperature) with an
  IEC 61724-1 / IEA-PVPS Task 13 P50/P75/P90 build-up, at parity with the wind side.

### GIS-for-wind siting (opt-in `[gis]`)

A raster/vector siting toolchain under `analytics/gis/` (GeoTIFF export, Global Wind Atlas
and DEM ingest, land-cover roughness, exclusion masks, RIX terrain diagnostic, and an
AHP-weighted MCDM suitability surface). All imports are guarded, so the base install needs no
GIS stack. See [docs/GIS_GEOTIFF_EXPORT.md](docs/GIS_GEOTIFF_EXPORT.md).

### Grid interconnection screening (opt-in `[grid]`, advisory)

An in-house design-stage grid study under `analytics/grid/` (short-circuit ratio at the point
of connection via pandapower, ANDES ride-through, reactive/voltage and harmonics screens).
Default-off and additive, so committed scenarios stay result-identical.

This is a screening/design-stage study only, not the utility-accepted bankable grid-connection
study. CEB/NSCC require PSS/E or PowerFactory run against their confidential grid base case,
and the OEM binaries feed that study. Cases the model cannot assert are reported as an explicit
"not run". See [docs/GRID_INTERFACE_SCHEMA.md](docs/GRID_INTERFACE_SCHEMA.md).

### Export and reporting

- Timestamped CSV/Excel exports and machine-readable JSON/JSONL.
- Board-ready executive workbooks (`analytics/executive_workbook.py`).
- An HTML lender report (Jinja2, a core dependency) with an optional PDF backend (WeasyPrint,
  opt-in `[report]`). The HTML report always renders; the PDF raises a clear dependency error
  when WeasyPrint is absent.

## Development

The [Development Guide](docs/DEVELOPMENT.md) covers setup, the quality gates, the contribution
workflow, and governance in full. In brief:

```bash
make lint        # ruff (mandatory) + black/isort (advisory locally)
make type        # strict, complete-annotation mypy over the engine surface
make security    # bandit SAST + pip-audit of the pinned lock
make test        # pytest -n auto with the 95% coverage floor
```

All parameters live in YAML with strict validation; IRR/NPV/WACC are isolated to
`finance/`; analytics evaluate only through the contract gateway; and every change flows
through branch to pull request to green CI to self-merge (never a direct commit to `main`).
See [go_with_the_flow_rules_v3_0_clean.csv](go_with_the_flow_rules_v3_0_clean.csv) (GWTF v3.0,
69 rules) for the complete standards.

## Deployment

The web service is a FastAPI application (`app.api.main:app`) with an optional durable async
job worker (arq + Redis) and an HTML/PDF report layer. The operator runbook for a local Docker
Compose stack and a production Fly.io deployment is [docs/deploy/DEPLOY.md](docs/deploy/DEPLOY.md).

The production deployment runs the durable async path: the `web` process plus an `arq`
worker backed by managed Redis (`DUTCHBAY_JOBS_BACKEND=redis`), per the runbook (restored in
#943 after a brief interim in-process posture). The image is built and boot-checked by the
`docker-build` CI workflow; deployment itself is a manual `fly deploy`.

## Optional install extras

The base install runs the finance engine and Hydra CLI with no heavy scientific stack. Each
extra below is opt-in and its imports fail at call time (not import time) with an actionable
message when the extra is absent.

| Extra | Installs | Powers |
| --- | --- | --- |
| `[dev]` | ruff/black/isort, mypy + stubs, bandit, pip-audit, pytest stack, hypothesis, libcst, build | The full CI gate |
| `[api]` | fastapi, uvicorn | The HTTP API (`api/`, `app/`) |
| `[dashboard]` | streamlit | The sensitivity dashboard |
| `[wind]` | cdsapi, xarray, netcdf4, windpowerlib, turbine-models, py-wake | The ERA5 to bankable-AEP wind pipeline |
| `[micrositing]` | topfarm | The micro-siting layout optimizer |
| `[solar]` | pvlib | The solar producer for hybrid multi-tech |
| `[pareto]` | pymoo | NSGA-II multi-objective search |
| `[gis]` | rasterio, shapely | The GIS-for-wind siting toolchain |
| `[ingestion]` | markitdown[pdf], pdfplumber, pymupdf | Governed PDF conversion, extraction, inspection, and rendering |
| `[report]` | weasyprint, reportlab, geopandas, contextily | The PDF lender report and location/context maps |
| `[jobs]` | arq, redis | The durable cross-process async job worker |
| `[grid]` | pandapower==3.3.0, andes, opendssdirect.py | The grid interconnection screening study (advisory) |

Install `[grid]` under the constraints file to protect the core numeric pins:
`PIP_CONSTRAINT=constraints.txt pip install -e ".[grid]"`.

## Documentation

- [Development Guide](docs/DEVELOPMENT.md) — setup, gates, workflow, governance
- [Module Reference](docs/MODULE_REFERENCE.md) — per-module purpose, reasoning, and grounding
- [Deployment Runbook](docs/deploy/DEPLOY.md) — Docker Compose and Fly.io
- [Architecture](docs/PIPELINE_ARCHITECTURE.md) — pipeline and technical design
- [Analytics Integration](docs/ANALYTICS_INTEGRATION.md) — analytics module details
- [CASPER / Monte Carlo](docs/CASPER_MC_INTEGRATION.md) — tail-risk and MC integration
- [FX / WACC / Equity](docs/FX_WACC_EQUITY_INTEGRATION_v14.md) — multi-currency and discounting
- [Wind Interface Schema](docs/WIND_INTERFACE_SCHEMA.md) and [AEP Provenance](docs/AEP_PROVENANCE.md)
- [Grid Interface Schema](docs/GRID_INTERFACE_SCHEMA.md) — grid-screening config (advisory)
- [Release Process](RELEASING.md) and [Security Policy](SECURITY.md)

## Project information

- Project: Dutch Bay 150 MW wind farm
- Location: Sri Lanka
- Technology: onshore wind (with optional BESS and hybrid solar)
- Status: financial modelling and development phase
- Repository: [arunakulat/dutchbay-epc-model](https://github.com/arunakulat/dutchbay-epc-model)

## License

Proprietary. All rights reserved.

Version: see the `VERSION` file (the single source of truth; currently 15.3.0).
