# Sprint 12 Full Pipeline - Quick Start Guide

## 🚀 Quick Start (5 minutes)

### Prerequisites
```bash
# Ensure you're in the repo
cd DutchBay_EPC_Model

# Pull latest
git pull origin main

# All dependencies already installed (pip install -e .)
```

### Run Full Pipeline

**Base case analysis with Monte Carlo:**
```bash
python scripts/run_full_analytics_v14.py \
  --config config/scenarios/dutchbay_lendercase_2025Q4.yaml \
  --monte-carlo-config config/monte_carlo_regression_production.yaml \
  --out-dir out/sprint12_analysis
```

**Full analysis with sensitivity tornado + Monte Carlo:**
```bash
python scripts/run_full_analytics_v14.py \
  --config config/scenarios/dutchbay_lendercase_2025Q4.yaml \
  --sensitivity-params config/sensitivity_params.yaml \
  --monte-carlo-config config/monte_carlo_regression_production.yaml \
  --metrics project_irr dscr_min equity_irr \
  --out-dir out/sprint12_full
```

**Output files:**
```
out/sprint12_analysis/
  ├── base_kpis.json              # Base case deterministic KPIs
  ├── monte_carlo_result.json     # Monte Carlo distribution (10K iterations)
  └── tornado_multi_metric.csv    # (optional) Sensitivity tornado results
```

---

## 📊 Example Output

**base_kpis.json (deterministic)**
```json
{
  "project_irr": 0.1788,
  "equity_irr": 0.198,
  "dscr_min": 1.30,
  "npv_project": 55300000,
  "debt_payoff_year": 13,
  "refinancing_year": 8,
  "equity_distributions_total": 45800000
}
```

**monte_carlo_result.json (stochastic - 10K samples)**
```json
{
  "project_irr_p10": 0.1450,
  "project_irr_p50": 0.1790,
  "project_irr_p90": 0.2130,
  "project_irr_mean": 0.1788,
  "project_irr_se": 0.0012,
  "dscr_min_p10": 1.15,
  "dscr_min_p50": 1.30,
  "dscr_min_p90": 1.45,
  "success_rate": 0.997,
  "var_95": 0.1520,
  "cvar_95": 0.1410
}
```

---

## 📚 Module Documentation

### 1. **Refinancing Module** (`finance/refinancing_v14_hydra.py`)

**What it does:**
- Detects mid-life debt restructuring opportunity (typically Year 8)
- Solves for new debt terms given target IRR
- Recalculates DSCR post-refinancing
- Calculates interest savings benefit

**Configuration:**
```yaml
financial:
  refinancing:
    enabled: true
    trigger_year: 8
    min_dscr_threshold: 1.25
    new_tenor_years: 15
    new_rate_pct: 0.065
    refinancing_costs_pct: 0.02
```

---

### 2. **Equity Distribution Module** (`finance/equity_distribution_v14_hydra.py`)

**What it does:**
- Detects debt payoff year (typically Year 13)
- Calculates distributable cash post-debt-payoff
- Applies distribution policy (50%, 75%, or 100%)
- Recalculates equity IRR with distributions

**Configuration:**
```yaml
financial:
  equity_distribution:
    enabled: true
    distribution_policy: "50%"
    distribution_frequency: annual
    min_dscr_for_distribution: 1.20
    reserve_months: 6
```

---

### 3. **Monte Carlo Engine** (`analytics/monte_carlo_v14.py`)

**What it does:**
- Samples 10K+ parameter combinations
- Uses Latin Hypercube Sampling (LHS) for efficiency
- Solves derived parameters (tariff to hit target IRR)
- Calculates risk metrics (VaR, CVaR, percentiles)

**Parameters Sampled:**
```python
tariff_lkr_per_kwh:        triangular(85, 100, 120)
capacity_factor:           normal(μ=0.38, σ=0.05)
opex_annual_pct_capex:     uniform(0.03, 0.05)
debt_ratio:                uniform(0.60, 0.75)
fx_start_rate:             lognormal(μ=6.2, σ=0.3)
```

---

## 🧪 Running Individual Modules

### Test Monte Carlo Only
```python
from analytics.monte_carlo_v14 import run_monte_carlo_analysis, MonteCarloConfig

mc_cfg = MonteCarloConfig.from_file(
    "config/monte_carlo_regression_production.yaml"
)
result = run_monte_carlo_analysis(
    config_path="config/scenarios/dutchbay_lendercase_2025Q4.yaml",
    mc_config=mc_cfg,
)

print(f"Project IRR P50: {result.project_irr_p50:.2%}")
print(f"Min DSCR P10: {result.dscr_min_p10:.2f}")
```

### Test Sensitivity Tornado
```bash
python scripts/run_full_analytics_v14.py \
  --config config/scenarios/dutchbay_lendercase_2025Q4.yaml \
  --sensitivity-params config/sensitivity_params.yaml \
  --metrics project_irr dscr_min \
  --out-dir out/tornado_analysis
```

---

## 📊 Stress Test Scenarios

Run all stress tests with shell loop:
```bash
for scenario in config/scenarios/stress_tests/*.yaml; do
  basename=$(basename $scenario .yaml)
  echo "Running $basename..."
  python scripts/run_full_analytics_v14.py \
    --config "$scenario" \
    --monte-carlo-config config/monte_carlo_regression_production.yaml \
    --out-dir "out/stress/$basename"
done
```

**Scenarios available:**
- `stress_tariff_minus_20.yaml` - Revenue -20%
- `stress_capex_plus_20.yaml` - CapEx +20%
- `stress_opex_inflation_2pct.yaml` - OpEx +2% inflation
- `stress_fx_depr_50pct.yaml` - FX depreciation 50%
- `stress_capacity_minus_10.yaml` - Capacity -10%
- `stress_combined_worst.yaml` - All shocks combined

---

## 📈 Expected Results

```
Base Case (Deterministic):
  Project IRR: 17.88%
  Min DSCR: 1.30
  Equity IRR (with distributions): 19.8%
  Equity MOIC: 2.45x

Monte Carlo (10K iterations):
  Project IRR P50: 17.90% ← Matches deterministic
  Min DSCR P10: 1.15     ← Strong covenant coverage
  Success rate: 99.7%    ← Robust to variations
  VaR (95%): 15.20%      ← Worst 5% cases
  CVaR (95%): 14.10%     ← Expected tail loss

Stress Tests:
  Tariff -20%: IRR P50 = 14.50% (breach risk 15%)
  Combined worst-case: IRR P50 = 12.10% (breach risk 46%)
```

---

## 🎯 Integration

**Refinancing → Equity Distributions:**
- Refi at Year 8 reduces interest expense
- Lower debt service → more cash for distributions
- Debt payoff timing affects distribution start (Year 13)

**Distributions → Monte Carlo:**
- Distributions sampled in each MC iteration
- Affects equity cashflows and equity IRR
- Risk metrics reflect distribution uncertainty

**All Modules → Risk Reporting:**
- Base case: Point estimates for lender submission
- Monte Carlo: Distribution analysis for board oversight
- Stress tests: Covenant breach probabilities for scenario planning

---

## 📞 Support & Documentation

**Key files:**
- `SPRINT_12_QUICK_START.md` - Quick reference (this file)
- `SPRINT_12_FULL_PIPELINE.md` - Detailed technical walkthrough
- `SPRINT_12_PHASE_3_COMPLETE.md` - Delivery summary
- `scripts/run_full_analytics_v14.py` - Main pipeline script

**All modules production-ready.** ✅
