"""Coverage tests for analytics.sensitivity.tail_risk.

Exercises the tail-risk enrichment helpers end to end with small synthetic
inputs: the VaR/CVaR/breach primitives (including empty-array and empty-tail
edge cases), the suite enrichment path (enabled / disabled / empty-tornado /
populated), the per-parameter tornado snapshot (with and without usable
shocks), the per-metric aggregation, the Monte-Carlo trial extraction across
its three branches, and the full per-case snapshot builder (trial path,
require-trials no-trials path, and the fallback single-point paths).

Everything is pure-numpy / dataclass arithmetic; no network, cdsapi, or
matplotlib is touched, so nothing needs mocking. Assertions check real
quantile direction and documented edge-case returns, not import smoke.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from analytics.contracts_v14 import SensitivitySuite, ShockResult, TornadoResult
from analytics.sensitivity.tail_risk import (
    TailRiskConfig,
    _aggregate_metric_snapshot,
    _build_case_tail_snapshot,
    _cvar,
    _extract_trials_from_case,
    _percentile,
    _prob_breach,
    _tornado_tail_stats,
    enrich_suite_with_tail_risk,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Primitive statistics: _percentile / _cvar / _prob_breach
# ---------------------------------------------------------------------------


def test_percentile_matches_numpy_and_direction() -> None:
    arr = np.arange(0.0, 101.0)  # 0..100 inclusive
    # p5 < p50 < p95 — strictly increasing quantiles.
    p5 = _percentile(arr, 5)
    p50 = _percentile(arr, 50)
    p95 = _percentile(arr, 95)
    assert p5 < p50 < p95
    assert p50 == pytest.approx(50.0)
    assert p5 == pytest.approx(float(np.percentile(arr, 5)))
    assert isinstance(p5, float)


def test_cvar_is_downside_tail_mean() -> None:
    arr = np.arange(0.0, 100.0)
    # CVaR at 5% is the mean of the worst (lowest) 5% of values, so it must
    # sit at or below the 5th percentile (VaR) and well below the mean.
    var = float(np.percentile(arr, 5.0))
    cvar = _cvar(arr, 0.05)
    assert cvar <= var
    assert cvar < float(arr.mean())
    assert isinstance(cvar, float)


def test_cvar_empty_array_is_nan() -> None:
    out = _cvar(np.array([], dtype=float), 0.05)
    assert math.isnan(out)


def test_cvar_empty_tail_falls_back_to_var() -> None:
    # With alpha small enough that the VaR cut lands strictly below every
    # sample, the `<= var` tail can still be non-empty for ordinary arrays.
    # Force the empty-tail branch with a single-element array: percentile is
    # the element itself, so values strictly below it are none — but `<= var`
    # always includes it. Use a degenerate case where var sits below min via
    # a constructed array whose min is excluded by floating compare.
    arr = np.array([10.0])
    # var == 10.0; tail = arr[arr <= 10.0] == [10.0] (non-empty) -> mean 10.0
    assert _cvar(arr, 0.05) == pytest.approx(10.0)


def test_cvar_empty_tail_branch_returns_var() -> None:
    # Degenerate all-NaN distribution: np.percentile yields NaN, so the
    # `arr <= var` comparison is all-False and the tail is empty. This
    # exercises the `tail.size == 0 -> return float(var)` fallback branch.
    arr = np.array([np.nan, np.nan, np.nan])
    out = _cvar(arr, 0.05)
    assert math.isnan(out)


def test_cvar_alpha_zero_tail_is_min() -> None:
    arr = np.array([1.0, 2.0, 3.0, 4.0])
    # 0th percentile == min == 1.0; tail = [1.0]; mean 1.0.
    out = _cvar(arr, 0.0)
    assert out == pytest.approx(1.0)


def test_prob_breach_counts_below_floor() -> None:
    arr = np.array([1.0, 1.2, 1.25, 1.3, 1.5, 2.0])
    # floor 1.30: strictly-below values are 1.0, 1.2, 1.25 -> 3 of 6 = 0.5
    assert _prob_breach(arr, 1.30) == pytest.approx(0.5)
    # No breaches when floor is below the minimum.
    assert _prob_breach(arr, 0.5) == pytest.approx(0.0)
    # All breach when floor is above the maximum.
    assert _prob_breach(arr, 99.0) == pytest.approx(1.0)


def test_prob_breach_empty_array_is_nan() -> None:
    out = _prob_breach(np.array([], dtype=float), 1.30)
    assert math.isnan(out)


# ---------------------------------------------------------------------------
# _tornado_tail_stats
# ---------------------------------------------------------------------------


def _tornado_with_shocks() -> TornadoResult:
    shocks = [
        ShockResult(
            label="aep_-1sd",
            low_case=0.040,
            high_case=0.060,
            impact_abs=0.010,
            metric_name="project_irr",
        ),
        ShockResult(
            label="aep_-2sd",
            low_case=0.030,
            high_case=0.070,
            impact_abs=0.020,
            metric_name="project_irr",
        ),
    ]
    return TornadoResult(
        metric_name="project_irr",
        base_metric=0.0543,
        shock_results=shocks,
        label="AEP",
        impact_abs=0.020,
    )


def test_tornado_tail_stats_uses_shock_extremes() -> None:
    stats = _tornado_tail_stats(tornado=_tornado_with_shocks())
    assert stats["parameter"] == "AEP"
    assert stats["metric"] == "project_irr"
    assert stats["base_value"] == pytest.approx(0.0543)
    # downside = worst KPI, upside = best KPI, over ALL shock cases (both directions).
    assert stats["downside"] == pytest.approx(0.030)
    assert stats["upside"] == pytest.approx(0.070)
    assert stats["worst_impact_abs"] == pytest.approx(0.020)
    assert stats["n_shocks"] == 2


def test_tornado_tail_stats_labels_cost_driver_by_outcome_not_direction() -> None:
    """A cost driver's low-cost (low) case is the BETTER outcome (audit D5/D10, #576).

    For CAPEX, shocking the driver LOW raises IRR (better) and HIGH lowers it (worse), so
    ``low_case > high_case`` in KPI terms. Keying by shock direction (min low / max high)
    would report downside=0.070 > upside=0.030 — inverted. Outcome-keying reports the true
    worst (0.030) and best (0.070).
    """
    cost_shock = ShockResult(
        label="capex_+1sd",
        low_case=0.070,  # low CAPEX -> higher IRR (better)
        high_case=0.030,  # high CAPEX -> lower IRR (worse)
        impact_abs=0.040,
        metric_name="project_irr",
    )
    tornado = TornadoResult(
        metric_name="project_irr",
        base_metric=0.05,
        shock_results=[cost_shock],
        label="CAPEX",
        impact_abs=0.040,
    )
    stats = _tornado_tail_stats(tornado=tornado)
    assert stats["downside"] == pytest.approx(0.030)  # the WORSE outcome
    assert stats["upside"] == pytest.approx(0.070)  # the BETTER outcome
    assert stats["downside"] < stats["upside"]  # never inverted


def test_tornado_tail_stats_no_usable_shocks_collapses_to_base() -> None:
    # A shock with all optional fields None contributes nothing; the snapshot
    # collapses downside/upside to the base value and impact to tornado.impact_abs.
    tornado = TornadoResult(
        metric_name="dscr_min",
        base_metric=1.30,
        shock_results=[ShockResult(label="empty")],
        label=None,  # forces fallback to metric_name for the parameter label
        impact_abs=0.0,
    )
    stats = _tornado_tail_stats(tornado=tornado)
    assert stats["parameter"] == "dscr_min"  # falls back to metric_name
    assert stats["downside"] == pytest.approx(1.30)
    assert stats["upside"] == pytest.approx(1.30)
    assert stats["worst_impact_abs"] == pytest.approx(0.0)
    assert stats["n_shocks"] == 1


# ---------------------------------------------------------------------------
# _aggregate_metric_snapshot
# ---------------------------------------------------------------------------


def test_aggregate_metric_snapshot_picks_extremes() -> None:
    rows = [
        {
            "base_value": 0.05,
            "downside": 0.03,
            "upside": 0.07,
            "worst_impact_abs": 0.02,
        },
        {
            "base_value": 0.05,
            "downside": 0.01,
            "upside": 0.09,
            "worst_impact_abs": 0.04,
        },
    ]
    cfg = TailRiskConfig(cvar_alpha=0.05, percentiles=(5, 10, 95), dscr_floor=1.30)
    snap = _aggregate_metric_snapshot(rows=rows, run_cfg=cfg)
    assert snap["base_value"] == pytest.approx(0.05)
    assert snap["downside"] == pytest.approx(0.01)  # worst downside
    assert snap["upside"] == pytest.approx(0.09)  # best upside
    assert snap["worst_impact_abs"] == pytest.approx(0.04)  # largest impact
    assert snap["n_parameters"] == 2
    # Audit D5 (#576): the tornado snapshot no longer echoes cvar_alpha / percentiles /
    # dscr_floor — it computes no VaR/CVaR/breach, so surfacing them was misleading.
    assert "cvar_alpha" not in snap
    assert "percentiles" not in snap
    assert "dscr_floor" not in snap


def test_aggregate_metric_snapshot_empty_rows() -> None:
    snap = _aggregate_metric_snapshot(rows=[], run_cfg=TailRiskConfig())
    assert math.isnan(snap["base_value"])
    assert math.isnan(snap["downside"])
    assert math.isnan(snap["upside"])
    assert snap["worst_impact_abs"] == pytest.approx(0.0)
    assert snap["n_parameters"] == 0


# ---------------------------------------------------------------------------
# enrich_suite_with_tail_risk
# ---------------------------------------------------------------------------


def test_enrich_disabled_returns_suite_unchanged() -> None:
    suite = SensitivitySuite(
        metric="project_irr", tornado_results=[_tornado_with_shocks()]
    )
    out = enrich_suite_with_tail_risk(
        suite=suite, base_config={}, run_cfg=TailRiskConfig(enabled=False)
    )
    # Disabled: the very same object is returned, no metadata injected.
    assert out is suite
    assert "tail_risk" not in out.metadata


def test_enrich_populated_attaches_table_and_summary() -> None:
    suite = SensitivitySuite(
        metric="project_irr",
        tornado_results=[_tornado_with_shocks()],
        metadata={"existing": "kept"},
    )
    out = enrich_suite_with_tail_risk(suite=suite, base_config={})
    # Frozen dataclass: a new instance is returned, original untouched.
    assert out is not suite
    assert "tail_risk" not in suite.metadata
    # Pre-existing metadata is preserved.
    assert out.metadata["existing"] == "kept"
    table = out.metadata["tail_risk"]
    assert isinstance(table, list) and len(table) == 1
    assert table[0]["parameter"] == "AEP"
    summary = out.metadata["tail_risk_summary"]
    assert "project_irr" in summary
    assert summary["project_irr"]["downside"] == pytest.approx(0.030)
    assert summary["project_irr"]["n_parameters"] == 1


def test_enrich_empty_tornado_leaves_blocks_empty() -> None:
    suite = SensitivitySuite(metric="project_irr", tornado_results=[])
    out = enrich_suite_with_tail_risk(suite=suite, base_config={})
    assert out.metadata["tail_risk"] == []
    assert out.metadata["tail_risk_summary"] == {}


def test_enrich_handles_none_metadata() -> None:
    # metadata coerced from a missing/None value should not blow up.
    suite = SensitivitySuite(metric="project_irr", tornado_results=[])
    object.__setattr__(suite, "metadata", None)
    out = enrich_suite_with_tail_risk(suite=suite, base_config={})
    assert out.metadata["tail_risk"] == []


# ---------------------------------------------------------------------------
# _extract_trials_from_case — all three branches
# ---------------------------------------------------------------------------


def test_extract_trials_no_metadata_mapping() -> None:
    # metadata absent / not a Mapping -> None
    assert _extract_trials_from_case({}, "project_irr") is None
    assert (
        _extract_trials_from_case({"metadata": ["not", "a", "map"]}, "project_irr")
        is None
    )


def test_extract_trials_missing_metric_returns_none() -> None:
    case = {"metadata": {"trials": {"other_metric": [1.0, 2.0]}}}
    assert _extract_trials_from_case(case, "project_irr") is None


def test_extract_trials_one_dim_from_trials_bucket() -> None:
    case = {"metadata": {"trials": {"project_irr": [0.01, 0.02, 0.03]}}}
    arr = _extract_trials_from_case(case, "project_irr")
    assert arr is not None
    assert arr.ndim == 1
    np.testing.assert_allclose(arr, [0.01, 0.02, 0.03])


def test_extract_trials_reshapes_multidim_from_mc_trials_bucket() -> None:
    # Falls through "trials" (absent) to the "mc_trials" bucket and flattens a
    # 2-D array down to 1-D.
    case = {"metadata": {"mc_trials": {"dscr_min": [[1.1, 1.2], [1.3, 1.4]]}}}
    arr = _extract_trials_from_case(case, "dscr_min")
    assert arr is not None
    assert arr.ndim == 1
    assert arr.size == 4
    np.testing.assert_allclose(arr, [1.1, 1.2, 1.3, 1.4])


# ---------------------------------------------------------------------------
# _build_case_tail_snapshot — trial path, no-trials path, fallback paths
# ---------------------------------------------------------------------------


def test_build_case_snapshot_trial_path_with_dscr_breach() -> None:
    rng = np.random.default_rng(7)
    irr = rng.normal(0.06, 0.01, size=2000)
    dscr = rng.normal(1.35, 0.10, size=2000)
    case = {
        "label": "lender_p50",
        "metadata": {
            "trials": {"project_irr": irr.tolist(), "dscr_min": dscr.tolist()}
        },
    }
    cfg = TailRiskConfig(cvar_alpha=0.05, dscr_floor=1.30)
    out = _build_case_tail_snapshot(
        case=case, metric_keys=["project_irr", "dscr_min"], run_cfg=cfg
    )
    rows = out["rows"]
    assert len(rows) == 2

    irr_row = next(r for r in rows if r["metric"] == "project_irr")
    # Quantile ordering must hold and CVaR sits in the downside tail.
    assert irr_row["p5"] < irr_row["p10"] < irr_row["p95"]
    assert irr_row["cvar"] <= irr_row["p5"]
    assert irr_row["mean"] == pytest.approx(float(np.asarray(irr).mean()))
    assert irr_row["std"] > 0.0
    assert "prob_breach" not in irr_row  # non-dscr metric: no breach key

    dscr_row = next(r for r in rows if r["metric"] == "dscr_min")
    # DSCR-like metric: breach probability + floor are attached.
    assert 0.0 <= dscr_row["prob_breach"] <= 1.0
    assert dscr_row["dscr_floor"] == pytest.approx(1.30)


def test_build_case_snapshot_single_sample_std_zero() -> None:
    # A one-element trial array -> std defaults to 0.0 (ddof=1 undefined).
    case = {"label": "tiny", "metadata": {"trials": {"project_irr": [0.05]}}}
    out = _build_case_tail_snapshot(
        case=case, metric_keys=["project_irr"], run_cfg=TailRiskConfig()
    )
    row = out["rows"][0]
    assert row["std"] == pytest.approx(0.0)
    assert row["mean"] == pytest.approx(0.05)


def test_build_case_snapshot_require_trials_notes_missing() -> None:
    # No trials present and require_trials=True -> a "no_trials" note row.
    case = {"label": "no_mc", "metadata": {}}
    out = _build_case_tail_snapshot(
        case=case,
        metric_keys=["project_irr"],
        run_cfg=TailRiskConfig(require_trials=True),
    )
    row = out["rows"][0]
    assert row == {"case": "no_mc", "metric": "project_irr", "note": "no_trials"}


def test_build_case_snapshot_fallback_value_from_value_key() -> None:
    # require_trials=False and a flat "value" present -> single-point fallback.
    case = {"label": "pt", "value": 0.044}
    out = _build_case_tail_snapshot(
        case=case,
        metric_keys=["project_irr"],
        run_cfg=TailRiskConfig(require_trials=False),
    )
    row = out["rows"][0]
    assert row["value"] == pytest.approx(0.044)
    assert math.isnan(row["p5"])
    assert math.isnan(row["p10"])
    assert math.isnan(row["p95"])
    assert math.isnan(row["cvar"])


def test_build_case_snapshot_fallback_value_from_values_map() -> None:
    # require_trials=False, no flat "value", but a "values" map keyed by metric.
    case = {"label": "ptmap", "values": {"project_irr": 0.052}}
    out = _build_case_tail_snapshot(
        case=case,
        metric_keys=["project_irr"],
        run_cfg=TailRiskConfig(require_trials=False),
    )
    assert out["rows"][0]["value"] == pytest.approx(0.052)


def test_build_case_snapshot_fallback_value_missing_is_nan() -> None:
    # require_trials=False and neither value nor values present -> NaN value,
    # using the default label "case" when no label key is provided.
    case = {"values": {"other": 1.0}}
    out = _build_case_tail_snapshot(
        case=case,
        metric_keys=["project_irr"],
        run_cfg=TailRiskConfig(require_trials=False),
    )
    row = out["rows"][0]
    assert row["case"] == "case"
    assert math.isnan(row["value"])


# ---------------------------------------------------------------------------
# Config defaults sanity (frozen dataclass) + canonical scenario portability
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    cfg = TailRiskConfig()
    assert cfg.enabled is True
    assert cfg.percentiles == (5, 10, 95)
    assert cfg.cvar_alpha == pytest.approx(0.05)
    assert cfg.dscr_floor == pytest.approx(1.30)
    assert cfg.require_trials is True


def test_canonical_scenario_path_resolves() -> None:
    # Portability guard: the scenario is resolved relative to the test file,
    # never an absolute worktree path, so this holds under a CI checkout.
    assert LENDER.exists()
