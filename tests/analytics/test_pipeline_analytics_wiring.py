"""The analytics wrapper must drive the FINANCE pipeline, and fail loud otherwise.

Regression for the wrong-import bug: ``pipeline_analytics_v14`` imported the
*wind* ``run_v14_pipeline`` (no ``annual_rows`` / ``debt_result``), so its
returns/risk analytics silently always returned ``None``.
"""

from __future__ import annotations

import pytest

import analytics.pipeline_analytics_v14 as mod
from analytics.pipeline_analytics_v14 import run_v14_pipeline_with_analytics

LENDER = "scenarios/dutchbay_lendercase_2025Q4.yaml"


def test_wrapper_drives_finance_pipeline_and_runs_risk() -> None:
    """With the finance pipeline wired, risk analytics actually execute."""
    result = run_v14_pipeline_with_analytics(
        config=LENDER, validation_mode="strict", enable_returns=True, enable_risk=True
    )
    # The finance result shape flows through at top level.
    assert result.get("annual_rows"), "finance annual_rows missing"
    assert "debt_result" in result and "kpis" in result
    ar = result["analytics_result"]
    # Risk analytics now run (were silently None under the wind wiring).
    risk = ar["risk_analysis"]
    assert risk is not None
    assert "var_cvar" in risk and "percentiles" in risk
    # Returns analytics run on the canonical lender scenario (Financing_Terms schema).
    returns = ar["returns_analysis"]
    assert returns is not None
    assert "project_returns" in returns


def test_wrapper_fails_loud_on_non_finance_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A base pipeline that returns a non-finance shape must fail loud, not silently."""
    monkeypatch.setattr(mod, "run_v14_pipeline", lambda **_kw: {"status": "success"})
    with pytest.raises(RuntimeError, match="finance keys"):
        run_v14_pipeline_with_analytics(config=LENDER, enable_risk=True)
