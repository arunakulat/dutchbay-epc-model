"""Independent oracle and negative-control tests for carbon credits (#1428)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from finance.carbon_credits_v14 import (
    CarbonCreditConfigError,
    evaluate_carbon_credit_scenarios,
    evaluate_carbon_credit_schedule,
    resolve_carbon_credit_contract,
)


def _placeholder_enabled_cfg(**overrides: Any) -> dict[str, Any]:
    path = Path("conf/carbon_credits_placeholder.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = dict(data["carbon_credits"])
    cfg["enabled"] = True
    cfg.update(overrides)
    return cfg


def test_default_off_omitted_and_disabled_produce_zero_revenue() -> None:
    """Without accepted evidence or when disabled, revenue stays strictly zero."""
    for raw in (None, {}, {"enabled": False}):
        contract = resolve_carbon_credit_contract(raw)
        sched = evaluate_carbon_credit_schedule(contract)
        assert sched.enabled is False
        assert sched.covenant_eligible is False
        assert sched.included_in_canonical_kpis is False
        assert sched.total_net_revenue_usd == 0.0
        assert sched.rows == ()


def test_placeholder_config_defaults_to_disabled() -> None:
    path = Path("conf/carbon_credits_placeholder.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    contract = resolve_carbon_credit_contract(data["carbon_credits"])
    assert contract.enabled is False
    assert contract.covenant_eligible is False
    assert contract.included_in_canonical_kpis is False


def test_closed_form_oracle_reconciles_units_delay_costs_tax_and_share() -> None:
    """Independent closed-form oracle checks estimated, issued, sold & net USD."""
    cfg = _placeholder_enabled_cfg(
        project_life_years=10,
        gross_eligible_tco2e_per_year=100_000.0,
        deduction_pct=5.0,
        rejection_rate_pct=10.0,
        issuance_delay_years=2,
        price_usd_per_tco2e=20.0,
        issuance_cost_usd_per_tco2e=1.0,
        tax_rate_pct=20.0,
        revenue_share_pct=10.0,
    )
    contract = resolve_carbon_credit_contract(cfg)
    assert contract.is_placeholder is True
    assert contract.data_status == "synthetic_placeholder"
    assert contract.claim_authority == "none_placeholder_only"

    sched = evaluate_carbon_credit_schedule(contract)
    assert sched.covenant_eligible is False
    assert sched.included_in_canonical_kpis is False
    assert len(sched.rows) == 10

    # Years 1 and 2 have 0 issued due to 2-year issuance delay; years 3..10 (8 years) issue.
    assert sched.rows[0].issued_tco2e == 0.0
    assert sched.rows[1].issued_tco2e == 0.0
    expected_yearly_issued = 100_000.0 * 0.95 * 0.90  # 85,500 tCO2e
    expected_total_issued = 8 * expected_yearly_issued
    expected_gross_rev = expected_total_issued * 20.0
    expected_cost = expected_total_issued * 1.0
    expected_pre_tax = expected_gross_rev - expected_cost
    expected_tax = expected_pre_tax * 0.20
    expected_after_tax = expected_pre_tax - expected_tax
    expected_share = expected_after_tax * 0.10
    expected_net = expected_gross_rev - expected_cost - expected_tax - expected_share

    assert sched.total_estimated_tco2e == pytest.approx(10 * 100_000.0)
    assert sched.total_issued_tco2e == pytest.approx(expected_total_issued)
    assert sched.total_sold_tco2e == pytest.approx(expected_total_issued)
    assert sched.total_gross_revenue_usd == pytest.approx(expected_gross_rev)
    assert sched.total_issuance_cost_usd == pytest.approx(expected_cost)
    assert sched.total_tax_usd == pytest.approx(expected_tax)
    assert sched.total_revenue_share_usd == pytest.approx(expected_share)
    assert sched.total_net_revenue_usd == pytest.approx(expected_net)


def test_stress_scenarios_cover_price_volume_delay_and_rejection() -> None:
    base = _placeholder_enabled_cfg()
    results = evaluate_carbon_credit_scenarios(
        base,
        [
            ("base", {}),
            ("low_price", {"price_usd_per_tco2e": 6.0}),
            ("low_volume", {"gross_eligible_tco2e_per_year": 75_000.0}),
            ("long_delay", {"issuance_delay_years": 5}),
            ("high_rejection", {"rejection_rate_pct": 50.0}),
        ],
    )
    base_net = results["base"].total_net_revenue_usd
    assert results["low_price"].total_net_revenue_usd < base_net
    assert results["low_volume"].total_net_revenue_usd < base_net
    assert results["long_delay"].total_net_revenue_usd < base_net
    assert results["high_rejection"].total_net_revenue_usd < base_net


@pytest.mark.parametrize(
    "bad_override",
    [
        {"covenant_eligible": True},
        {"included_in_canonical_kpis": True},
        {"gross_eligible_tco2e_per_year": -1.0},
        {"deduction_pct": 105.0},
        {"rejection_rate_pct": -5.0},
        {"issuance_delay_years": -1},
        {"registry_name": ""},
        {"methodology_id": ""},
        {"placeholder_data": False},  # missing accepted_evidence_ref
    ],
)
def test_negative_controls_fail_loud(bad_override: dict[str, Any]) -> None:
    cfg = _placeholder_enabled_cfg(**bad_override)
    with pytest.raises(CarbonCreditConfigError):
        resolve_carbon_credit_contract(cfg)
