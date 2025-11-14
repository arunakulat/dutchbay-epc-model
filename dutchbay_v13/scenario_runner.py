import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import yaml
from dutchbay_v13.finance.returns import calculate_all_returns

def main():
    yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
    with open(yaml_path) as f:
        params = yaml.safe_load(f)
    # Calculate all returns with new logic
    returns = calculate_all_returns(params)
    # CLI reporting, can be adapted for CSV/markdown
    print("\n========= FULL SCENARIO RUNNER (GRID/REG/RISK/TAX/DSCR) =========\n")
    print(f"Project NPV (10%): ${returns['project']['project_npv']:,.2f}")
    print(f"Equity NPV (12%): ${returns['equity']['equity_npv']:,.2f}")
    print(f"Project IRR: {returns['project']['project_irr']*100:.2f}%")
    print(f"Equity IRR: {returns['equity']['equity_irr']*100:.2f}%")
    print("\n--- Year|Debt Service|Net CFADS|Taxes| ")
    print("Yr | Debt Svc (M) | Net CFADS (M) | Tax (M)")
    for i, (ds, cf, tx) in enumerate(zip(returns['debt_service'], returns['cfads'], returns['tax'])):
        print(f"{i+1:2d} | {ds/1e6:12.2f} | {cf/1e6:14.2f} | {tx/1e6:8.2f}")

if __name__ == "__main__":
    main()
