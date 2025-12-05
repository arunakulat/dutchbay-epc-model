from __future__ import annotations

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
    """Ensure cfads_haircut_pct is actually applied to post-tax CFADS.

    With cfads_haircut_pct = 0.1, we expect for every operating year:

        cfads_final_lkr == 0.9 * posttax_cfads
        risk_haircut_amount == 0.1 * posttax_cfads

    This is a behavioural test; it does not care about the absolute level of
    CFADS, only that the haircut logic is wired correctly.
    """
    cfg_path = Path(scenario_path)
    assert cfg_path.exists(), f"Scenario not found: {cfg_path}"

    config = load_scenario_config(str(cfg_path))

    # Pull haircut from config so the test will fail if someone changes YAML
    risk_cfg = config.get("risk_adjustment") or {}
    haircut_pct = float(risk_cfg.get("cfads_haircut_pct", 0.0))

    assert haircut_pct == pytest.approx(
        expected_haircut_pct
    ), "Unexpected haircut in scenario config"

    cashflow = build_annual_rows(config)
    rows = cashflow["annual_rows"]

    # Sanity: there should be at least a few operating years
    assert len(rows) >= 5

    for row in rows:
        posttax_cfads = float(row["posttax_cfads"])
        cfads_final_lkr = float(row["cfads_final_lkr"])
        risk_amount = float(row["risk_haircut_amount"])
        row_pct = float(row["risk_haircut_pct"])

        # All rows should carry the same pct (for this scenario)
        assert row_pct == pytest.approx(haircut_pct)

        # If post-tax CFADS is numerically zero (degenerate stress case),
        # both the haircut amount and final CFADS should also be ~0.
        if abs(posttax_cfads) < 1e-6:
            assert abs(risk_amount) < 1e-4
            assert abs(cfads_final_lkr) < 1e-4
            continue

        expected_amount = posttax_cfads * haircut_pct
        expected_final = posttax_cfads * (1.0 - haircut_pct)

        assert risk_amount == pytest.approx(
            expected_amount, rel=1e-9
        ), "Risk haircut amount not applied correctly"

        assert cfads_final_lkr == pytest.approx(
            expected_final, rel=1e-9
        ), "Final CFADS after haircut not consistent with base * (1 - pct)"
