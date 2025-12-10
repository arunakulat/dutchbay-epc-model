from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from analytics import sensitivity_tail_risk as tr
from analytics.contracts_v14 import SensitivitySuite, TornadoResult
from analytics.monte_carlo_v14 import MonteCarloResult


def _make_toy_monte_carlo_with_metric_samples(
    values: List[float],
) -> MonteCarloResult:
    """
    Build a minimal MonteCarloResult with metric_samples populated.

    This stays engine-agnostic and mirrors the contracts_v14 surface.
    """
    mc = MonteCarloResult(
        iterations=len(values),
        project_irr_mean=float(np.mean(values)),
        project_irr_std=float(np.std(values)),
        project_irr_p10=float(np.percentile(values, 10)),
        project_irr_p50=float(np.percentile(values, 50)),
        project_irr_p90=float(np.percentile(values, 90)),
        project_npv_mean=0.0,
        project_npv_p10=0.0,
        project_npv_p50=0.0,
        project_npv_p90=0.0,
        dscr_min_p10=0.0,
        dscr_min_p50=0.0,
        failed_iterations=0,
        raw_results=None,
        scenario_name="toy-sensitivity-tail-risk",
    )
    # Engine extension: tail-risk prefers metric_samples if present.
    metric_samples: Dict[str, List[float]] = {"project_irr": list(values)}
    setattr(mc, "metric_samples", metric_samples)
    return mc


def test_enrich_tornado_with_tail_risk_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Happy-path API test:

    - Uses metric_samples on MonteCarloResult.
    - Monkeypatches tornado_suite_to_dataframe so we control the schema.
    - Asserts that tail-risk columns and breach probabilities are present.
    """
    values = [0.10, 0.11, 0.12, 0.13, 0.14]
    mc_result = _make_toy_monte_carlo_with_metric_samples(values)

    # Minimal tornado suite – actual rows come from the patched DataFrame.
    suite = SensitivitySuite(
        tornado_results=[
            TornadoResult(
                variable="project.capex_usd_per_kw",
                base_irr=0.12,
                low_irr=0.10,
                high_irr=0.14,
            ),
        ],
        base_metric=0.12,
        base_config_path="conf/toy.yaml",
        metric="project_irr",
    )

    def fake_tornado_df(_suite: SensitivitySuite) -> pd.DataFrame:
        # The API only cares that there is a "low metric" column
        # and some thresholds to compute breach probabilities against.
        return pd.DataFrame(
            {
                "Variable": ["project.capex_usd_per_kw"],
                "Low Metric": [0.11],
                "High Metric": [0.13],
            }
        )

    monkeypatch.setattr(tr, "tornado_suite_to_dataframe", fake_tornado_df)

    df = tr.enrich_tornado_with_tail_risk(
        tornado_suite=suite,
        mc_result=mc_result,
        metric="project_irr",
        confidence=0.9,
    )

    # Columns expected by CASPER / dashboards.
    for col in ("VaR", "CVaR", "P10", "P90", "BreachProbability"):
        assert col in df.columns

    # Sanity: at least one row and breach probability is in [0, 1].
    assert len(df) == 1
    breach_prob = float(df.loc[0, "BreachProbability"])
    assert 0.0 <= breach_prob <= 1.0


def test_enrich_tornado_with_tail_risk_rejects_bad_confidence() -> None:
    """
    Guardrail: invalid confidence values should raise a ValueError with
    clear semantics. This keeps the public API predictable.
    """
    mc_result = _make_toy_monte_carlo_with_metric_samples([0.1, 0.12, 0.14])
    suite = SensitivitySuite(
        tornado_results=[],
        base_metric=0.12,
        base_config_path="conf/toy.yaml",
        metric="project_irr",
    )

    with pytest.raises(ValueError) as exc:
        tr.enrich_tornado_with_tail_risk(
            tornado_suite=suite,
            mc_result=mc_result,
            metric="project_irr",
            confidence=1.5,
        )

    msg = str(exc.value)
    assert "confidence must be in (0, 1)" in msg
