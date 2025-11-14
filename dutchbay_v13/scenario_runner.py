from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional, List
import sys
import yaml
import argparse
import os
from dutchbay_v13.finance.metrics import calculate_llcr, calculate_plcr, summarize_dscr
from dutchbay_v13.finance.debt import apply_debt_layer
from dutchbay_v13.finance.cashflow import build_annual_rows
from dutchbay_v13.finance.returns import calculate_all_returns

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dutchbay_v13_scenario_runner",
        description="DutchBay EPC financial runner with coverage ratios and returns (LLCR/PLCR/IRR/NPV).",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=str,
        help="YAML configuration file (e.g., full_model_variables_updated.yaml)",
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs",
        type=str,
        help="Directory for scenario outputs.",
    )
    args = parser.parse_args(argv)

    outputs_dir = Path(args.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    config_path = Path(args.config)
    with open(config_path) as f:
        params = yaml.safe_load(f)

    # Discount rates from YAML
    project_discount_rate = params.get('returns', {}).get('project_discount_rate', 0.10)
    equity_discount_rate = params.get('returns', {}).get('equity_discount_rate', 0.12)
    project_life = params.get('returns', {}).get('project_life_years', 20)

    # Build model scenario
    annual_rows = build_annual_rows(params)
    debt_results = apply_debt_layer(params, annual_rows)
    cfads_series = [row['cfads_usd'] for row in annual_rows]
    debt_outstanding_series = debt_results.get('debt_outstanding', [0.0]*len(annual_rows))
    debt_service_series = debt_results.get('debt_service_total', [0.0]*len(annual_rows))
    # Coverage ratios
    llcr_result = calculate_llcr(cfads_series, debt_outstanding_series, discount_rate=0.10)
    plcr_result = calculate_plcr(cfads_series, debt_outstanding_series, discount_rate=0.10)
    dscr_series = [row['cfads_usd']/row['debt_service'] if row.get('debt_service', 0) > 0 else None for row in annual_rows]
    dscr_summary = summarize_dscr(dscr_series)
    # Returns (YAML driven)
    capex = params.get('capex', {}).get('usd_total', 150e6)
    debt_ratio = params.get('Financing_Terms', {}).get('debt_ratio', 0.70)
    returns = calculate_all_returns(
        cfads_series,
        debt_service_series,
        capex,
        debt_ratio=debt_ratio,
        project_discount_rate=project_discount_rate,
        equity_discount_rate=equity_discount_rate,
        project_life=project_life
    )
    # Print coverage ratio summary
    print("\n===== COVERAGE RATIOS SUMMARY =====")
    print(f"LLCR MIN: {llcr_result['llcr_min']:.2f}x\tLLCR AVG: {llcr_result['llcr_avg']:.2f}x")
    print(f"PLCR MIN: {plcr_result['plcr_min']:.2f}x\tPLCR AVG: {plcr_result['plcr_avg']:.2f}x")
    print(f"DSCR: {dscr_summary['dscr_min']} min | {dscr_summary['dscr_avg']} avg\n")
    # Print returns summary (NEW - YAML-driven)
    print("===== FINANCIAL RETURNS SUMMARY =====")
    if returns['project']['project_irr']:
        print(f"Project IRR: {returns['project']['project_irr']*100:.2f}%")
    else:
        print("Project IRR: N/A")
    print(f"Project NPV ({project_discount_rate*100:.1f}%): ${returns['project']['project_npv']:,.2f}")
    if returns['equity']['equity_irr']:
        print(f"Equity IRR: {returns['equity']['equity_irr']*100:.2f}%")
    else:
        print("Equity IRR: N/A")
    print(f"Equity NPV ({equity_discount_rate*100:.1f}%): ${returns['equity']['equity_npv']:,.2f}")
    print(f"Debt Ratio: {debt_ratio*100:.1f}%\n")
    # Write CSV output
    csv_path = outputs_dir / 'coverage_ratios_summary.csv'
    with open(csv_path, 'w') as f:
        f.write('Year,CFADS_USD,Debt_Outstanding,Debt_Service,LLCR,PLCR\n')
        for i, (cf, do, ll, pl) in enumerate(zip(cfads_series, debt_outstanding_series, llcr_result['llcr_series'], plcr_result['plcr_series'])):
            ds = debt_service_series[i] if i < len(debt_service_series) else 0
            f.write(f"{i+1},{cf},{do},{ds},{ll},{pl}\n")
    print(f"Coverage ratios exported: {csv_path}")
    # Return 0 = success
    return 0

if __name__ == "__main__":
    sys.exit(main())
