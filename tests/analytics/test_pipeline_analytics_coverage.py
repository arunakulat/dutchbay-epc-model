"""Coverage harness for ``analytics.pipeline_analytics_v14``.

This exercises the analytics-pipeline wrapper (the #C3 wiring) against the LIVE
finance engine for the happy path, then drives every defensive / warning / stub
branch directly with crafted inputs. No source edits; deterministic.

Branches covered beyond the happy path:
- ``RETURNS_AVAILABLE`` / ``RISK_AVAILABLE`` False guards (module toggled).
- The ImportError fallbacks at import time (re-import with imports forced to
  fail) so the ``except ImportError`` lines execute.
- Missing ``annual_rows``, missing / short ``debt_service_total`` padding,
  and the broad ``except Exception`` paths in the returns/risk calculators.
- The fail-loud ``TypeError`` for a non-path (Mapping) config and the
  ``RuntimeError`` for a non-finance base result.
- That the dead sensitivity / Monte-Carlo / scenario-comparison stub toggles are
  gone (removed in #489 / PIPE-6) — no longer accepted, no longer in the result.

All repo paths resolve relative to THIS file (CI checks out the repo at a
different absolute root); writes (none here) would land under ``tmp_path``.
"""

from __future__ import annotations

import builtins
import importlib
from pathlib import Path
from typing import Any, Dict

import pytest

import analytics.pipeline_analytics_v14 as mod
from analytics.pipeline_analytics_v14 import (
    AnalyticsEnablement,
    EnhancedAnalyticsResult,
    run_v14_pipeline_with_analytics,
)
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Shared fixtures: a real cfg + a tiny finance-shaped base_result so the fast
# branch tests never pay for the heavy live pipeline.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_cfg() -> Dict[str, Any]:
    """The canonical lender scenario config (drives ReturnsConfig.from_yaml)."""
    return dict(load_scenario_config(str(LENDER)))


@pytest.fixture
def finance_base_result() -> Dict[str, Any]:
    """A minimal finance-shaped base result with the keys analytics consume."""
    return {
        "annual_rows": [
            {"cfads_final_lkr": 1.0e9},
            {"cfads_final_lkr": 1.1e9},
            {"cfads_final_lkr": 1.2e9},
        ],
        "debt_result": {"debt_service_total": [4.0e8, 4.0e8, 4.0e8]},
        "kpis": {},
    }


# ---------------------------------------------------------------------------
# Happy path against the LIVE engine: returns + risk actually run.
# ---------------------------------------------------------------------------
def test_live_pipeline_returns_and_risk() -> None:
    """The wrapper drives the finance engine and emits returns + risk blocks."""
    result = run_v14_pipeline_with_analytics(
        config=str(LENDER),
        validation_mode="strict",
        enable_returns=True,
        enable_risk=True,
    )
    # Finance shape flows through at top level.
    assert result.get("annual_rows"), "finance annual_rows missing"
    assert "debt_result" in result and "kpis" in result

    ar = result["analytics_result"]
    enabled = ar["analytics_enabled"]
    assert enabled["returns_enabled"] is True
    assert enabled["risk_enabled"] is True
    assert enabled["returns_available"] is mod.RETURNS_AVAILABLE
    assert enabled["risk_available"] is mod.RISK_AVAILABLE

    # Returns block: project + equity returns present, NPV finite.
    returns = ar["returns_analysis"]
    assert returns is not None
    assert "project_returns" in returns and "equity_returns" in returns
    assert returns["project_returns"]["project_npv"] == pytest.approx(
        returns["project_returns"]["project_npv"]
    )  # finite (not NaN)

    # Risk block: on a CFADS (cashflow) series the worse tail is LOWER cashflow,
    # so CVaR (mean of the adverse tail) is <= VaR (the tail-percentile value).
    risk = ar["risk_analysis"]
    assert risk is not None
    assert "var_cvar" in risk and "percentiles" in risk
    assert risk["var_cvar"]["cvar"] <= risk["var_cvar"]["var"]


def test_live_pipeline_no_analytics_when_flags_off() -> None:
    """With all flags off, no analytics blocks are produced (defaults None)."""
    result = run_v14_pipeline_with_analytics(config=str(LENDER))
    ar = result["analytics_result"]
    assert ar["returns_analysis"] is None
    assert ar["risk_analysis"] is None
    enabled = ar["analytics_enabled"]
    assert enabled["returns_enabled"] is False
    assert enabled["risk_enabled"] is False


# ---------------------------------------------------------------------------
# Fail-loud contract on the wrapper.
# ---------------------------------------------------------------------------
def test_inline_mapping_config_raises_typeerror() -> None:
    """A non-path (Mapping) config must fail loud with TypeError (line 442)."""
    with pytest.raises(TypeError, match="path-based config"):
        run_v14_pipeline_with_analytics(config={"some": "mapping"})


def test_non_finance_base_result_raises_runtimeerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A base result missing finance keys must fail loud with RuntimeError."""
    monkeypatch.setattr(mod, "run_v14_pipeline", lambda **_kw: {"status": "ok"})
    with pytest.raises(RuntimeError, match="finance keys"):
        run_v14_pipeline_with_analytics(config=str(LENDER), enable_risk=True)


# ---------------------------------------------------------------------------
# PIPE-6 (#489): the dead sensitivity / Monte-Carlo / scenario-comparison stub
# toggles were removed (they silently returned None). Pin that they are gone and
# the result surface no longer advertises them.
# ---------------------------------------------------------------------------
def test_removed_stub_toggles_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    finance_base_result: Dict[str, Any],
) -> None:
    """The removed stub flags are no longer accepted, and the result surface drops them."""
    monkeypatch.setattr(
        mod, "run_v14_pipeline", lambda **_kw: dict(finance_base_result)
    )
    monkeypatch.setattr(mod, "load_scenario_config", lambda _p: {})

    for dead_flag in (
        "enable_sensitivity",
        "enable_monte_carlo",
        "enable_scenario_comparison",
    ):
        with pytest.raises(TypeError):
            run_v14_pipeline_with_analytics(config=str(LENDER), **{dead_flag: True})

    result = run_v14_pipeline_with_analytics(config=str(LENDER), enable_returns=False)
    ar = result["analytics_result"]
    assert set(ar["analytics_enabled"]) == {
        "returns_enabled",
        "returns_available",
        "risk_enabled",
        "risk_available",
    }
    for dropped in (
        "sensitivity_analysis",
        "monte_carlo_analysis",
        "scenario_comparison",
    ):
        assert dropped not in ar


# ---------------------------------------------------------------------------
# _calculate_returns_analysis: defensive branches.
# ---------------------------------------------------------------------------
def test_returns_unavailable_returns_none(
    monkeypatch: pytest.MonkeyPatch, finance_base_result: Dict[str, Any]
) -> None:
    """RETURNS_AVAILABLE False -> warn + None (lines 207-208)."""
    monkeypatch.setattr(mod, "RETURNS_AVAILABLE", False)
    assert mod._calculate_returns_analysis(finance_base_result, {}) is None


def test_returns_no_annual_rows_returns_none() -> None:
    """No annual_rows -> warn + None (lines 216-217)."""
    assert mod._calculate_returns_analysis({"annual_rows": []}, {}) is None


def test_returns_empty_debt_service_uses_zeros(real_cfg: Dict[str, Any]) -> None:
    """Empty debt_service_total -> zero-filled series (lines 225-226)."""
    base = {
        "annual_rows": [{"cfads_final_lkr": 1.0e9}, {"cfads_final_lkr": 1.1e9}],
        "debt_result": {"debt_service_total": []},
    }
    out = mod._calculate_returns_analysis(base, real_cfg)
    assert out is not None
    assert out.project_returns is not None


def test_returns_short_debt_service_is_padded(real_cfg: Dict[str, Any]) -> None:
    """debt_service_total shorter than CFADS -> padded with zeros (line 231)."""
    base = {
        "annual_rows": [
            {"cfads_final_lkr": 1.0e9},
            {"cfads_final_lkr": 1.1e9},
            {"cfads_final_lkr": 1.2e9},
        ],
        # one entry vs three CFADS years -> while-loop padding runs.
        "debt_result": {"debt_service_total": [4.0e8]},
    }
    out = mod._calculate_returns_analysis(base, real_cfg)
    assert out is not None
    assert out.equity_returns is not None


def test_returns_bad_config_caught_returns_none(
    finance_base_result: Dict[str, Any],
) -> None:
    """A config that breaks ReturnsConfig.from_yaml -> except path -> None (251-253)."""
    # Missing capex/fx/financing/returns keys -> ReturnsConfig.from_yaml raises,
    # caught by the broad except.
    assert mod._calculate_returns_analysis(finance_base_result, {}) is None


# ---------------------------------------------------------------------------
# _calculate_risk_analysis: defensive branches.
# ---------------------------------------------------------------------------
def test_risk_unavailable_returns_none(
    monkeypatch: pytest.MonkeyPatch, finance_base_result: Dict[str, Any]
) -> None:
    """RISK_AVAILABLE False -> warn + None (lines 262-263)."""
    monkeypatch.setattr(mod, "RISK_AVAILABLE", False)
    assert mod._calculate_risk_analysis(finance_base_result, {}) is None


def test_risk_no_annual_rows_returns_none() -> None:
    """No annual_rows -> warn + None (lines 268-269)."""
    assert mod._calculate_risk_analysis({"annual_rows": []}, {}) is None


def test_risk_happy_path_cvar_le_var(finance_base_result: Dict[str, Any]) -> None:
    """Risk on a CFADS series: adverse-tail CVaR <= VaR (lower cashflow is worse)."""
    out = mod._calculate_risk_analysis(finance_base_result, {})
    assert out is not None
    assert out["var_cvar"]["cvar"] <= out["var_cvar"]["var"]
    assert "percentiles" in out


def test_risk_exception_caught_returns_none(
    monkeypatch: pytest.MonkeyPatch, finance_base_result: Dict[str, Any]
) -> None:
    """An analyzer failure is caught -> None (lines 314-316)."""

    class _Boom:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            raise ValueError("boom")

    monkeypatch.setattr(mod, "TailRiskAnalyzer", _Boom)
    assert mod._calculate_risk_analysis(finance_base_result, {}) is None


# ---------------------------------------------------------------------------
# Contract sanity (frozen pydantic models).
# ---------------------------------------------------------------------------
def test_enablement_defaults() -> None:
    """AnalyticsEnablement defaults: only the live returns/risk toggles remain (#489)."""
    e = AnalyticsEnablement()
    assert e.returns_enabled is False
    assert e.risk_enabled is False
    # The dead sensitivity / MC / scenario-comparison fields were removed (PIPE-6).
    assert not hasattr(e, "scenario_comparison_available")
    assert not hasattr(e, "sensitivity_enabled")


def test_enhanced_result_round_trips() -> None:
    """EnhancedAnalyticsResult packages a base result and enablement block."""
    res = EnhancedAnalyticsResult(
        base_result={"annual_rows": []},
        analytics_enabled=AnalyticsEnablement(returns_enabled=True),
    )
    dumped = res.model_dump()
    assert dumped["analytics_enabled"]["returns_enabled"] is True
    assert dumped["returns_analysis"] is None


# ---------------------------------------------------------------------------
# Import-time ImportError fallbacks (lines 49-50, 59-60).
# ---------------------------------------------------------------------------
def test_import_error_fallbacks_set_flags_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-import with analytics core imports forced to fail -> *_AVAILABLE False."""
    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in (
            "analytics.core.returns",
            "analytics.core.risk_metrics",
        ):
            raise ImportError(f"forced for {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    reloaded = importlib.reload(mod)
    try:
        assert reloaded.RETURNS_AVAILABLE is False
        assert reloaded.RISK_AVAILABLE is False
    finally:
        # Restore the real import and reload a clean module so other tests
        # (and the suite at large) see the genuine, fully-imported module.
        monkeypatch.setattr(builtins, "__import__", real_import)
        importlib.reload(mod)
