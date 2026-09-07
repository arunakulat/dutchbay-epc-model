"""Check both Weibull diagnostics against a directly calculated KS statistic."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from wind_resource.weibull_fit import fit_weibull_on_series
from wind_resource.wind_analyzer import WindAnalyzer


@pytest.mark.parametrize("seed", [7, 21])
@pytest.mark.parametrize("entrypoint", ["series", "analyzer"])
def test_weibull_ks_pvalue_matches_two_sided_distribution(
    seed: int, entrypoint: str
) -> None:
    """The reported p-value follows the two-sided KS law, not its statistic."""
    speeds = np.random.default_rng(seed).weibull(2.2, 32) * 8.0
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=len(speeds), freq="h"),
            "ws_150m": speeds,
        }
    )
    if entrypoint == "series":
        fitted = fit_weibull_on_series(frame, "ws_150m")
        shape, scale, pvalue = fitted.weibull_k, fitted.weibull_a, fitted.ks_pvalue
    else:
        result = WindAnalyzer(frame).fit_weibull()
        shape, scale, pvalue = (
            result["shape_k"],
            result["scale_c"],
            result["ks_pvalue"],
        )

    # Compute D directly from the empirical CDF jumps and the Weibull formula;
    # do not call kstest or either consumer's SciPy CDF helper for the oracle.
    cdf = 1.0 - np.exp(-((np.sort(speeds) / scale) ** shape))
    count = len(speeds)
    d_plus = np.max(np.arange(1, count + 1) / count - cdf)
    d_minus = np.max(cdf - np.arange(count) / count)
    statistic = float(max(d_plus, d_minus))
    expected_pvalue = float(stats.kstwo.sf(statistic, count))
    assert pvalue == pytest.approx(expected_pvalue, rel=1e-12, abs=1e-14)
    assert abs(expected_pvalue - statistic) > 0.1
