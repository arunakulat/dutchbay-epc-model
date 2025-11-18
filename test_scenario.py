import os
import sys
import json
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dutchbay_v14chat.finance.cashflow import build_annual_rows_v14
from dutchbay_v14chat.finance.debt import apply_debt_layer

def test_scenario(path):
    print(f"\nTesting: {path}")
    try:
        if path.endswith('.json'):
            with open(path, 'r') as f:
                config = json.load(f)
        elif path.endswith(('.yaml', '.yml')):
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
        
        print(f"  Config loaded: {list(config.keys())}")
        
        annual_rows = build_annual_rows_v14(config)
        print(f"  Annual rows generated: {len(annual_rows)} years")
        
        debt_result = apply_debt_layer(config, annual_rows)
        print(f"  Debt layer applied: OK")
        
        print(f"  SUCCESS!")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    scenarios = [
        './scenarios/example_a.yaml',
        './scenarios/example_b.json',
        './scenarios/edge_extreme_stress.yaml',
        './scenarios/zz_bad.yaml',
    ]
    
    success_count = 0
    for scenario in scenarios:
        if os.path.exists(scenario):
            if test_scenario(scenario):
                success_count += 1
    
    print(f"\n\nSummary: {success_count}/{len(scenarios)} scenarios processed successfully")
