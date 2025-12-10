from __future__ import annotations

from typing import Any, List

import numpy as np
import pandas as pd
import pytest

from analytics.sensitivity_tail_risk import (
    _compute_tail_risk_stats,
    _resolve_low_metric_column,
    enrich_tornado_with_tail_risk,
)


class DummyMonteCarloResult:
    """
    Minimal stand-in for MonteCarloResult.

    We deliberately mirror only the attributes used by
    analytics.sensitivity_tail_risk:
        - metric_samples: dict[str, Sequence[float]]
        - raw_results: list[dict[str, float]]
    """

    def __init__(self, metric_name: str, values: List[float]) -> None:
        array = np.asarray(values, dtype=float)
        self.metric_samples = {metric_name: array}
        self.raw_results = [{metric_name: float(v)} for v in array]


def test_compute_tail_risk_stats_basic() -> None:
    values = np.asarray([0.05, 0.08, 0.10, 0.12, 0.15], dtype=float)
    confidence = 0.90

    stats = _compute_tail_risk_stats(values, confidence=confidence)

    # Basic sanity: confidence is echoed, and quantiles are within range.
    assert stats.confidence == confidence
    assert 0.05 <= stats.var <= 0.15
    assert 0.05 <= stats.cvar <= 0.15
    assert stats.p10 <= stats.p90
    # CVaR should be at least as bad as VaR on the left tail.
    assert stats.cvar <= stats.var + 1e-9


def test_resolve_low_metric_column_prefers_known_candidates() -> None:
    df = pd.DataFrame(
        {
            "Parameter": ["capex", "tariff"],
            "low_metric": [0.05, 0.06],  # lower-case variant
            "High Metric": [0.15, 0.14],
        }
    )

    column = _resolve_low_metric_column(df)
    assert column == "low_metric"


def test_resolve_low_metric_column_raises_when_missing() -> None:
    df = pd.DataFrame(
        {
            "Parameter": ["capex", "tariff"],
            "High Metric": [0.15, 0.14],
        }
    )

    with pytest.raises(ValueError):
        _resolve_low_metric_column(df)


def test_enrich_tornado_with_tail_risk_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Happy-path integration:

    - monkeypatch tornado_suite_to_dataframe to return a simple DataFrame
    - use DummyMonteCarloResult to feed a small sample
    - verify columns and that VaR/CVaR/P10/P90 align with helper stats
    """
    base_df = pd.DataFrame(
        {
            "Parameter": ["capex", "tariff"],
            "Low Metric": [0.06, 0.07],
            "High Metric": [0.14, 0.13],
        }
    )

    def fake_tornado_to_df(tornado_suite: Any) -> pd.DataFrame:  # noqa: ARG001
        return base_df

    monkeypatch.setattr(
        "analytics.sensitivity_tail_risk.tornado_suite_to_dataframe",
        fake_tornado_to_df,
    )

    metric_name = "project_irr"
    sample_values = [0.05, 0.08, 0.10, 0.12, 0.15]
    mc_result = DummyMonteCarloResult(metric_name, sample_values)
    confidence = 0.90

    result_df = enrich_tornado_with_tail_risk(
        tornado_suite=object(),
        mc_result=mc_result,
        metric=metric_name,
        confidence=confidence,
    )

    # Columns preserved + new columns added.
    for col in ("Parameter", "Low Metric", "High Metric"):
        assert col in result_df.columns

    for col in ("VaR", "CVaR", "P10", "P90", "BreachProbability"):
        assert col in result_df.columns

    # VaR/CVaR/P10/P90 should be constant across rows and match helper stats.
    stats = _compute_tail_risk_stats(
        np.asarray(sample_values, dtype=float),
        confidence=confidence,
    )

    assert result_df["VaR"].nunique() == 1
    assert result_df["CVaR"].nunique() == 1
    assert result_df["P10"].nunique() == 1
    assert result_df["P90"].nunique() == 1

    assert result_df["VaR"].iloc[0] == pytest.approx(stats.var)
    assert result_df["CVaR"].iloc[0] == pytest.approx(stats.cvar)
    assert result_df["P10"].iloc[0] == pytest.approx(stats.p10)
    assert result_df["P90"].iloc[0] == pytest.approx(stats.p90)

    # Breach probabilities should be between 0 and 1.
    assert (result_df["BreachProbability"] >= 0.0).all()
    assert (result_df["BreachProbability"] <= 1.0).all()


def test_enrich_tornado_with_tail_risk_invalid_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    confidence ∉ (0, 1) should raise a ValueError before touching MC samples.
    """
    base_df = pd.DataFrame(
        {
            "Parameter": ["capex"],
            "Low Metric": [0.06],
            "High Metric": [0.14],
        }
    )

    def fake_tornado_to_df(tornado_suite: Any) -> pd.DataFrame:  # noqa: ARG001
        return base_df

    monkeypatch.setattr(
        "analytics.sensitivity_tail_risk.tornado_suite_to_dataframe",
        fake_tornado_to_df,
    )

    mc_result = DummyMonteCarloResult("project_irr", [0.1, 0.12])

    with pytest.raises(ValueError):
        enrich_tornado_with_tail_risk(
            tornado_suite=object(),
            mc_result=mc_result,
            metric="project_irr",
            confidence=1.0,
        )


def test_enrich_tornado_with_tail_risk_missing_metric_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    If the requested metric is missing from both metric_samples and raw_results,
    we should raise a clear ValueError.
    """
    base_df = pd.DataFrame(
        {
            "Parameter": ["capex"],
            "Low Metric": [0.06],
            "High Metric": [0.14],
        }
    )

    def fake_tornado_to_df(tornado_suite: Any) -> pd.DataFrame:  # noqa: ARG001
        return base_df

    monkeypatch.setattr(
        "analytics.sensitivity_tail_risk.tornado_suite_to_dataframe",
        fake_tornado_to_df,
    )

    # Metric name intentionally different from what's inside DummyMonteCarloResult.
    mc_result = DummyMonteCarloResult("project_irr", [0.1, 0.12])

    with pytest.raises(ValueError):
        enrich_tornado_with_tail_risk(
            tornado_suite=object(),
            mc_result=mc_result,
            metric="dscr_min",
            confidence=0.95,
        )
