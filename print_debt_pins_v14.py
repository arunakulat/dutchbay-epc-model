# tools/print_debt_pins_v14.py
from pathlib import Path

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt


def dump(name: str) -> None:
    cfg = load_scenario_config(str(Path("scenarios") / name))
    rows = build_annual_rows(cfg)
    result = plan_debt(annual_rows=rows, config=cfg)

    print(f"\n=== {name} ===")
    for k in ("lkr", "usd", "dfi"):
        tr = result[k]
        print(f"{k}: principal={tr['principal']:.3f}, idc={tr['idc']:.3f}")
    print(f"total_idc={result['total_idc']:.3f}")


if __name__ == "__main__":
    dump("dutchbay_lendercase_2025Q4.yaml")
    dump("edge_extreme_stress.yaml")
# EOF
