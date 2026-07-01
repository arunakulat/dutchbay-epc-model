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


def test_returns_rows_missing_usd_fields_default_to_zero(
    real_cfg: Dict[str, Any],
) -> None:
    """Rows without the enriched USD fields -> zero series, still returns AllReturns.

    Post-D12 the series are read from per-row ``cf_pre_debt`` / ``debt_service_total``
    (USD). Rows carrying only the legacy ``cfads_final_lkr`` therefore yield all-zero
    USD series via ``row.get(..., 0.0)`` and must still produce a (degenerate)
    AllReturns rather than raising.
    """
    base = {
        "annual_rows": [{"cfads_final_lkr": 1.0e9}, {"cfads_final_lkr": 1.1e9}],
    }
    out = mod._calculate_returns_analysis(base, real_cfg)
    assert out is not None
    assert out.project_returns is not None


def test_returns_series_are_one_entry_per_annual_row(
    real_cfg: Dict[str, Any],
) -> None:
    """Both series are built one entry per annual row (index-aligned by construction).

    Post-D12 CFADS and debt service both come from the annual rows themselves, so the
    two series are always the same length as ``annual_rows`` -- no positional slice of
    a period-indexed debt series and no while-loop padding can desynchronise them.
    """
    base = {
        "annual_rows": [
            {"cf_pre_debt": 1.2e7, "debt_service_total": 4.0e6},
            {"cf_pre_debt": 1.3e7, "debt_service_total": 4.0e6},
            {"cf_pre_debt": 1.4e7, "debt_service_total": 4.0e6},
        ],
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


def test_returns_geared_equity_below_project_for_expensive_debt() -> None:
    """D12: enhanced-analytics returns are USD-consistent and phase-aligned.

    With debt priced (11%) above the unlevered project return (~8.4%) at 60% gearing,
    geared equity IRR must sit BELOW project IRR. Pre-fix, CFADS was read in LKR
    (``cfads_final_lkr``) while debt service was sliced from the USD, period-indexed
    ``debt_result['debt_service_total']`` -- a ~FX-rate currency mismatch plus a phase
    offset that made debt service ~vanish and inflated equity IRR far above project
    IRR. This is a regression guard for that bug.
    """
    fx = 300.0
    n = 15
    cf_usd = 12_000_000.0
    r_d, debt_usd = 0.11, 60_000_000.0
    ds_usd = debt_usd * r_d / (1.0 - (1.0 + r_d) ** -n)  # level annuity
    # Enriched-row shape: per-row USD cf_pre_debt + per-row USD debt_service_total,
    # plus the legacy LKR cfads_final_lkr the buggy path used to read.
    annual_rows = [
        {
            "year": i + 1,
            "cfads_final_lkr": cf_usd * fx,
            "cf_pre_debt": cf_usd,
            "debt_service_total": ds_usd,
        }
        for i in range(n)
    ]
    base = {
        "annual_rows": annual_rows,
        # Period-indexed USD series with a construction lead-in: what the buggy path
        # positionally sliced (now ignored -- the per-row fields drive the series).
        "debt_result": {"debt_service_total": [0.0, 0.0] + [ds_usd] * n},
    }
    cfg = {
        "capex": {"usd_total": 100_000_000.0},
        "fx": {"start_lkr_per_usd": fx},
        "Financing_Terms": {"debt_ratio": 0.6},
        "returns": {"project_discount_rate": 0.10, "equity_discount_rate": 0.12},
    }
    out = mod._calculate_returns_analysis(base, cfg)
    assert out is not None
    proj = out.project_returns.project_irr
    eq = out.equity_returns.equity_irr
    assert proj is not None and eq is not None
    # Expensive debt above the project return de-levers equity.
    assert eq < proj
    # The currency-mismatch inflation (uplift was strongly positive pre-fix) is gone.
    assert out.irr_uplift < 0.0
    # Equity base is USD equity (capex_usd * (1 - debt_ratio)), not LKR-scaled.
    assert out.equity_investment_lkr == pytest.approx(40_000_000.0)


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
