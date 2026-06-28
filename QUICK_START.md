# Quick Start — DutchBay EPC Model

> A lender/DFI-grade project-finance model for a 150 MW wind farm (Kalpitiya, Sri Lanka).
> Canonical execution path is **v14**; all CLIs are **Hydra** (`key=value`, not `--flags`).

## Setup

```bash
git clone https://github.com/arunakulat/dutchbay-epc-model.git
cd dutchbay-epc-model

python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt   # pinned reproducibility lock
pip install -e ".[dev]"            # dev/CI toolchain (from pyproject — the abstract source of truth)
# Optional extras: wind/ERA5, solar, gis, report, api, dashboard, jobs — e.g.:
# pip install -e ".[wind]"
```

## Run the four routines

```bash
# 1) Finance pipeline (canonical lender case)
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml

# 2) Monte Carlo (reads scenario monte_carlo.parameters; deterministic with seed)
python -m analytics.cli.cli_monte_carlo_hydra \
  config=scenarios/dutchbay_lendercase_2025Q4.yaml n_trials=200 seed=42

# 3) Sensitivity tornado
python -m analytics.cli.cli_sensitivity_hydra \
  config=scenarios/dutchbay_lendercase_2025Q4.yaml output_dir=_out/sensitivity

# 4) Optimization sweep (Python API)
python -c "from analytics.optimization_v14 import optimize_parameter; \
print(optimize_parameter('scenarios/dutchbay_lendercase_2025Q4.yaml', \
param_path='Financing_Terms.debt_ratio', objective_key='equity_irr', \
lower=0.30, upper=0.70, n_steps=9, constraint_key='min_dscr', constraint_min=1.30).best)"
```

> Note: run the `analytics/cli/*` entrypoints with `python -m ...` so the
> `analytics` package is importable.

## Python API

```python
from analytics.evaluation_v14 import evaluate_with_overrides

kpis = evaluate_with_overrides("scenarios/dutchbay_lendercase_2025Q4.yaml")
print(kpis["project_irr"], kpis["min_dscr"], kpis["discount_rate_used"])
```

## Tests

```bash
pytest tests/                                   # full suite
pytest tests/finance/ tests/integration/ -q     # finance + integration
mypy finance/ analytics/ --ignore-missing-imports
```

## Where things live

| Concern | Module |
|---|---|
| Evaluation gateway | `analytics/evaluation_v14.py` (`evaluate_with_overrides`) |
| Pipeline orchestration | `analytics/pipeline_v14_enhanced.py` (`run_v14_pipeline`) |
| KPIs | `analytics/core/metrics.py` |
| IRR / NPV | `finance/irr.py` (ARCH-02 canonical) |
| WACC | `finance/wacc_v14.py` (ARCH-02 canonical) |
| Monte Carlo | `analytics/mc/engine.py` |
| Governance ruleset | `go_with_the_flow_rules_v3_0_clean.csv` (GWTF v3.0) |

See `README.md` for the architecture overview and `RELEASING.md` for the release process.
