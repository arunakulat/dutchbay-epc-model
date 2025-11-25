import os
import glob
import yaml
import json
import matplotlib.pyplot as plt
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

def plot_batch(directory, metric='dscr_series'):
    files = get_scenario_files(directory)
    if not files:
        print("No scenarios found!")
        return

    plt.figure(figsize=(10, 6))
    for file in files:
        label = os.path.splitext(os.path.basename(file))[0]
        try:
            config = load_config(file)
            annual_rows = build_annual_rows_v14(config)
            debt = apply_debt_layer(config, annual_rows)
            if metric == 'dscr_series':
                ys = debt.get('dscr_series', [])
                xs = list(range(1, len(ys)+1))
                plt.plot(xs, ys, marker='o', label=label)
            elif metric == 'debt_outstanding':
                ys = debt.get('debt_outstanding', [])
                xs = list(range(1, len(ys)+1))
                plt.plot(xs, ys, marker='o', label=label)
            elif metric == 'cfads':
                ys = [row['cfads_usd'] for row in annual_rows]
                xs = [row['year'] for row in annual_rows]
                plt.plot(xs, ys, marker='o', label=label)
        except Exception as e:
            print(f"Error plotting {label}: {e}")

    plt.xlabel('Year')
    if metric == 'dscr_series':
        plt.ylabel('DSCR')
        plt.title('Project DSCR per Scenario')
    elif metric == 'debt_outstanding':
        plt.ylabel('Debt Outstanding (USD)')
        plt.title('Debt Outstanding per Scenario')
    elif metric == 'cfads':
        plt.ylabel('CFADS (USD)')
        plt.title('CFADS per Scenario')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Plot DSCR, Debt, or CFADS across scenarios")
    parser.add_argument("--dir", "-d", type=str, required=True, help="Scenario directory")
    parser.add_argument("--metric", "-m", type=str, choices=['dscr_series', 'debt_outstanding', 'cfads'], default='dscr_series', help="Metric to plot")
    args = parser.parse_args()
    plot_batch(args.dir, metric=args.metric)


