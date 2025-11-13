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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dutchbay_v13_scenario_runner",
        description="DutchBay EPC financial runner and coverage summary (LLCR/PLCR/DSCR).",
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

    # Build model scenario
    annual_rows = build_annual_rows(params)
    debt_results = apply_debt_layer(params, annual_rows)
    cfads_series = [row['cfads_usd'] for row in annual_rows]
    debt_outstanding_series = debt_results.get('debt_outstanding', [0.0]*len(annual_rows))
    llcr_result = calculate_llcr(cfads_series, debt_outstanding_series, discount_rate=0.10)
    plcr_result = calculate_plcr(cfads_series, debt_outstanding_series, discount_rate=0.10)
    dscr_series = [row['cfads_usd']/row['debt_service'] if row.get('debt_service', 0) > 0 else None for row in annual_rows]
    dscr_summary = summarize_dscr(dscr_series)

    # Print coverage ratio summary
    print("\n===== COVERAGE RATIOS SUMMARY =====")
    print(f"LLCR MIN: {llcr_result['llcr_min']:.2f}x	LLCR AVG: {llcr_result['llcr_avg']:.2f}x")
    print(f"PLCR MIN: {plcr_result['plcr_min']:.2f}x\tPLCR AVG: {plcr_result['plcr_avg']:.2f}x")
    print(f"DSCR: {dscr_summary['dscr_min']} min | {dscr_summary['dscr_avg']} avg\n")

    # Write CSV output
    csv_path = outputs_dir / 'coverage_ratios_summary.csv'
    with open(csv_path, 'w') as f:
        f.write('Year,CFADS_USD,Debt_Outstanding,LLCR,PLCR\n')
        for i, (cf, do, ll, pl) in enumerate(zip(cfads_series, debt_outstanding_series, llcr_result['llcr_series'], plcr_result['plcr_series'])):
            f.write(f"{i+1},{cf},{do},{ll},{pl}\n")
    print(f"Coverage ratios exported: {csv_path}")

    # Return 0 = success
    return 0

if __name__ == "__main__":
    sys.exit(main())
