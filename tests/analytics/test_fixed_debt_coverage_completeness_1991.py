"""Comprehensive completeness and validation tests for fixed-debt covenant coverage (#1991, #924).

Validates that fixed_debt_coverage_by_row fails closed on missing, duplicate, or nonfinite
required covenant rows, malformed committed schedules, unmapped positive debt service, and
misaligned bridge or construction periods. Validates Monte Carlo engine handling (no surviving-
subset breach probability in permissive mode, fail-loud in lender mode) and P90 consumer rejection
of incomplete views. All fixtures are 100% synthetic.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from analytics.finance import p90_recomputed_downside as p90
from analytics.mc import engine as mc_engine
from analytics.mc.engine import _trial_fixed_debt_min_dscr
from analytics.mc.fixed_debt_coverage import fixed_debt_coverage_by_row

# Synthetic base fixture: 3 operating rows (annual_row_index 0, 1, 2) mapped to debt periods 1, 2, 3.
# Period 0 is the bridge debt period (debt service 10.0, folds into row 0).
# Periods 1 and 2 have debt service 50.0. Period 3 has debt service 0.0 (zero-service row).
# Fees are 0.0 for all periods.
SYNTHETIC_BASE: Dict[str, Any] = {
    "annual_row_debt_period_map": [
        {"annual_row_index": 0, "debt_period": 1, "cfads_usd": 100.0},
        {"annual_row_index": 1, "debt_period": 2, "cfads_usd": 20.0},
        {"annual_row_index": 2, "debt_period": 3, "cfads_usd": 0.0},
    ],
    "debt_service_total": [10.0, 50.0, 50.0, 0.0],
    "senior_fee_usd": [0.0, 0.0, 0.0, 0.0],
    "bridge_debt_period": 0,
}


# =============================================================================
# 1. POSITIVE CONTROLS
# =============================================================================


def test_positive_control_complete_and_reordered() -> None:
    """Complete rows evaluate accurately; row reordering in trial map produces identical results."""
    # Row 0: service = 50.0 + 10.0 (bridge) = 60.0; net CFADS = 100.0; dscr = 100.0 / 60.0
    # Row 1: service = 50.0; net CFADS = 20.0; dscr = 20.0 / 50.0 = 0.4
    # Row 2: service = 0.0; zero service -> excluded from required covenant rows
    expected = [(0, 100.0, 100.0 / 60.0), (1, 20.0, 0.4)]
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, SYNTHETIC_BASE) == expected

    # Reordered trial map
    reordered_trial = copy.deepcopy(SYNTHETIC_BASE)
    reordered_trial["annual_row_debt_period_map"].reverse()
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, reordered_trial) == expected
    assert _trial_fixed_debt_min_dscr(SYNTHETIC_BASE, reordered_trial) == pytest.approx(
        0.4
    )


def test_positive_control_negative_cfads() -> None:
    """Negative CFADS in trial is valid and computes negative DSCR."""
    trial = copy.deepcopy(SYNTHETIC_BASE)
    trial["annual_row_debt_period_map"][1]["cfads_usd"] = -20.0
    res = fixed_debt_coverage_by_row(SYNTHETIC_BASE, trial)
    assert len(res) == 2
    assert res[1] == (1, -20.0, -0.4)
    assert _trial_fixed_debt_min_dscr(SYNTHETIC_BASE, trial) == pytest.approx(-0.4)


def test_positive_control_zero_service_row_omitted() -> None:
    """Zero-service covenant row does not require trial CFADS."""
    trial = copy.deepcopy(SYNTHETIC_BASE)
    # Pop row 2 (which has debt_service = 0.0)
    trial["annual_row_debt_period_map"].pop()
    expected = [(0, 100.0, 100.0 / 60.0), (1, 20.0, 0.4)]
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, trial) == expected


def test_positive_control_bridge_only_service() -> None:
    """When operating debt service is zero and only bridge debt service exists in row 0."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    base["debt_service_total"] = [10.0, 0.0, 0.0, 0.0]
    # Only row 0 has positive service (from bridge 10.0). Rows 1 and 2 have 0 service.
    trial = {
        "annual_row_debt_period_map": [{"annual_row_index": 0, "cfads_usd": 100.0}]
    }
    res = fixed_debt_coverage_by_row(base, trial)
    assert res == [(0, 100.0, 10.0)]


# =============================================================================
# 2. NEGATIVE / HOSTILE CONTROLS (FAIL-CLOSED INTEGRITY)
# =============================================================================


@pytest.mark.parametrize("missing_idx", [0, 1])
def test_negative_control_missing_required_row(missing_idx: int) -> None:
    """Missing any required positive-service covenant row returns empty list and None min_dscr."""
    trial = copy.deepcopy(SYNTHETIC_BASE)
    del trial["annual_row_debt_period_map"][missing_idx]
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, trial) == []
    assert _trial_fixed_debt_min_dscr(SYNTHETIC_BASE, trial) is None


def test_negative_control_duplicate_trial_row() -> None:
    """Duplicate annual_row_index in trial fails closed."""
    trial = copy.deepcopy(SYNTHETIC_BASE)
    dup = dict(trial["annual_row_debt_period_map"][1])
    dup["cfads_usd"] = 999.0
    trial["annual_row_debt_period_map"].append(dup)
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, trial) == []


def test_negative_control_duplicate_base_row() -> None:
    """Duplicate annual_row_index or debt_period in base fails closed."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    base["annual_row_debt_period_map"].append(base["annual_row_debt_period_map"][0])
    assert fixed_debt_coverage_by_row(base, base) == []


@pytest.mark.parametrize(
    "bad_cfads",
    [None, True, False, float("nan"), float("inf"), float("-inf"), "100.0", 10**1000],
)
def test_negative_control_bad_trial_cfads(bad_cfads: Any) -> None:
    """Invalid, nonfinite, boolean, string, or overflowing CFADS fails closed."""
    trial = copy.deepcopy(SYNTHETIC_BASE)
    trial["annual_row_debt_period_map"][1]["cfads_usd"] = bad_cfads
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, trial) == []


@pytest.mark.parametrize("bad_row_idx", [True, False, 1.5, -1, float("nan"), "1", None])
def test_negative_control_bad_row_index(bad_row_idx: Any) -> None:
    """Invalid, negative, fractional, or non-integer row indices fail closed."""
    trial = copy.deepcopy(SYNTHETIC_BASE)
    trial["annual_row_debt_period_map"][1]["annual_row_index"] = bad_row_idx
    assert fixed_debt_coverage_by_row(SYNTHETIC_BASE, trial) == []


def test_negative_control_incomplete_base_map() -> None:
    """Base map with missing operating rows (non-contiguous) fails closed."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    del base["annual_row_debt_period_map"][0]  # Missing row 0
    assert fixed_debt_coverage_by_row(base, base) == []


def test_negative_control_unmapped_positive_service() -> None:
    """Committed debt service in a period that is neither mapped nor bridge fails closed."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    # Add extra period 4 with positive debt service
    base["debt_service_total"].append(25.0)
    assert fixed_debt_coverage_by_row(base, base) == []


def test_negative_control_bad_debt_service_values() -> None:
    """Negative, NaN, or nonfinite values in debt_service_total fail closed."""
    base_neg = copy.deepcopy(SYNTHETIC_BASE)
    base_neg["debt_service_total"][1] = -10.0
    assert fixed_debt_coverage_by_row(base_neg, base_neg) == []

    base_nan = copy.deepcopy(SYNTHETIC_BASE)
    base_nan["debt_service_total"][1] = float("nan")
    assert fixed_debt_coverage_by_row(base_nan, base_nan) == []


def test_negative_control_bad_senior_fees() -> None:
    """Nonfinite, negative, or truncated senior fee schedules fail closed."""
    base_inf = copy.deepcopy(SYNTHETIC_BASE)
    base_inf["senior_fee_usd"][1] = float("inf")
    assert fixed_debt_coverage_by_row(base_inf, base_inf) == []

    base_short = copy.deepcopy(SYNTHETIC_BASE)
    base_short["senior_fee_usd"] = [0.0]  # shorter than service periods
    assert fixed_debt_coverage_by_row(base_short, base_short) == []


def test_negative_control_non_contiguous_base_periods() -> None:
    """Base operating periods that are swapped or non-contiguous fail closed."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    r = base["annual_row_debt_period_map"]
    r[0]["debt_period"], r[1]["debt_period"] = r[1]["debt_period"], r[0]["debt_period"]
    assert fixed_debt_coverage_by_row(base, base) == []


def test_negative_control_invalid_bridge_or_construction() -> None:
    """Misaligned bridge or construction periods fail closed."""
    base_bridge = copy.deepcopy(SYNTHETIC_BASE)
    base_bridge["bridge_debt_period"] = 99  # out of bounds
    assert fixed_debt_coverage_by_row(base_bridge, base_bridge) == []

    base_const = copy.deepcopy(SYNTHETIC_BASE)
    base_const["construction_periods"] = 5  # does not match bridge or first operating
    assert fixed_debt_coverage_by_row(base_const, base_const) == []


def test_negative_control_dscr_by_year_mismatch() -> None:
    """Declared dscr_by_year count mismatch fails closed."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    base["dscr_by_year"] = {0: 1.5, 1: 0.4, 2: None, 3: None}
    assert fixed_debt_coverage_by_row(base, base) == []


def test_negative_control_malformed_containers() -> None:
    """Malformed container types fail closed."""
    assert (
        fixed_debt_coverage_by_row(SYNTHETIC_BASE, {"annual_row_debt_period_map": 42})
        == []
    )
    assert (
        fixed_debt_coverage_by_row(
            {"annual_row_debt_period_map": "bad"}, SYNTHETIC_BASE
        )
        == []
    )


# =============================================================================
# 3. MONTE CARLO ENGINE INTEGRATION & QUALIFICATION
# =============================================================================


def _make_synthetic_engine_config(
    fixed_debt_stress: bool, allow_toy_fallback: bool
) -> Dict[str, Any]:
    """Build a minimal synthetic configuration for MonteCarloEngine testing."""
    return {
        "scenario": {"name": "synthetic_cfads_test"},
        "capex": {"usd_total": 100.0},
        "monte_carlo": {
            "fixed_debt_stress": fixed_debt_stress,
            "allow_toy_fallback": allow_toy_fallback,
            "fixed_debt_covenant": 1.20,
            "parameters": [
                {
                    "name": "capex.usd_total",
                    "low": 90.0,
                    "high": 110.0,
                    "distribution": "uniform",
                }
            ],
        },
    }


def test_mc_permissive_mode_handles_incomplete_trial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permissive MC mode marks fixed_debt_stress unavailable and preserves other metrics without breach probability."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    bad_trial = copy.deepcopy(SYNTHETIC_BASE)
    del bad_trial["annual_row_debt_period_map"][1]  # missing required row

    # Mock evaluate_with_overrides:
    # 1. Base evaluation (returns complete debt_result)
    # 2. Trial 0: complete
    # 3. Trial 1: incomplete (missing row)
    # 4. Trial 2: complete
    calls = iter(
        [
            {"debt_result": base},
            {"kpis": {"equity_npv": 100.0}, "debt_result": base},
            {"kpis": {"equity_npv": 200.0}, "debt_result": bad_trial},
            {"kpis": {"equity_npv": 300.0}, "debt_result": base},
        ]
    )
    monkeypatch.setattr(
        mc_engine, "evaluate_with_overrides", lambda *args, **kwargs: next(calls)
    )

    cfg = _make_synthetic_engine_config(fixed_debt_stress=True, allow_toy_fallback=True)
    engine = mc_engine.MonteCarloEngine(cfg, seed=42)
    res = engine.run(n_trials=3)

    stress = res.metadata.get("fixed_debt_stress")
    assert stress is not None
    assert stress["status"] == "unavailable"
    assert (
        "not every trial produced complete covenant-year coverage" in stress["reason"]
    )
    assert stress["n"] == 2
    assert stress["n_requested"] == 3
    assert "breach_probability" not in stress
    assert "min_dscr_p50" not in stress

    # Check other trial metrics are preserved
    assert list(res.trials["equity_npv"]) == [100.0, 200.0, 300.0]
    assert res.metadata.get("toy_fallback_count") == 0


def test_mc_strict_mode_raises_on_incomplete_trial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict/lender mode raises RuntimeError if any trial publishes incomplete covenant CFADS."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    bad_trial = copy.deepcopy(SYNTHETIC_BASE)
    del bad_trial["annual_row_debt_period_map"][1]

    calls = iter(
        [
            {"debt_result": base},
            {"kpis": {}, "debt_result": bad_trial},
        ]
    )
    monkeypatch.setattr(
        mc_engine, "evaluate_with_overrides", lambda *args, **kwargs: next(calls)
    )

    cfg = _make_synthetic_engine_config(
        fixed_debt_stress=True, allow_toy_fallback=False
    )
    engine = mc_engine.MonteCarloEngine(cfg, seed=42)
    with pytest.raises(RuntimeError, match="published no CFADS|base case"):
        engine.run(n_trials=1)


# =============================================================================
# 4. P90 RECOMPUTED DOWNSIDE CONSUMER INTEGRATION
# =============================================================================


def test_p90_consumer_rejects_incomplete_covenant_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P90 recomputed downside returns unavailable when downside run has incomplete covenant-year CFADS coverage."""
    down = copy.deepcopy(SYNTHETIC_BASE)
    del down["annual_row_debt_period_map"][1]

    calls = iter([{"debt_result": SYNTHETIC_BASE}, {"debt_result": down}])
    monkeypatch.setattr(p90, "evaluate_with_overrides", lambda **kwargs: next(calls))
    monkeypatch.setattr(p90, "p90_production_config", lambda cfg, ratio: cfg)
    monkeypatch.setattr(
        p90, "_covenant_cfads_on_interest", lambda *args: [100.0, 20.0, 0.0]
    )

    res = p90.recomputed_p90_downside(
        {"expected_results": {"net_aep_p50_gwh": 100.0, "net_aep_p90_gwh": 80.0}}
    )
    assert res["status"] == "unavailable"
    assert "incomplete fixed-debt covenant-year CFADS coverage" in res["reason"]


def test_p90_consumer_rejects_incomplete_sizing_downside(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P90 recomputed downside returns unavailable when sizing downside has incomplete coverage."""
    base = copy.deepcopy(SYNTHETIC_BASE)
    base["dual_dscr"] = {"downside_ratio": 0.85, "downside_source": "test"}

    calls = iter([{"debt_result": base}, {"debt_result": base}])
    monkeypatch.setattr(p90, "evaluate_with_overrides", lambda **kwargs: next(calls))
    monkeypatch.setattr(p90, "p90_production_config", lambda cfg, ratio: cfg)
    monkeypatch.setattr(
        p90, "_covenant_cfads_on_interest", lambda *args: [100.0, 20.0, 0.0]
    )

    # Intercept fixed_debt_coverage_by_row: return empty list on sizing view
    orig_cov = p90.fixed_debt_coverage_by_row

    def _mock_cov(base_d: Any, trial_d: Any) -> List[Any]:
        # Sizing view uses sizing factor
        if (
            trial_d.get("annual_row_debt_period_map", [{}])[0].get("cfads_usd")
            == 100.0 * 0.85
        ):
            return []  # simulate missing rows for sizing view
        return orig_cov(base_d, trial_d)

    monkeypatch.setattr(p90, "fixed_debt_coverage_by_row", _mock_cov)

    res = p90.recomputed_p90_downside(
        {"expected_results": {"net_aep_p50_gwh": 100.0, "net_aep_p90_gwh": 80.0}}
    )
    assert res["status"] == "unavailable"
    assert "incomplete fixed-debt sizing downside coverage" in res["reason"]
