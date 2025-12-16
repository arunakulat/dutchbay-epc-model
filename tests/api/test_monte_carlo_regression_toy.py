# tests/api/test_monte_carlo_regression_toy.py
# Sprint 10: FAST regression tests using reduced-scale toy config

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.monte_carlo_v14 import run_monte_carlo

# ---------------------------------------------------------------------------
# FAST test configs (20 iterations, ~30 seconds)
# ---------------------------------------------------------------------------

MC_CONFIG_PATH = Path("config/monte_carlo_regression_toy.yaml")
BASE_SCENARIO_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


# ---------------------------------------------------------------------------
# Helper to pretty-print Monte CarloResult-like objects in assertions
# ---------------------------------------------------------------------------


def _result_to_dict(mc_result: Any) -> Dict[str, Any]:
    """
    Convert MonteCarloResult (pydantic/dataclass) into a plain dict for
    debugging and assertion messages. Falls back to __dict__ if needed.
    """
    if hasattr(mc_result, "model_dump"):
        return mc_result.model_dump()
    if hasattr(mc_result, "dict"):
        # pydantic v1-style
        return mc_result.dict()  # type: ignore[call-arg]
    if hasattr(mc_result, "__dict__"):
        return dict(mc_result.__dict__)
    return {"_repr": repr(mc_result)}


# ---------------------------------------------------------------------------
# Regression bands – TUNE THESE AFTER FIRST GOOD RUN
# ---------------------------------------------------------------------------
#
# Run once, print the actual stats, then tighten these ranges to something
# lender-sensible (e.g. ±0.5–1.0 percentage point on IRR, ±5–10% on NPV).
#
# The idea is:
#   seed=42 + toy config (20 iterations) + v14 engine + MC wiring → deterministic band.
#
# ---------------------------------------------------------------------------

# Placeholder bands – replace with actual numbers once you inspect the output.
IRR_P50_LOW = 0.10  # TODO: update to actual ~P50 IRR - margin
IRR_P50_HIGH = 0.20  # TODO: update to actual ~P50 IRR + margin

NPV_P50_LOW = -1e9  # TODO: tighten after first run
NPV_P50_HIGH = 1e9  # TODO: tighten after first run

DSCR_P10_LOW = 1.10  # TODO: update to actual ~P10 DSCR - margin
DSCR_P10_HIGH = 1.60  # TODO: update to actual ~P10 DSCR + margin


# ---------------------------------------------------------------------------
# FAST Tests (20 iterations, ~30 seconds total)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_monte_carlo_toy_regression_is_stable() -> None:
    """
    FAST regression check for the v14 Monte Carlo engine.

    Configuration:
    - 20 iterations (reduced from 500 for rapid testing)
    - Single 'base_case' scenario
    - Seed fixed at 42 for reproducibility
    - Expected runtime: ~20-30 seconds

    This test locks P50 IRR, P50 NPV and P10 DSCR into regression bands.
    Any silent drift in the finance engine, evaluator, or MC wiring should
    trip this test once you've tuned the bands above.

    Production validation: see monte_carlo_regression_production.yaml
    """
    # ===== P1.2 OPTIMIZATION: Skip CSV writes during tests =====
    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        write_output=False,
    )

    # 1) We expect at least one scenario and specifically 'base_case'.
    assert results, "Monte Carlo returned no scenario results"
    assert (
        "base_case" in results
    ), f"Expected scenario 'base_case' in MC results; got {list(results.keys())}"

    mc_result = results["base_case"]
    data = _result_to_dict(mc_result)

    irr_p50 = data.get("project_irr_p50")
    npv_p50 = data.get("project_npv_p50")
    dscr_p10 = data.get("dscr_min_p10")

    assert isinstance(
        irr_p50, (int, float)
    ), f"project_irr_p50 missing or not numeric: {irr_p50!r}"
    assert isinstance(
        npv_p50, (int, float)
    ), f"project_npv_p50 missing or not numeric: {npv_p50!r}"
    assert isinstance(
        dscr_p10, (int, float)
    ), f"dscr_min_p10 missing or not numeric: {dscr_p10!r}"

    # 2) Assert IRR/NPV/DSCR lie inside configured regression bands.
    assert IRR_P50_LOW <= irr_p50 <= IRR_P50_HIGH, (
        f"P50 IRR {irr_p50:.6f} outside expected band "
        f"[{IRR_P50_LOW:.6f}, {IRR_P50_HIGH:.6f}]"
    )

    assert NPV_P50_LOW <= npv_p50 <= NPV_P50_HIGH, (
        f"P50 NPV {npv_p50:.2f} outside expected band "
        f"[{NPV_P50_LOW:.2f}, {NPV_P50_HIGH:.2f}]"
    )

    assert DSCR_P10_LOW <= dscr_p10 <= DSCR_P10_HIGH, (
        f"P10 DSCR {dscr_p10:.6f} outside expected band "
        f"[{DSCR_P10_LOW:.6f}, {DSCR_P10_HIGH:.6f}]"
    )


def test_monte_carlo_toy_precisions_are_reported() -> None:
    """
    Guard that the new SE (standard error) fields are wired and non-pathological.

    We don't fix exact SE values here, but we require:
    - project_irr_se, project_npv_se, dscr_min_se are present,
    - they are finite (not NaN / inf),
    - and non-negative.

    These fields enable confidence interval reporting:
      E.g., P50 IRR ± 1.96 * SE → 95% CI
    """
    # ===== P1.2 OPTIMIZATION: Skip CSV writes during tests =====
    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        write_output=False,
    )

    assert results, "Monte Carlo returned no scenario results"

    mc_result = results.get("base_case") or next(iter(results.values()))
    data = _result_to_dict(mc_result)

    for field in ("project_irr_se", "project_npv_se", "dscr_min_se"):
        value = data.get(field)
        assert isinstance(
            value, (int, float)
        ), f"{field} missing or not numeric: {value!r}"
        assert not math.isnan(value), f"{field} is NaN"
        assert math.isfinite(value), f"{field} is not finite: {value!r}"
        assert value >= 0.0, f"{field} is negative: {value!r}"
