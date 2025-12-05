import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows


def test_risk_adjustment_cfads_haircut_is_applied():
    """
    Ensure risk_adjustment.cfads_haircut_pct in config:
      - is picked up as risk_haircut_pct (decimal),
      - actually reduces CFADS vs post-tax CFADS.
    """
    config = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")

    # Force a clean, obvious haircut for the test
    config.setdefault("risk_adjustment", {})
    config["risk_adjustment"]["cfads_haircut_pct"] = 10  # 10%

    rows = build_annual_rows(config=config)
    assert rows, "Expected at least one annual cashflow row"

    for row in rows:
        pct = row["risk_haircut_pct"]
        post_tax = row["posttax_cfads_lkr"]
        final = row["cfads_final_lkr"]

        # 1) Mapped as decimal (0.10), not 10.0
        assert pct == pytest.approx(0.10), "risk_haircut_pct should be 0.10 for 10%"

        # 2) Haircut actually reduces CFADS
        assert final < post_tax
        expected_final = post_tax * (1 - pct)
        assert final == pytest.approx(expected_final)
