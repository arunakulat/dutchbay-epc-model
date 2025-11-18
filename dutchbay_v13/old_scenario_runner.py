import os
import sys
import json
import glob
import csv
import yaml
from dutchbay_v14chat.finance.cashflow import build_annual_rows_v14
from dutchbay_v14chat.finance.debt import apply_debt_layer

def load_config(path):
    if path.endswith('.json'):
        with open(path, 'r') as f:
            return json.load(f)
    elif path.endswith(('.yaml', '.yml')):
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    else:
        raise ValueError("Unsupported file extension for scenario: " + path)

def get_scenario_files(directory):
    pats = ['*.json', '*.yaml', '*.yml']
    files = []
    for pat in pats:
        files.extend(glob.glob(os.path.join(directory, pat)))
    return files

def run_scenarios(scenarios_dir, csv_outfile="scenario_results.csv"):
    files = get_scenario_files(scenarios_dir)
    if not files:
        print("No scenario files found.")
        sys.exit(1)
    results = []
    print(f"Running scenarios from: {scenarios_dir}")
    for sc_path in files:
        try:
            config = load_config(sc_path)
            rows = build_annual_rows_v14(config)
            debt = apply_debt_layer(config, rows)
            kpis = {
                "scenario": os.path.basename(sc_path),
                "timeline_periods": debt.get("timeline_periods"),
                "min_dscr": debt.get("dscr_min"),
                "total_idc_capitalized": debt.get("total_idc_capitalized"),
                "max_debt_outstanding": max(debt.get("debt_outstanding", [0])),
                "final_year_cfads": rows[-1].get("cfads_usd", None),
                "grace_years": debt.get("grace_periods")
            }
            print(f"[{kpis['scenario']}]: {kpis}")
            results.append(kpis)
        except Exception as e:
            print(f"Error running scenario {sc_path}: {repr(e)}")
    # Save summary results
    if results:
        keys = list(results[0].keys())
        with open(csv_outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nScenario summary saved to: {csv_outfile}\n")
    else:
        print("No successful scenario runs.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch scenario runner for v14 model")
    parser.add_argument("--dir", "-d", type=str, required=True, help="Directory with scenario YAML or JSON files")
    parser.add_argument("--csv", "-o", type=str, default="scenario_results.csv", help="Output CSV file for KPIs")
    args = parser.parse_args()
    run_scenarios(args.dir, args.csv)
