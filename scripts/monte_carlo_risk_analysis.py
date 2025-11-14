#!/usr/bin/env python3
"""
Monte Carlo Risk Analysis Script - P0-2B Tail Risk Analytics
DutchBay V13 - VaR/CVaR/Percentile/Covenant Breach Analysis

Runs 10,000+ Monte Carlo scenarios with correlated parameter perturbations and computes:
- VaR(95%), CVaR(95%)
- P10/P50/P90 percentile distribution
- Downside deviation and Sortino ratio
- Covenant breach probabilities (DSCR, LLCR, PLCR)
- Full result export to CSV

Author: DutchBay V13 Team, Nov 2025
Version: 1.0
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import numpy as np
import pandas as pd
from tqdm import tqdm
from dutchbay_v13.finance.returns import calculate_all_returns
from dutchbay_v13.finance.metrics import calculate_llcr, calculate_plcr
from dutchbay_v13.finance.risk_metrics import TailRiskAnalyzer
import time

print("=" * 80)
print("DUTCHBAY V13 - MONTE CARLO TAIL RISK ANALYSIS (P0-2B)")
print("VaR/CVaR | P10/P90 | Covenant Breach Probability")
print("=" * 80)

# Load YAML configuration
yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

# Monte Carlo configuration
mc_config = params.get('monte_carlo', {})
n_scenarios = mc_config.get('n_scenarios', 10000)
seed = mc_config.get('seed', 42)
np.random.seed(seed)

print(f"\n--- Monte Carlo Configuration ---")
print(f"Scenarios: {n_scenarios:,}")
print(f"Random seed: {seed}")

# Parameter perturbation settings
mc_params = mc_config.get('parameters', {})
cf_std = mc_params.get('capacity_factor_std', 0.05)
tariff_std = mc_params.get('tariff_lkr_std', 0.10)
opex_std = mc_params.get('opex_usd_std', 0.15)
capex_std = mc_params.get('capex_usd_std', 0.08)

# Base case values
base_cf = params['project']['capacity_factor']
base_tariff = params['tariff']['lkr_per_kwh']
base_opex = params['opex']['usd_per_year']
base_capex = params['capex']['usd_total']

print(f"\n--- Parameter Perturbations ---")
print(f"Capacity Factor: {base_cf:.1%} ± {cf_std:.1%}")
print(f"Tariff (LKR/kWh): {base_tariff:.2f} ± {tariff_std:.1%}")
print(f"OPEX (USD/yr): ${base_opex:,.0f} ± {opex_std:.1%}")
print(f"CAPEX (USD): ${base_capex:,.0f} ± {capex_std:.1%}")

# Correlation matrix (if provided, else independent)
corr_matrix = np.array(mc_params.get('correlation_matrix', np.eye(4)))

print(f"\n--- Generating Correlated Parameter Scenarios ---")
# Generate correlated samples
mean_vec = [0, 0, 0, 0]  # Zero mean for % perturbations
cov_matrix = np.diag([cf_std, tariff_std, opex_std, capex_std]) @ corr_matrix @ np.diag([cf_std, tariff_std, opex_std, capex_std])

perturbations = np.random.multivariate_normal(mean_vec, cov_matrix, n_scenarios)
print(f"✓ {n_scenarios:,} correlated parameter sets generated")

# Storage for results
equity_irr_results = []
project_irr_results = []
equity_npv_results = []
project_npv_results = []
dscr_min_results = []
llcr_min_results = []
plcr_min_results = []

print(f"\n--- Running {n_scenarios:,} Monte Carlo Scenarios ---")
start_time = time.time()

for i in tqdm(range(n_scenarios), desc="Scenarios", ncols=80):
    # Perturb parameters
    scenario_params = params.copy()
    scenario_params['project']['capacity_factor'] = max(0.1, base_cf * (1 + perturbations[i, 0]))
    scenario_params['tariff']['lkr_per_kwh'] = max(5, base_tariff * (1 + perturbations[i, 1]))
    scenario_params['opex']['usd_per_year'] = max(1e6, base_opex * (1 + perturbations[i, 2]))
    scenario_params['capex']['usd_total'] = max(50e6, base_capex * (1 + perturbations[i, 3]))
    
    # Run financial model
    try:
        returns = calculate_all_returns(scenario_params)
        
        equity_irr_results.append(returns['equity']['equity_irr'])
        project_irr_results.append(returns['project']['project_irr'])
        equity_npv_results.append(returns['equity']['equity_npv'])
        project_npv_results.append(returns['project']['project_npv'])
        
        # Calculate coverage ratios
        cfads = returns['cfads']
        ds = returns['debt_service']
        debt_out = returns['debt_outstanding']
        
        dscr_series = [cfads[y] / ds[y] if ds[y] > 1e-7 else 0 for y in range(len(ds))]
        dscr_min = min([d for d in dscr_series if d > 0], default=0)
        dscr_min_results.append(dscr_min)
        
        llcr = calculate_llcr(cfads, debt_out, discount_rate=0.10)
        plcr = calculate_plcr(cfads, debt_out, discount_rate=0.10)
        
        llcr_min_results.append(llcr['llcr_min'])
        plcr_min_results.append(plcr['plcr_min'])
        
    except Exception as e:
        # Handle failed scenarios gracefully
        equity_irr_results.append(np.nan)
        project_irr_results.append(np.nan)
        equity_npv_results.append(np.nan)
        project_npv_results.append(np.nan)
        dscr_min_results.append(np.nan)
        llcr_min_results.append(np.nan)
        plcr_min_results.append(np.nan)

elapsed = time.time() - start_time
print(f"\n✓ Completed in {elapsed:.1f}s ({n_scenarios/elapsed:.0f} scenarios/sec)")

# Convert to numpy arrays (filter NaN)
equity_irr_arr = np.array([x for x in equity_irr_results if not np.isnan(x)])
project_irr_arr = np.array([x for x in project_irr_results if not np.isnan(x)])
equity_npv_arr = np.array([x for x in equity_npv_results if not np.isnan(x)])
project_npv_arr = np.array([x for x in project_npv_results if not np.isnan(x)])
dscr_min_arr = np.array([x for x in dscr_min_results if not np.isnan(x)])
llcr_min_arr = np.array([x for x in llcr_min_results if not np.isnan(x)])
plcr_min_arr = np.array([x for x in plcr_min_results if not np.isnan(x)])

print(f"\n--- Scenario Results ---")
print(f"Valid scenarios: {len(equity_irr_arr):,} / {n_scenarios:,}")
print(f"Failed scenarios: {n_scenarios - len(equity_irr_arr):,}")

# Initialize risk analyzer
analyzer = TailRiskAnalyzer(confidence_level=0.95)

# Compute tail risk metrics
print(f"\n--- Computing Tail Risk Metrics ---")

equity_irr_risk = analyzer.calculate_var_cvar(equity_irr_arr, 'equity_irr')
equity_irr_percentiles = analyzer.percentile_analysis(equity_irr_arr, [10, 25, 50, 75, 90])
equity_irr_downside = analyzer.downside_risk(equity_irr_arr, target_return=0.12)

project_irr_risk = analyzer.calculate_var_cvar(project_irr_arr, 'project_irr')
project_irr_percentiles = analyzer.percentile_analysis(project_irr_arr, [10, 25, 50, 75, 90])

# Covenant breach probabilities
min_dscr_covenant = mc_config.get('min_dscr_covenant', 1.20)
min_llcr_covenant = mc_config.get('min_llcr_covenant', 1.25)
min_plcr_covenant = 1.40

dscr_breach_prob = (dscr_min_arr < min_dscr_covenant).sum() / len(dscr_min_arr)
llcr_breach_prob = (llcr_min_arr < min_llcr_covenant).sum() / len(llcr_min_arr)
plcr_breach_prob = (plcr_min_arr < min_plcr_covenant).sum() / len(plcr_min_arr)

print(f"✓ Risk metrics calculated")

# ============================================================================
# RESULTS DISPLAY
# ============================================================================

print("\n" + "=" * 80)
print("MONTE CARLO TAIL RISK ANALYSIS RESULTS")
print("=" * 80)

print("\n--- EQUITY IRR DISTRIBUTION ---")
print(f"Mean:              {equity_irr_arr.mean()*100:.2f}%")
print(f"Std Dev:           {equity_irr_arr.std()*100:.2f}%")
print(f"P10 (Downside):    {equity_irr_percentiles['p10']*100:.2f}%")
print(f"P50 (Median):      {equity_irr_percentiles['p50']*100:.2f}%")
print(f"P90 (Upside):      {equity_irr_percentiles['p90']*100:.2f}%")
print(f"VaR(95%):          {equity_irr_risk['var']*100:.2f}%")
print(f"CVaR(95%):         {equity_irr_risk['cvar']*100:.2f}%")
print(f"Probability < 12%: {equity_irr_downside['probability_below_target']*100:.1f}%")

print("\n--- PROJECT IRR DISTRIBUTION ---")
print(f"Mean:              {project_irr_arr.mean()*100:.2f}%")
print(f"Std Dev:           {project_irr_arr.std()*100:.2f}%")
print(f"P10:               {project_irr_percentiles['p10']*100:.2f}%")
print(f"P50:               {project_irr_percentiles['p50']*100:.2f}%")
print(f"P90:               {project_irr_percentiles['p90']*100:.2f}%")
print(f"VaR(95%):          {project_irr_risk['var']*100:.2f}%")
print(f"CVaR(95%):         {project_irr_risk['cvar']*100:.2f}%")

print("\n--- EQUITY NPV DISTRIBUTION ---")
equity_npv_risk = analyzer.calculate_var_cvar(equity_npv_arr, 'equity_npv')
equity_npv_percentiles = analyzer.percentile_analysis(equity_npv_arr, [10, 50, 90])
print(f"Mean:              ${equity_npv_arr.mean():,.2f}")
print(f"Std Dev:           ${equity_npv_arr.std():,.2f}")
print(f"P10:               ${equity_npv_percentiles['p10']:,.2f}")
print(f"P50:               ${equity_npv_percentiles['p50']:,.2f}")
print(f"P90:               ${equity_npv_percentiles['p90']:,.2f}")
print(f"VaR(95%):          ${equity_npv_risk['var']:,.2f}")
print(f"CVaR(95%):         ${equity_npv_risk['cvar']:,.2f}")

print("\n--- COVENANT BREACH PROBABILITIES ---")
print(f"DSCR < {min_dscr_covenant:.2f}x: {dscr_breach_prob*100:.2f}%")
print(f"LLCR < {min_llcr_covenant:.2f}x: {llcr_breach_prob*100:.2f}%")
print(f"PLCR < {min_plcr_covenant:.2f}x: {plcr_breach_prob*100:.2f}%")

# ============================================================================
# EXPORT RESULTS
# ============================================================================

outputs_dir = Path(__file__).parent.parent / 'outputs'
outputs_dir.mkdir(parents=True, exist_ok=True)

# Export full scenario results
mc_results = pd.DataFrame({
    'scenario': range(1, len(equity_irr_arr) + 1),
    'equity_irr': equity_irr_arr,
    'project_irr': project_irr_arr,
    'equity_npv': equity_npv_arr,
    'project_npv': project_npv_arr,
    'dscr_min': dscr_min_arr,
    'llcr_min': llcr_min_arr,
    'plcr_min': plcr_min_arr
})

csv_path = outputs_dir / 'monte_carlo_results.csv'
mc_results.to_csv(csv_path, index=False)
print(f"\n✓ Full results exported: {csv_path}")

# Export risk summary
risk_summary = pd.DataFrame([
    {
        'metric': 'Equity IRR',
        'mean': f"{equity_irr_arr.mean()*100:.2f}%",
        'std': f"{equity_irr_arr.std()*100:.2f}%",
        'p10': f"{equity_irr_percentiles['p10']*100:.2f}%",
        'p50': f"{equity_irr_percentiles['p50']*100:.2f}%",
        'p90': f"{equity_irr_percentiles['p90']*100:.2f}%",
        'var_95': f"{equity_irr_risk['var']*100:.2f}%",
        'cvar_95': f"{equity_irr_risk['cvar']*100:.2f}%"
    },
    {
        'metric': 'Project IRR',
        'mean': f"{project_irr_arr.mean()*100:.2f}%",
        'std': f"{project_irr_arr.std()*100:.2f}%",
        'p10': f"{project_irr_percentiles['p10']*100:.2f}%",
        'p50': f"{project_irr_percentiles['p50']*100:.2f}%",
        'p90': f"{project_irr_percentiles['p90']*100:.2f}%",
        'var_95': f"{project_irr_risk['var']*100:.2f}%",
        'cvar_95': f"{project_irr_risk['cvar']*100:.2f}%"
    },
    {
        'metric': 'Equity NPV',
        'mean': f"${equity_npv_arr.mean():,.0f}",
        'std': f"${equity_npv_arr.std():,.0f}",
        'p10': f"${equity_npv_percentiles['p10']:,.0f}",
        'p50': f"${equity_npv_percentiles['p50']:,.0f}",
        'p90': f"${equity_npv_percentiles['p90']:,.0f}",
        'var_95': f"${equity_npv_risk['var']:,.0f}",
        'cvar_95': f"${equity_npv_risk['cvar']:,.0f}"
    }
])

summary_path = outputs_dir / 'risk_summary.csv'
risk_summary.to_csv(summary_path, index=False)
print(f"✓ Risk summary exported: {summary_path}")

# Export covenant breach analysis
covenant_summary = pd.DataFrame([
    {'covenant': f'DSCR < {min_dscr_covenant:.2f}x', 'breach_probability': f"{dscr_breach_prob*100:.2f}%"},
    {'covenant': f'LLCR < {min_llcr_covenant:.2f}x', 'breach_probability': f"{llcr_breach_prob*100:.2f}%"},
    {'covenant': f'PLCR < {min_plcr_covenant:.2f}x', 'breach_probability': f"{plcr_breach_prob*100:.2f}%"}
])

covenant_path = outputs_dir / 'covenant_breach_probabilities.csv'
covenant_summary.to_csv(covenant_path, index=False)
print(f"✓ Covenant breach analysis exported: {covenant_path}")

print("\n" + "=" * 80)
print("MONTE CARLO TAIL RISK ANALYSIS COMPLETE")
print("=" * 80)
print(f"\n✓ {n_scenarios:,} scenarios completed in {elapsed:.1f}s")
print(f"✓ Equity IRR range: {equity_irr_arr.min()*100:.2f}% to {equity_irr_arr.max()*100:.2f}%")
print(f"✓ P10/P90 spread: {(equity_irr_percentiles['p90']-equity_irr_percentiles['p10'])*100:.2f}%")
print(f"✓ Covenant breach risk: {max(dscr_breach_prob, llcr_breach_prob, plcr_breach_prob)*100:.1f}%")
print("\n✓ Ready for equity investor/lender risk presentations")
print("=" * 80)
