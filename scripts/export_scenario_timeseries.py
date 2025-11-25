import os
import glob
import yaml
import json
import csv
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
        raise ValueError("Unsupported file extension: " + path)

def get_scenario_files(directory):
    pats = ['*.json', '*.yaml', '*.yml']
    files = []
    for pat in pats:
        files.extend(glob.glob(os.path.join(directory, pat)))
    return files

def export_timeseries(directory, outfile="scenario_timeseries.csv"):
    files = get_scenario_files(directory)
    all_rows = []
    for file in files:
        scen_name = os.path.splitext(os.path.basename(file))[0]
        try:
            config = load_config(file)
            annual_rows = build_annual_rows_v14(config)
            debt = apply_debt_layer(config, annual_rows)
            dscr_series = debt.get("dscr_series", [])
            debt_series = debt.get("debt_outstanding", [])
            # Assumes annual_rows[year-1] corresponds to each year
            for i, row in enumerate(annual_rows):
                rec = {
                    "scenario": scen_name,
                    "year": row.get("year", i + 1),
                    "label": row.get("label", ""),
                    "revenue_usd": row.get("revenue_usd"),
                    "opex_usd": row.get("opex_usd"),
                    "cfads": row.get("cfads_usd"),
                    "dscr": dscr_series[i] if i < len(dscr_series) else "",
                    "debt_outstanding": debt_series[i] if i < len(debt_series) else ""
                }
                all_rows.append(rec)
        except Exception as e:
            print(f"Error exporting {scen_name}: {e}")

    keys = ["scenario", "year", "label", "revenue_usd", "opex_usd", "cfads", "dscr", "debt_outstanding"]
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Full annual timeseries exported to: {outfile}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export all scenario timeseries to long-format CSV")
    parser.add_argument("--dir", "-d", type=str, required=True, help="Scenario directory")
    parser.add_argument("--csv", "-o", type=str, default="scenario_timeseries.csv", help="Output CSV filename")
    args = parser.parse_args()
    export_timeseries(args.dir, args.csv)


