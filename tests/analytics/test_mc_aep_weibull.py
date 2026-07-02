#!/usr/bin/env python
"""Tests for Monte-Carlo AEP from an ECMWF-derived Weibull (#24).

Covers the Weibull fit (recovers known parameters), the MC percentile ordering
(exceedance convention), corroboration of the canonical P50, reproducibility,
and the summary CSV. Uses a synthetic ws150 series so it needs no ECMWF network
access; runs fast with a reduced sample size.

Context:
    Sprint 10 - Issue #24 (Monte Carlo AEP from ECMWF-derived Weibull).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from analytics.wind.mc_aep_weibull import (
    fit_weibull_from_series,
    run_mc_aep,
    write_mc_summary_csv,
)

CANONICAL_LOSSES = {
    "wake_loss_pct": 5.0,
    "availability_pct": 97.0,
    "electrical_loss_pct": 2.0,
    "curtailment_pct": 2.0,
    "other_pct": 1.0,
}


def _synthetic_ws150(a: float = 8.32, k: float = 2.1, n: int = 50_000) -> np.ndarray:
    return np.random.default_rng(7).weibull(k, n) * a


def test_fit_recovers_known_weibull() -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    assert fit.a == pytest.approx(8.32, abs=0.4)
    assert fit.k == pytest.approx(2.1, abs=0.25)
    assert fit.n_obs == 50_000


def test_fit_too_few_samples_raises() -> None:
    with pytest.raises(ValueError, match="Need >=10"):
        fit_weibull_from_series([7.0, 8.0, 6.5])


def test_percentile_ordering_exceedance() -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    p = run_mc_aep(
        fit,
        n_turbines=23,
        capacity_mw=6.5,
        losses=CANONICAL_LOSSES,
        curve_key="envision_en171_6p5",
        n_samples=800,
    )["percentiles"]
    assert p["p99"] < p["p90"] < p["p75"] < p["p50"]


def test_p50_corroborates_canonical() -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    res = run_mc_aep(
        fit,
        n_turbines=23,
        capacity_mw=6.5,
        losses=CANONICAL_LOSSES,
        curve_key="envision_en171_6p5",
        n_samples=2000,
    )
    assert res["percentiles"]["p50"] == pytest.approx(402.6, abs=10.0)


def test_p90_is_conservative() -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    res = run_mc_aep(
        fit,
        n_turbines=23,
        capacity_mw=6.5,
        losses=CANONICAL_LOSSES,
        curve_key="envision_en171_6p5",
        n_samples=800,
    )
    assert res["percentiles"]["p90"] < res["percentiles"]["p50"]


def test_reproducible_with_seed() -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    kw = dict(
        n_turbines=23,
        capacity_mw=6.5,
        losses=CANONICAL_LOSSES,
        curve_key="envision_en171_6p5",
        n_samples=500,
        seed=11,
    )
    a = run_mc_aep(fit, **kw)["percentiles"]
    b = run_mc_aep(fit, **kw)["percentiles"]
    assert a == b


def test_higher_uncertainty_widens_spread() -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    base = dict(
        n_turbines=23,
        capacity_mw=6.5,
        losses=CANONICAL_LOSSES,
        curve_key="envision_en171_6p5",
        n_samples=1500,
    )
    narrow = run_mc_aep(fit, weibull_uncertainty_pct=3.0, **base)
    wide = run_mc_aep(fit, weibull_uncertainty_pct=12.0, **base)
    assert wide["std"] > narrow["std"]


def test_summary_csv_written(tmp_path: Path) -> None:
    fit = fit_weibull_from_series(_synthetic_ws150())
    res = run_mc_aep(
        fit,
        n_turbines=23,
        capacity_mw=6.5,
        losses=CANONICAL_LOSSES,
        curve_key="envision_en171_6p5",
        n_samples=500,
    )
    out = write_mc_summary_csv(res, str(tmp_path / "DutchBay_AEP_MC_Summary.csv"))
    assert out.exists()
    text = out.read_text()
    assert "P90_net_aep_gwh" in text and "weibull_a" in text
