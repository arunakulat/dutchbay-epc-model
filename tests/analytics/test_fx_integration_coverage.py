"""Coverage tests for analytics.fx.fx_integration (v14R6).

Drives integrate_fx_into_scenario_result() end-to-end with a synthetic
ScenarioResult plus a real FX config, asserting:
  - the happy path overlays fx_block / fx_curve / fx_risk_profile onto a fresh
    ScenarioResult while leaving the base financial fields untouched;
  - each documented TypeError raise (scenario_result / config / debt_result /
    annual_rows of the wrong type);
  - the ValueError wrapper when an underlying FX builder rejects its inputs.

Deterministic and offline: the FX builders read only the config-sourced
reference rate (config/defaults.yaml); no network, cdsapi, or matplotlib.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.contracts_v14 import ScenarioResult
from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
)
from analytics.fx.fx_integration import integrate_fx_into_scenario_result

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _annual_rows() -> List[Dict[str, Any]]:
    """Two well-formed annual rows with mixed-currency debt and LKR revenue."""
    return [
        {
            "year": 2025,
            "total_debt_lkr": 1000.0,
            "total_debt_usd": 2000.0,
            "total_debt_cny": 0.0,
            "revenue_lkr": 500.0,
            "revenue_usd": 0.0,
            "interest_lkr": 80.0,
            "principal_lkr": 50.0,
        },
        {
            "year": 2026,
            "total_debt_lkr": 900.0,
            "total_debt_usd": 1800.0,
            "total_debt_cny": 300.0,
            "revenue_lkr": 550.0,
            "revenue_usd": 0.0,
            "interest_lkr": 72.0,
            "principal_lkr": 50.0,
        },
    ]


def _fx_config() -> Dict[str, Any]:
    """An explicit FX config section exercising the builder knobs."""
    return {
        "FX": {
            "strategy": "hedged",
            "base_currency": "USD",
            "reporting_currency": "USD",
            "fx_match_ratio": 50.0,
            "hedging_coverage_pct": 30.0,
            "revenue_currencies": ["LKR"],
            "notes": "lender case",
            "curve": {
                "lkr_usd": [330.0, 335.0],
                "lkr_cny": [46.0, 47.0],
                "source": "stress",
                "notes": "two-year curve",
            },
        }
    }


def _debt_result() -> Dict[str, Any]:
    return {"tranches": {"T1": {"currency": "USD"}, "T2": {"currency": "LKR"}}}


def _base_result() -> ScenarioResult:
    """A minimal, FX-free ScenarioResult to overlay onto."""
    return ScenarioResult(
        scenario_name="cov-fx",
        config_path=str(LENDER_SCENARIO),
        project_npv=-31_900_000.0,
        project_irr=0.0543,
        dscr_series=[1.30, 1.45, 1.60],
        min_dscr=1.30,
        max_debt_usd=120_000_000.0,
        discount_rate_used=0.0818,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_overlay_populates_fx_fields_and_preserves_base() -> None:
    """The overlay returns a NEW ScenarioResult with FX blocks set; base intact."""
    base = _base_result()
    out = integrate_fx_into_scenario_result(
        scenario_result=base,
        config=_fx_config(),
        debt_result=_debt_result(),
        annual_rows=_annual_rows(),
    )

    # A fresh, distinct object (immutability: base is untouched).
    assert isinstance(out, ScenarioResult)
    assert out is not base
    assert base.fx_block is None
    assert base.fx_curve is None
    assert base.fx_risk_profile is None

    # FX fields are populated with the right contract types.
    assert isinstance(out.fx_block, FXStructuredBlock)
    assert isinstance(out.fx_curve, FXCurveOutput)
    assert isinstance(out.fx_risk_profile, FXRiskProfile)

    # The block reflects the driving config.
    assert out.fx_block.strategy == "hedged"
    assert out.fx_block.debt_tranches == {"T1": "USD", "T2": "LKR"}

    # Base financial fields survive the round-trip.
    assert out.scenario_name == "cov-fx"
    assert out.project_irr == pytest.approx(0.0543)
    assert out.min_dscr == pytest.approx(1.30)
    assert out.dscr_series == [1.30, 1.45, 1.60]


def test_overlay_uses_default_strategy_when_fx_absent() -> None:
    """A config with no FX section still produces a valid blended block."""
    out = integrate_fx_into_scenario_result(
        scenario_result=_base_result(),
        config={},
        debt_result=_debt_result(),
        annual_rows=_annual_rows(),
    )
    assert isinstance(out.fx_block, FXStructuredBlock)
    assert out.fx_block.strategy == "blended"


# ---------------------------------------------------------------------------
# TypeError guards (CESSPIT fail-fast validation)
# ---------------------------------------------------------------------------


def test_scenario_result_wrong_type_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="scenario_result must be ScenarioResult"):
        integrate_fx_into_scenario_result(
            scenario_result={"not": "a ScenarioResult"},
            config=_fx_config(),
            debt_result=_debt_result(),
            annual_rows=_annual_rows(),
        )


def test_config_wrong_type_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="config must be Mapping"):
        integrate_fx_into_scenario_result(
            scenario_result=_base_result(),
            config=["not", "a", "mapping"],  # type: ignore[arg-type]
            debt_result=_debt_result(),
            annual_rows=_annual_rows(),
        )


def test_debt_result_wrong_type_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="debt_result must be Mapping"):
        integrate_fx_into_scenario_result(
            scenario_result=_base_result(),
            config=_fx_config(),
            debt_result=["not", "a", "mapping"],  # type: ignore[arg-type]
            annual_rows=_annual_rows(),
        )


def test_annual_rows_wrong_type_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="annual_rows must be Sequence"):
        integrate_fx_into_scenario_result(
            scenario_result=_base_result(),
            config=_fx_config(),
            debt_result=_debt_result(),
            annual_rows=42,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# ValueError wrapper (FX computation failure propagation)
# ---------------------------------------------------------------------------


def test_fx_builder_failure_is_wrapped_as_valueerror() -> None:
    """A malformed annual row makes a builder raise; the wrapper restates it."""
    bad_rows = [{"year": "not-a-number", "total_debt_usd": object()}]
    with pytest.raises(ValueError, match="FX computation failed"):
        integrate_fx_into_scenario_result(
            scenario_result=_base_result(),
            config=_fx_config(),
            debt_result=_debt_result(),
            annual_rows=bad_rows,
        )
