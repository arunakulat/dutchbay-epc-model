#!/usr/bin/env python3
"""
Tornado Sensitivity Analysis Script - P0-2C
DutchBay V13 - Executive presentation-grade tornado charts

Calculates sensitivity of Equity IRR, Project IRR, and Equity NPV
to key parameter variations and generates tornado diagrams.

Author: DutchBay V13 Team, Nov 2025
Version: 1.0
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import matplotlib.pyplot as plt
from dutchbay_v13.finance.returns import calculate_all_returns
from dutchbay_v13.visualization.sensitivity_tornado import TornadoSensitivityAnalyzer
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("DUTCHBAY V13 - TORNADO SENSITIVITY ANALYSIS (P0-2C)")
print("Executive-Grade Parameter Impact Analysis")
print("=" * 80)

# Load configuration
yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

# Calculate base case
print("\n--- Base Case Calculation ---")
base_returns = calculate_all_returns(params)
base_equity_irr = base_returns['equity']['equity_irr']
base_project_irr = base_returns['project']['project_irr']
base_equity_npv = base_returns['equity']['equity_npv']

print(f"Base Equity IRR: {base_equity_irr*100:.2f}%")
print(f"Base Project IRR: {base_project_irr*100:.2f}%")
print(f"Base Equity NPV: ${base_equity_npv:,.0f}")

# Initialize analyzer
print("\n--- Initializing Sensitivity Analyzer ---")
analyzer = TornadoSensitivityAnalyzer(base_returns, params)

# Define sensitivity parameters
# Format: (param_name, yaml_path, low_%, high_%, metric)
sensitivity_specs = [
    ("Capacity Factor", ['project', 'capacity_factor'], -0.05, +0.05, 'equity/equity_irr'),
    ("PPA Tariff (LKR/kWh)", ['tariff', 'lkr_per_kwh'], -0.10, +0.10, 'equity/equity_irr'),
    ("OPEX (USD/yr)", ['opex', 'usd_per_year'], -0.15, +0.15, 'equity/equity_irr'),
    ("CAPEX (USD)", ['capex', 'usd_total'], -0.08, +0.08, 'equity/equity_irr'),
    ("Grid Loss %", ['regulatory', 'grid_loss_pct'], -0.01, +0.03, 'equity/equity_irr'),
]

print(f"\n--- Running {len(sensitivity_specs)} Sensitivity Scenarios ---")

# Calculate sensitivities for Equity IRR
equity_irr_sens = {}
for spec in sensitivity_specs:
    param_name, param_path, low_pct, high_pct, metric = spec
    try:
        sens_result = analyzer.calculate_sensitivity(
            param_name,
            param_path,
            low_pct,
            high_pct,
            calculate_all_returns,
            metric
        )
        equity_irr_sens[param_name] = sens_result
        print(f"✓ {param_name}: {sens_result['total_swing']*100:.2f}% swing")
    except Exception as e:
        print(f"✗ {param_name}: {str(e)}")

print("\n✓ Sensitivity calculations complete")

# Generate visualizations and reports
outputs_dir = Path(__file__).parent.parent / 'outputs'
outputs_dir.mkdir(parents=True, exist_ok=True)

print("\n--- Generating Tornado Chart ---")
fig_tornado = analyzer.tornado_chart(
    equity_irr_sens,
    metric_name='Equity IRR (%)',
    title='DutchBay 150MW Wind Farm - Sensitivity Tornado Chart (Equity IRR)',
    output_path=outputs_dir / 'tornado_chart_equity_irr.png'
)
print(f"✓ Tornado chart saved: {outputs_dir / 'tornado_chart_equity_irr.png'}")

# Generate sensitivity table
print("\n--- Generating Sensitivity Table ---")
sensitivity_table = analyzer.sensitivity_table(equity_irr_sens, metric_type='IRR')
table_path = outputs_dir / 'sensitivity_analysis.csv'
sensitivity_table.to_csv(table_path, index=False)
print(f"✓ Sensitivity table saved: {table_path}")

# Print table to console
print("\n--- SENSITIVITY ANALYSIS RESULTS ---\n")
print(sensitivity_table.to_string(index=False))

# Generate markdown report
print("\n--- Generating Markdown Report ---")
report_path = outputs_dir / 'sensitivity_report.md'
report = analyzer.generate_summary_report(equity_irr_sens, output_path=report_path)
print(f"✓ Report saved: {report_path}")

# Print summary
print("\n" + "=" * 80)
print("SENSITIVITY ANALYSIS COMPLETE")
print("=" * 80)

sorted_sens = sorted(equity_irr_sens.items(), key=lambda x: x[1]['total_swing'], reverse=True)

print("\n--- PARAMETER RANKING (by Equity IRR Impact) ---\n")
for i, (param_name, sens) in enumerate(sorted_sens, 1):
    swing_pct = sens['total_swing'] * 100
    print(f"{i}. {param_name:.<30} {swing_pct:>6.2f}% swing")

print("\n--- TOP 3 VALUE DRIVERS ---\n")
for i, (param_name, sens) in enumerate(sorted_sens[:3], 1):
    print(f"{i}. {param_name}")
    print(f"   Range: {sens['low_metric']*100:.2f}% to {sens['high_metric']*100:.2f}%")
    print(f"   Base: {sens['base_metric']*100:.2f}%")
    print()

print("✓ Outputs generated in: /outputs/")
print("✓ Files:")
print("  - tornado_chart_equity_irr.png")
print("  - sensitivity_analysis.csv")
print("  - sensitivity_report.md")
print("\n✓ Ready for board/IC presentations")
print("=" * 80)

# Keep plot open
plt.show()
