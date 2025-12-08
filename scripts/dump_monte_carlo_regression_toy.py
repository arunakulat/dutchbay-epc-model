from __future__ import annotations

import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# Repo bootstrap: ensure we can import `analytics.*`
# ──────────────────────────────────────────────────────────────

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.monte_carlo_v14 import run_monte_carlo  # type: ignore[import]

# Adjust this if your canonical lender config path changes
BASE_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
MC_CONFIG = REPO_ROOT / "config" / "monte_carlo_regression_toy.yaml"


def main() -> None:
    """
    Run the MC regression config once and dump the key metrics and a ready-to-paste
    regression_expectations block for config/monte_carlo_regression_toy.yaml.
    """
    if not BASE_CONFIG.exists():
        raise SystemExit(f"Base scenario config not found: {BASE_CONFIG}")

    if not MC_CONFIG.exists():
        raise SystemExit(f"Monte Carlo config not found: {MC_CONFIG}")

    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG),
        base_config_path=str(BASE_CONFIG),
    )

    if "base_case" not in results:
        raise SystemExit(
            f"No 'base_case' scenario in MC results: {list(results.keys())}"
        )

    mc = results["base_case"]

    irr_p50 = mc.project_irr_p50
    npv_p50 = mc.project_npv_p50
    dscr_p10 = mc.dscr_min_p10

    print("=== Monte Carlo regression run (seed=42) ===")
    print(f"Scenario          : {mc.scenario_name}")
    print(f"P50 IRR           : {irr_p50:.6f}")
    print(f"P50 NPV (LKR?)    : {npv_p50:.2f}")
    print(f"P10 DSCR_min      : {dscr_p10:.6f}")
    print()

    # Build narrow but sane bands around the observed values
    irr_margin = 0.002
    npv_margin = abs(npv_p50) * 0.02 if npv_p50 != 0 else 1.0
    dscr_margin = 0.02

    print("=== regression_expectations snippet (YAML) ===")
    print("regression_expectations:")
    print("  scenario_name: base_case")
    print("  metrics:")
    print("    project_irr_p50:")
    print(f"      lower: {irr_p50 - irr_margin:.6f}")
    print(f"      upper: {irr_p50 + irr_margin:.6f}")
    print("    project_npv_p50_lkr:")
    print(f"      lower: {npv_p50 - npv_margin:.2f}")
    print(f"      upper: {npv_p50 + npv_margin:.2f}")
    print("    dscr_min_p10:")
    print(f"      lower: {dscr_p10 - dscr_margin:.6f}")
    print(f"      upper: {dscr_p10 + dscr_margin:.6f}")


if __name__ == "__main__":
    main()
