"""MC convergence diagnostic (#590) — analytics/mc/convergence.py.

Read-only: verifies the CI-half-width formula, checkpoint/filtering behaviour, that the
band shrinks with more trials, and that the engine attaches it to result.metadata without
changing any band (KPI-neutral).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from analytics.core.covenant_breach import prob_breach
from analytics.mc.convergence import (
    Z_95,
    _order_stat_ci_ranks,
    _wilson_interval,
    convergence_diagnostic,
    percentile_ci_diagnostic,
)

_LENDER = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)

PIN_UNIT = np.array([1.2999999999999996, 1.2999999999999998, 1.3, 1.3000000000000003])


def test_ci_halfwidth_matches_formula_and_ends_at_n() -> None:
    rng = np.random.default_rng(0)
    arr = rng.normal(0.10, 0.02, size=500)
    out = convergence_diagnostic({"project_irr": arr.tolist()}, z=Z_95, min_n=30)
    d = out["project_irr"]

    assert d["n"] == 500
    assert d["checkpoints"][-1] == 500  # trace always ends at n
    expected_hw = Z_95 * float(arr.std(ddof=1)) / np.sqrt(500)
    assert d["final_ci_halfwidth"] == pytest.approx(expected_hw)
    assert d["final_mean"] == pytest.approx(float(arr.mean()))
    assert d["final_rel_ci_halfwidth"] == pytest.approx(
        expected_hw / abs(float(arr.mean()))
    )
    # The half-width narrows from the first checkpoint (k=30) to the last (k=500).
    assert d["ci_halfwidth_trace"][0] >= d["ci_halfwidth_trace"][-1]


def test_metric_below_min_n_is_omitted() -> None:
    assert convergence_diagnostic({"x": [1.0, 2.0, 3.0]}, min_n=30) == {}


def test_none_and_nonfinite_entries_are_dropped() -> None:
    arr = [1.0, None, float("nan"), float("inf"), 2.0] + [1.5] * 40
    out = convergence_diagnostic({"x": arr}, min_n=30)
    assert out["x"]["n"] == 42  # 45 entries minus None, nan, inf


def test_halfwidth_shrinks_with_more_trials() -> None:
    rng = np.random.default_rng(1)
    small = convergence_diagnostic({"x": rng.normal(0, 1, 100).tolist()}, min_n=30)["x"]
    big = convergence_diagnostic({"x": rng.normal(0, 1, 4000).tolist()}, min_n=30)["x"]
    assert big["final_ci_halfwidth"] < small["final_ci_halfwidth"]


def test_rel_ci_halfwidth_is_none_when_mean_near_zero() -> None:
    """A mean within one half-width of zero has undefined relative precision (audit: DutchBay
    IRRs sit near zero, so |mean| in the denominator would blow up to a spurious huge number).
    """
    rng = np.random.default_rng(3)
    arr = rng.normal(0.0, 1.0, size=1000)  # mean ~ 0, well inside its own CI half-width
    d = convergence_diagnostic({"x": arr.tolist()}, min_n=30)["x"]
    assert d["final_rel_ci_halfwidth"] is None
    assert d["final_ci_halfwidth"] > 0.0  # the absolute half-width is still reported
    assert d["statistic"] == "mean"


def test_min_n_below_one_does_not_crash() -> None:
    """min_n <= 0 must not raise an opaque geomspace('cannot include zero') error."""
    out = convergence_diagnostic({"x": [float(i) for i in range(50)]}, min_n=0)
    assert out["x"]["checkpoints"][-1] == 50


def test_engine_attaches_convergence_metadata_without_changing_bands() -> None:
    from analytics.mc.engine import MonteCarloEngine

    cfg = yaml.safe_load(_LENDER.read_text())
    result = MonteCarloEngine(cfg, seed=1).run(n_trials=64)

    assert "convergence" in result.metadata
    conv = result.metadata["convergence"]
    # n_trials=64 >= min_n=30, so at least one metric is always diagnosed (assert, not guard).
    assert isinstance(conv, dict) and conv
    d = next(iter(conv.values()))
    assert d["statistic"] == "mean"
    assert {
        "n",
        "checkpoints",
        "ci_halfwidth_trace",
        "final_ci_halfwidth",
        "final_rel_ci_halfwidth",
    } <= set(d)
    assert d["checkpoints"][-1] == d["n"]
    assert len(d["ci_halfwidth_trace"]) == len(d["checkpoints"])
    # The diagnostic is additive: the percentile bands are still present and untouched.
    assert result.percentiles is not None


# --------------------------------------------------------------------------------------
# percentile_ci_diagnostic (#642) — distribution-free order-statistic CI for the P90/P95.
# --------------------------------------------------------------------------------------


def test_order_stat_ranks_match_normal_approx_and_widen_outward() -> None:
    """Ranks are floor(n*p - z*sd) / ceil(n*p + z*sd) with sd = sqrt(n*p*(1-p))."""
    n, p = 500, 0.90
    sd = np.sqrt(n * p * (1.0 - p))
    lo, hi = _order_stat_ci_ranks(n, p, Z_95)
    assert lo == int(np.floor(n * p - Z_95 * sd))
    assert hi == int(np.ceil(n * p + Z_95 * sd))
    # Widened outward (conservative): lower rank strictly below the point rank n*p, upper above.
    assert lo < n * p < hi


def test_order_stat_upper_rank_is_none_when_n_too_small() -> None:
    """P95 upper rank cannot be placed until n is large enough — reported None, never clamped."""
    lo_small, hi_small = _order_stat_ci_ranks(40, 0.95, Z_95)
    assert hi_small is None  # ceil(40*.95 + z*sd) = 42 > 40
    assert lo_small is not None
    lo_big, hi_big = _order_stat_ci_ranks(73, 0.95, Z_95)
    assert hi_big is not None and hi_big <= 73  # placeable once n is large enough


def test_percentile_ci_point_matches_numpy_quantile_and_brackets_it() -> None:
    rng = np.random.default_rng(0)
    arr = rng.normal(0.10, 0.02, size=1000)
    out = percentile_ci_diagnostic({"project_irr": arr.tolist()}, percentiles=[90, 95])
    d = out["project_irr"]
    assert d["statistic"] == "percentile_ci"
    assert d["n"] == 1000
    for p in ("90", "95"):
        lv = d["percentiles"][p]
        assert lv["point"] == pytest.approx(
            float(np.quantile(np.sort(arr), int(p) / 100.0))
        )
        # The band brackets the point estimate (order statistics on both sides).
        assert lv["ci_lower"] <= lv["point"] <= lv["ci_upper"]
        assert lv["rank_lower"] < lv["rank_upper"]


def test_percentile_ci_covers_known_analytic_p90() -> None:
    """Distribution-free coverage: the 95% order-stat CI for the P90 of Uniform(0,1) brackets
    the analytic true P90 (=0.90) at ~the nominal rate over many independent draws. The
    outward floor/ceil widening makes it conservative (coverage >= 0.95), which is the correct
    direction for a lender-facing band.
    """
    rng = np.random.default_rng(12345)
    n, true_p90, reps = 500, 0.90, 400
    covered = 0
    for _ in range(reps):
        x = rng.uniform(0.0, 1.0, n)
        lv = percentile_ci_diagnostic({"x": x.tolist()}, percentiles=[90])["x"][
            "percentiles"
        ]["90"]
        if lv["ci_lower"] <= true_p90 <= lv["ci_upper"]:
            covered += 1
    coverage = covered / reps
    assert coverage >= 0.95  # conservative order-stat interval, seeded → deterministic


def test_percentile_ci_shrinks_with_more_trials() -> None:
    rng = np.random.default_rng(7)
    big = rng.normal(0.0, 1.0, 8000)

    def width(nsub: int) -> float:
        lv = percentile_ci_diagnostic({"x": big[:nsub].tolist()}, percentiles=[90])[
            "x"
        ]["percentiles"]["90"]
        return lv["ci_upper"] - lv["ci_lower"]

    assert width(4000) < width(200)


def test_percentile_ci_omits_metric_below_min_n() -> None:
    assert percentile_ci_diagnostic({"x": [1.0, 2.0, 3.0]}, min_n=30) == {}


def test_percentile_ci_drops_none_and_nonfinite() -> None:
    arr = [1.0, None, float("nan"), float("inf"), 2.0] + [1.5] * 40
    out = percentile_ci_diagnostic({"x": arr}, min_n=30)
    assert out["x"]["n"] == 42  # 45 entries minus None, nan, inf


def test_wilson_interval_matches_formula_and_stays_in_unit() -> None:
    k, n = 5, 100
    lo, hi = _wilson_interval(k, n, Z_95)
    phat = k / n
    z2 = Z_95 * Z_95
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = (Z_95 / denom) * np.sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n))
    assert lo == pytest.approx(max(0.0, center - margin))
    assert hi == pytest.approx(min(1.0, center + margin))
    # Zero breaches: lower clamps to 0, band still non-degenerate (Wilson, not Wald).
    z_lo, z_hi = _wilson_interval(0, 100, Z_95)
    assert z_lo == pytest.approx(0.0, abs=1e-9)
    assert 0.0 < z_hi < 1.0


def test_breach_probability_ci_only_when_threshold_given() -> None:
    rng = np.random.default_rng(2)
    dscr = rng.normal(1.35, 0.10, size=500).tolist()
    # No threshold → no breach block invented.
    plain = percentile_ci_diagnostic({"dscr_min": dscr})["dscr_min"]
    assert "breach_probability_ci" not in plain
    # With a covenant threshold → Wilson breach CI on P(dscr_min < 1.30).
    withthr = percentile_ci_diagnostic(
        {"dscr_min": dscr}, breach_thresholds={"dscr_min": 1.30}
    )["dscr_min"]
    b = withthr["breach_probability_ci"]
    expected = prob_breach(np.asarray(dscr, dtype=float), 1.30)
    assert b["threshold"] == 1.30
    assert b["method"] == "wilson"
    assert b["n_breaches"] == int(round(expected * len(dscr)))
    assert b["point"] == pytest.approx(expected)
    assert b["ci_lower"] <= b["point"] <= b["ci_upper"]


def test_breach_probability_ci_excludes_floor_pin_noise() -> None:
    dscr = np.tile(PIN_UNIT, 10)  # 40 representation-noise pins at 1.30
    b = percentile_ci_diagnostic(
        {"dscr_min": dscr}, breach_thresholds={"dscr_min": 1.30}
    )["dscr_min"]["breach_probability_ci"]

    assert b["n_breaches"] == 0
    assert b["point"] == pytest.approx(0.0)
    assert b["ci_lower"] == pytest.approx(0.0)
    assert 0.0 < b["ci_upper"] < 1.0


def test_breach_probability_ci_still_counts_genuine_breaches() -> None:
    dscr = np.concatenate([np.tile(PIN_UNIT, 10), [1.10, 1.10]])
    b = percentile_ci_diagnostic(
        {"dscr_min": dscr}, breach_thresholds={"dscr_min": 1.30}
    )["dscr_min"]["breach_probability_ci"]

    assert b["n_breaches"] == 2
    assert b["point"] == pytest.approx(2.0 / 42.0)
    assert b["ci_lower"] <= b["point"] <= b["ci_upper"]


def test_engine_attaches_percentile_ci_without_changing_bands() -> None:
    from analytics.mc.engine import MonteCarloEngine

    cfg = yaml.safe_load(_LENDER.read_text())
    result = MonteCarloEngine(cfg, seed=1).run(n_trials=128)

    assert "percentile_ci" in result.metadata
    pci = result.metadata["percentile_ci"]
    assert isinstance(pci, dict) and pci
    d = next(iter(pci.values()))
    assert d["statistic"] == "percentile_ci"
    assert "90" in d["percentiles"]
    lv = d["percentiles"]["90"]
    assert {"point", "ci_lower", "ci_upper", "rank_lower", "rank_upper"} <= set(lv)
    # dscr_min carries a covenant breach CI (threshold wired from the resolved covenant).
    assert "dscr_min" in pci
    assert "breach_probability_ci" in pci["dscr_min"]
    breach = pci["dscr_min"]["breach_probability_ci"]
    dscr = np.asarray(result.trials["dscr_min"], dtype=float)
    dscr = dscr[np.isfinite(dscr)]
    expected = prob_breach(dscr, breach["threshold"])
    assert breach["point"] == pytest.approx(expected)
    assert breach["n_breaches"] == int(round(expected * dscr.size))
    # Additive only: the percentile bands the aggregator reports are still present.
    assert result.percentiles is not None
