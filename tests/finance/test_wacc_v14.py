from __future__ import annotations

from typing import Any, Dict

import pytest

from analytics.contracts_v14 import WaccComponents as WaccComponentsContract
from finance import wacc_v14


def _build_base_config() -> Dict[str, Any]:
    """Minimal v14-style config root we can hang a `wacc` block off."""
    return {
        "tax": {
            # Used as a fallback when wacc.tax_rate is omitted.
            "corporate_tax_rate_pct": 24.0,
        }
    }


def test_compute_wacc_from_config_fixed_mode_and_extract_rates() -> None:
    config: Dict[str, Any] = _build_base_config()
    config["wacc"] = {
        "discount_rate": 12.0,  # percent
        "prudential_spread_bps": 100,  # 100 bps = 1.0%
    }

    components = wacc_v14.compute_wacc_from_config(config)
    # Ensure we got a non-empty dict back
    assert components
    assert components["mode"] == "fixed"

    # 12% nominal, 13% prudential, no real WACC in fixed mode.
    assert components["wacc_nominal"] == pytest.approx(0.12)
    assert components["wacc_prudential"] == pytest.approx(0.13)
    assert components["wacc_real"] is None

    # Top-level helper should expose the same numbers.
    headline = wacc_v14.extract_wacc_rates(config)
    assert headline["wacc_nominal"] == pytest.approx(0.12)
    assert headline["wacc_prudential"] == pytest.approx(0.13)
    assert headline["wacc_real"] is None


def test_compute_wacc_from_config_capm_mode_matches_expected_values() -> None:
    """CAPM mode should produce a numerically coherent WACC surface.

    Parameters chosen here match the worked example:
    - Rf = 5%
    - MRP = 6%
    - β_asset = 0.8
    - D/V = 60%
    - Kd = 8%
    - Tax = 24%
    - Inflation = 2%
    - Prudential spread = 150 bps
    """
    config: Dict[str, Any] = _build_base_config()
    config["wacc"] = {
        "mode": "capm",
        "risk_free": 5.0,  # percent
        "market_premium": 6.0,  # percent
        "beta": 0.8,  # asset beta
        # Capital structure – 60% debt to value
        "gearing": 60.0,  # D/V in percent
        # Cost of debt
        "cost_of_debt": 8.0,  # percent
        # Tax override (would also come from config["tax"])
        "tax_rate": 24.0,  # percent
        # Optional extras
        "inflation_rate": 2.0,  # percent
        "prudential_spread_bps": 150,
    }

    components = wacc_v14.compute_wacc_from_config(config)
    assert components["mode"] == "capm"

    # Expected values from the formulae in the module docstring:
    # - β_equity ≈ 1.712
    # - Ke ≈ 15.271999999999998%
    # - WACC_nominal ≈ 9.7568%
    # - WACC_real ≈ 7.6047%
    # - WACC_prudential ≈ 11.2568%
    assert components["wacc_nominal"] == pytest.approx(0.097568, rel=1e-6)
    assert components["wacc_real"] == pytest.approx(0.076047, rel=1e-6)
    assert components["wacc_prudential"] == pytest.approx(0.112568, rel=1e-6)

    # Check that the capital structure and pricing pieces are also sane.
    assert components["target_debt_to_value"] == pytest.approx(0.60, rel=1e-6)
    assert components["target_equity_to_value"] == pytest.approx(0.40, rel=1e-6)
    assert components["cost_of_debt_pretax"] == pytest.approx(0.08, rel=1e-6)
    assert components["tax_rate"] == pytest.approx(0.24, rel=1e-6)
    assert components["inflation_rate"] == pytest.approx(0.02, rel=1e-6)

    # Top-level helper should surface the same headline rates.
    headline = wacc_v14.extract_wacc_rates(config)
    assert headline["wacc_nominal"] == pytest.approx(0.097568, rel=1e-6)
    assert headline["wacc_real"] == pytest.approx(0.076047, rel=1e-6)
    assert headline["wacc_prudential"] == pytest.approx(0.112568, rel=1e-6)


def test_extract_wacc_rates_without_wacc_block_returns_none() -> None:
    """If there is no `wacc` block, the helper should surface None values."""
    config: Dict[str, Any] = _build_base_config()
    # Intentionally no "wacc" key
    headline = wacc_v14.extract_wacc_rates(config)

    assert headline == {
        "wacc_nominal": None,
        "wacc_real": None,
        "wacc_prudential": None,
    }


def test_compute_wacc_from_config_is_compatible_with_analytics_contract() -> None:
    """Ensure the WACC dict surface matches analytics.contracts_v14.WaccComponents."""
    config: Dict[str, Any] = _build_base_config()
    config["wacc"] = {
        "mode": "capm",
        "risk_free": 5.0,
        "market_premium": 6.0,
        "beta": 0.8,
        "gearing": 60.0,
        "cost_of_debt": 8.0,
        "tax_rate": 24.0,
        "inflation_rate": 2.0,
        "prudential_spread_bps": 100,
    }

    components_dict = wacc_v14.compute_wacc_from_config(config)
    # This will fail loudly if any required field is missing or misnamed.
    contract_obj = WaccComponentsContract(**components_dict)

    # Sanity: contract object should carry the same nominal WACC.
    assert contract_obj.wacc_nominal == pytest.approx(
        components_dict["wacc_nominal"], rel=1e-9
    )
