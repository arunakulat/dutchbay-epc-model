"""
Test that cfads_haircut_pct (lender-case risk adjustment) is correctly applied.
"""

from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows


@pytest.mark.parametrize(
    "scenario_path, expected_haircut_pct",
    [
        ("scenarios/dutchbay_lendercase_2025Q4.yaml", 0.10),
    ],
)
def test_cfads_risk_haircut_applied_to_posttax_cfads(
    scenario_path: str, expected_haircut_pct: float
) -> None:
    """Ensure cfads_haircut_pct is actually applied to post-tax CFADS."""
    cfg_path = Path(scenario_path)
    assert cfg_path.exists(), f"Scenario not found: {cfg_path}"

    config = load_scenario_config(str(cfg_path))

    risk_cfg = config.get("risk_adjustment") or {}
    haircut_pct = float(risk_cfg.get("cfads_haircut_pct", 0.0))

    assert haircut_pct == pytest.approx(
        expected_haircut_pct
    ), "Unexpected haircut in scenario config"

    rows = build_annual_rows(config)

    assert len(rows) > 0, "Expected at least one cashflow row"

    for i, row in enumerate(rows):
        year = row["year"]
        posttax = row["posttax_cfads_lkr"]
        cfads_final = row["cfads_final_lkr"]
        haircut_amt = row["risk_haircut_amount_lkr"]
        haircut_pct_row = row["risk_haircut_pct"]

        assert haircut_pct_row == pytest.approx(
            haircut_pct, abs=1e-6
        ), f"Year {year}: haircut % mismatch"

        expected_haircut_amt = posttax * haircut_pct
        assert haircut_amt == pytest.approx(
            expected_haircut_amt, abs=1.0
        ), f"Year {year}: haircut amount mismatch"

        expected_cfads_final = posttax - haircut_amt
        assert cfads_final == pytest.approx(
            expected_cfads_final, abs=1.0
        ), f"Year {year}: final CFADS mismatch"

        assert cfads_final == pytest.approx(
            posttax * (1.0 - haircut_pct), abs=1.0
        ), f"Year {year}: alternative haircut check failed"
