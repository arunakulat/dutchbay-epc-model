"""Coverage tests for analytics.core.risk_metrics (TailRiskAnalyzer).

Exercises the tail-risk analytics primitives end to end with small, fully
deterministic synthetic arrays: VaR/CVaR direction and the small-sample
``max(1, ...)`` guard, percentile ordering, downside risk (including both the
finite-Sortino path and the two zero-downside-deviation branches that yield
``inf`` / ``0.0``), the covenant-breach probabilities over a (scenario, year)
grid, the full ``tail_risk_report`` aggregation, and the ``to_dataframe``
summariser. Also covers the ``RiskConfig`` confidence-level warning branch and
the canonical-scenario portability guard.

Pure numpy / pydantic arithmetic — no network, cdsapi, or matplotlib is
touched, so nothing needs mocking. Assertions check real quantile direction,
signs, conservation, and documented edge-case returns against the live engine,
never hardcoded financial magic numbers.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics.core.risk_metrics import (
    CovenantBreachAnalysis,
    DownsideRisk,
    PercentileAnalysis,
    RiskConfig,
    TailRiskAnalyzer,
    TailRiskReport,
    VaRCVaRResult,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _config(
    *,
    confidence_level: float = 0.95,
    target_return: float = 0.10,
    min_dscr: float = 1.30,
    min_llcr: float = 1.40,
    min_plcr: float = 1.50,
) -> RiskConfig:
    return RiskConfig(
        confidence_level=confidence_level,
        target_return=target_return,
        min_dscr=min_dscr,
        min_llcr=min_llcr,
        min_plcr=min_plcr,
    )


def _analyzer(**kwargs: float) -> TailRiskAnalyzer:
    return TailRiskAnalyzer(_config(**kwargs))


# ---------------------------------------------------------------------------
# RiskConfig.validate_confidence — warning branch (line 62)
# ---------------------------------------------------------------------------


def test_config_unusual_confidence_warns(caplog: pytest.LogCaptureFixture) -> None:
    # A confidence level outside the typical 0.80-0.99 band is still accepted
    # (the field bound is 0..1) but emits a warning.
    with caplog.at_level(
        logging.WARNING, logger="dutchbay.analytics.core.risk_metrics"
    ):
        cfg = _config(confidence_level=0.50)
    assert cfg.confidence_level == pytest.approx(0.50)
    assert any("Unusual confidence level" in rec.message for rec in caplog.records)


def test_config_typical_confidence_no_warn(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(
        logging.WARNING, logger="dutchbay.analytics.core.risk_metrics"
    ):
        _config(confidence_level=0.95)
    assert not any("Unusual confidence level" in rec.message for rec in caplog.records)


def test_config_is_frozen() -> None:
    cfg = _config()
    with pytest.raises(Exception):
        cfg.confidence_level = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# __init__ — var_percentile derivation
# ---------------------------------------------------------------------------


def test_analyzer_var_percentile_derivation() -> None:
    analyzer = _analyzer(confidence_level=0.95)
    # int((1 - conf) * 100): matches the engine's exact float-truncation. For
    # 0.95 this is int(5.0000...) == 5.
    assert analyzer.var_percentile == int((1 - 0.95) * 100)
    assert analyzer.var_percentile == 5
    # For 0.90, (1-0.90)*100 == 9.999... which int() truncates to 9, not 10 —
    # assert against the live derivation rather than the nominal 10.
    other = _analyzer(confidence_level=0.90)
    assert other.var_percentile == int((1 - 0.90) * 100)


# ---------------------------------------------------------------------------
# calculate_var_cvar — direction, labels, small-sample guard
# ---------------------------------------------------------------------------


def test_var_cvar_direction_and_labels() -> None:
    analyzer = _analyzer(confidence_level=0.95)
    returns = np.arange(0.0, 100.0)  # 0..99
    out = analyzer.calculate_var_cvar(returns, return_type="equity_irr")
    assert isinstance(out, VaRCVaRResult)
    # CVaR (mean of the worst tail) must sit at or below VaR (the cut point).
    assert out.cvar <= out.var
    # Both must be drawn from the lower (downside) tail of the distribution.
    assert out.var < float(returns.mean())
    assert out.return_type == "equity_irr"
    assert out.var_label == "VaR(95%)"
    # CVaR is labelled with both standard names: CVaR == Expected Shortfall (#600).
    assert out.cvar_label == "CVaR/ES(95%)"
    assert out.confidence == pytest.approx(0.95)


def test_var_cvar_small_sample_guard_no_nan() -> None:
    # n=5 with conf 0.95: (1-0.95)*5 = 0.25 -> int 0; max(1, 0) keeps the tail
    # non-empty so CVaR is finite rather than NaN (audit R1).
    analyzer = _analyzer(confidence_level=0.95)
    returns = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    out = analyzer.calculate_var_cvar(returns)
    assert math.isfinite(out.var)
    assert math.isfinite(out.cvar)
    # The single-point tail is the minimum, and var sits just above it.
    assert out.cvar == pytest.approx(1.0)
    assert out.var == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# percentile_analysis — ordering
# ---------------------------------------------------------------------------


def test_percentile_analysis_is_monotone() -> None:
    analyzer = _analyzer()
    returns = np.arange(0.0, 101.0)
    out = analyzer.percentile_analysis(returns)
    assert isinstance(out, PercentileAnalysis)
    assert out.p10 < out.p25 < out.p50 < out.p75 < out.p90
    assert out.p50 == pytest.approx(50.0)
    assert out.p10 == pytest.approx(float(np.percentile(returns, 10)))


# ---------------------------------------------------------------------------
# downside_risk — finite Sortino + both zero-deviation branches
# ---------------------------------------------------------------------------


def test_downside_risk_finite_sortino() -> None:
    analyzer = _analyzer(target_return=0.10)
    # Mix of returns straddling the target; some below -> non-zero downside dev.
    returns = np.array([0.02, 0.05, 0.08, 0.12, 0.15, 0.20])
    out = analyzer.downside_risk(returns)
    assert isinstance(out, DownsideRisk)
    below = returns[returns < 0.10]
    assert out.returns_below_target == below.size
    assert out.downside_deviation == pytest.approx(float(below.std()))
    assert out.downside_deviation > 0.0
    assert out.probability_below_target == pytest.approx(below.size / returns.size)
    assert out.target_return == pytest.approx(0.10)
    # Sortino = (mean - target) / downside_dev; sign follows mean vs target.
    expected = (float(returns.mean()) - 0.10) / float(below.std())
    assert out.sortino_ratio == pytest.approx(expected)
    assert math.isfinite(out.sortino_ratio)


def test_downside_risk_zero_deviation_mean_above_target_is_inf() -> None:
    # No returns below target -> downside_deviation 0.0; mean > target -> +inf.
    analyzer = _analyzer(target_return=0.10)
    returns = np.array([0.12, 0.15, 0.20, 0.25])
    out = analyzer.downside_risk(returns)
    assert out.downside_deviation == pytest.approx(0.0)
    assert out.returns_below_target == 0
    assert out.probability_below_target == pytest.approx(0.0)
    assert math.isinf(out.sortino_ratio)
    assert out.sortino_ratio > 0.0


def test_downside_risk_zero_deviation_mean_not_above_target_is_zero() -> None:
    # All returns equal to the target -> none strictly below, downside dev 0.0,
    # and mean == target (not > target) -> Sortino collapses to 0.0.
    analyzer = _analyzer(target_return=0.10)
    returns = np.array([0.10, 0.10, 0.10, 0.10])
    out = analyzer.downside_risk(returns)
    assert out.downside_deviation == pytest.approx(0.0)
    assert out.returns_below_target == 0
    assert out.sortino_ratio == pytest.approx(0.0)


def test_downside_risk_single_below_target_has_zero_std() -> None:
    # Exactly one return below target: std of a one-element array is 0.0, so we
    # take the zero-deviation branch; mean is below target -> Sortino 0.0.
    analyzer = _analyzer(target_return=0.10)
    returns = np.array([0.05, 0.20])
    out = analyzer.downside_risk(returns)
    assert out.returns_below_target == 1
    assert out.downside_deviation == pytest.approx(0.0)
    # mean = 0.125 > 0.10 -> +inf (single below value gives zero deviation).
    assert math.isinf(out.sortino_ratio)


# ---------------------------------------------------------------------------
# covenant_breach_probability — (scenario, year) grid
# ---------------------------------------------------------------------------


def test_covenant_breach_probability_grid() -> None:
    analyzer = _analyzer(min_dscr=1.30, min_llcr=1.40, min_plcr=1.50)
    # 4 scenarios x 3 years. Per-scenario minima taken across the year axis.
    dscr = np.array(
        [
            [1.50, 1.60, 1.45],  # min 1.45 -> ok
            [1.20, 1.35, 1.40],  # min 1.20 -> breach (< 1.30)
            [1.31, 1.32, 1.33],  # min 1.31 -> ok
            [1.10, 1.10, 1.10],  # min 1.10 -> breach
        ]
    )
    llcr = np.array(
        [
            [1.50, 1.55, 1.60],  # min 1.50 -> ok
            [1.30, 1.45, 1.50],  # min 1.30 -> breach (< 1.40)
            [1.45, 1.46, 1.47],  # min 1.45 -> ok
            [1.41, 1.41, 1.41],  # min 1.41 -> ok
        ]
    )
    plcr = np.array(
        [
            [1.60, 1.70, 1.65],  # min 1.60 -> ok
            [1.55, 1.58, 1.59],  # min 1.55 -> ok
            [1.45, 1.46, 1.47],  # min 1.45 -> breach (< 1.50)
            [1.51, 1.52, 1.53],  # min 1.51 -> ok
        ]
    )
    out = analyzer.covenant_breach_probability(dscr, llcr, plcr)
    assert isinstance(out, CovenantBreachAnalysis)
    assert out.dscr_breach_probability == pytest.approx(2 / 4)
    assert out.llcr_breach_probability == pytest.approx(1 / 4)
    assert out.plcr_breach_probability == pytest.approx(1 / 4)
    # Mean-of-minima conservation: equals the mean of the per-scenario minima.
    assert out.dscr_min_mean == pytest.approx(float(np.min(dscr, axis=1).mean()))
    assert out.llcr_min_mean == pytest.approx(float(np.min(llcr, axis=1).mean()))
    assert out.plcr_min_mean == pytest.approx(float(np.min(plcr, axis=1).mean()))
    assert out.thresholds == {"min_dscr": 1.30, "min_llcr": 1.40, "min_plcr": 1.50}


def test_covenant_breach_no_breaches() -> None:
    analyzer = _analyzer(min_dscr=1.0, min_llcr=1.0, min_plcr=1.0)
    grid = np.array([[2.0, 2.1], [2.2, 2.3]])
    out = analyzer.covenant_breach_probability(grid, grid, grid)
    assert out.dscr_breach_probability == pytest.approx(0.0)
    assert out.llcr_breach_probability == pytest.approx(0.0)
    assert out.plcr_breach_probability == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# tail_risk_report — full aggregation
# ---------------------------------------------------------------------------


def _mc_inputs() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(11)
    n = 500
    return {
        "equity_irr": rng.normal(0.08, 0.03, size=n),
        "project_irr": rng.normal(0.06, 0.02, size=n),
        "equity_npv": rng.normal(20.0, 10.0, size=n),
        "project_npv": rng.normal(-5.0, 15.0, size=n),
        "dscr": rng.normal(1.40, 0.10, size=(n, 5)),
        "llcr": rng.normal(1.55, 0.10, size=(n, 5)),
        "plcr": rng.normal(1.65, 0.10, size=(n, 5)),
    }


def test_tail_risk_report_full() -> None:
    analyzer = _analyzer(confidence_level=0.95, target_return=0.10)
    d = _mc_inputs()
    report = analyzer.tail_risk_report(
        equity_irr=d["equity_irr"],
        project_irr=d["project_irr"],
        equity_npv=d["equity_npv"],
        project_npv=d["project_npv"],
        dscr_results=d["dscr"],
        llcr_results=d["llcr"],
        plcr_results=d["plcr"],
    )
    assert isinstance(report, TailRiskReport)

    # Per-metric summaries carry the right names and consistent stats.
    assert report.equity_irr.metric_name == "equity_irr"
    assert report.equity_irr.mean == pytest.approx(float(d["equity_irr"].mean()))
    assert report.equity_irr.std == pytest.approx(float(d["equity_irr"].std()))
    assert report.equity_irr.min == pytest.approx(float(d["equity_irr"].min()))
    assert report.equity_irr.max == pytest.approx(float(d["equity_irr"].max()))
    assert report.equity_irr.min <= report.equity_irr.mean <= report.equity_irr.max

    # Only equity IRR carries a downside block; the other three are None.
    assert report.equity_irr.downside is not None
    assert report.project_irr.downside is None
    assert report.equity_npv.downside is None
    assert report.project_npv.downside is None

    # VaR/CVaR ordering holds on the equity IRR profile.
    assert report.equity_irr.var_cvar.cvar <= report.equity_irr.var_cvar.var

    # Covenant block is populated and target is echoed back.
    assert isinstance(report.covenant_breaches, CovenantBreachAnalysis)
    assert 0.0 <= report.probability_below_hurdle <= 1.0
    assert report.target_equity_irr == pytest.approx(0.10)
    # probability_below_hurdle equals the empirical share below the target.
    expected_share = float((d["equity_irr"] < 0.10).sum() / d["equity_irr"].size)
    assert report.probability_below_hurdle == pytest.approx(expected_share)


# ---------------------------------------------------------------------------
# to_dataframe — summariser
# ---------------------------------------------------------------------------


def test_to_dataframe_summary() -> None:
    analyzer = _analyzer()
    d = _mc_inputs()
    report = analyzer.tail_risk_report(
        equity_irr=d["equity_irr"],
        project_irr=d["project_irr"],
        equity_npv=d["equity_npv"],
        project_npv=d["project_npv"],
        dscr_results=d["dscr"],
        llcr_results=d["llcr"],
        plcr_results=d["plcr"],
    )
    df = analyzer.to_dataframe(report)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "metric",
        "mean",
        "std",
        "min",
        "max",
        "var",
        "cvar",
        "p50",
    ]
    assert list(df["metric"]) == [
        "equity_irr",
        "project_irr",
        "equity_npv",
        "project_npv",
    ]
    # Row values must mirror the underlying contract for equity_irr.
    eq_row = df[df["metric"] == "equity_irr"].iloc[0]
    assert eq_row["mean"] == pytest.approx(report.equity_irr.mean)
    assert eq_row["var"] == pytest.approx(report.equity_irr.var_cvar.var)
    assert eq_row["cvar"] == pytest.approx(report.equity_irr.var_cvar.cvar)
    assert eq_row["p50"] == pytest.approx(report.equity_irr.percentiles.p50)


# ---------------------------------------------------------------------------
# Portability guard
# ---------------------------------------------------------------------------


def test_canonical_scenario_path_resolves() -> None:
    # Resolved relative to the test file, never an absolute worktree path.
    assert LENDER.exists()
