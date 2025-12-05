import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows


@pytest.mark.smoke
def test_build_annual_rows_cfads_aliases_and_keys():
    """
    Guardrail test:
    - build_annual_rows produces at least one row
    - key CFADS fields exist
    - cfads_final_lkr and cfads_risk_adjusted_lkr stay in lockstep
    """

    # Use a known-good scenario that already passes schema_guard + pipeline
    config = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")

    rows = build_annual_rows(config=config)

    # We expect a proper project life horizon, not an empty list
    assert rows, "Expected at least one annual cashflow row"

    required_keys = {
        "year",
        "revenue_lkr",
        "opex_lkr",
        "ebitda_lkr",
        "pretax_cfads_lkr",
        "posttax_cfads_lkr",
        "cfads_final_lkr",
        "cfads_risk_adjusted_lkr",
        "risk_haircut_pct",
        "risk_haircut_amount_lkr",
        "cfads_usd",
    }

    for row in rows:
        # 1) All key fields present
        missing = required_keys.difference(row.keys())
        assert not missing, f"Row {row.get('year')} missing keys: {missing}"

        # 2) Alias stays in lockstep with canonical CFADS
        assert row["cfads_final_lkr"] == pytest.approx(
            row["cfads_risk_adjusted_lkr"]
        ), f"CFADS alias mismatch in year {row.get('year')}"
