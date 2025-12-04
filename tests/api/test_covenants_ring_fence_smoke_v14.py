"""
Ring-fence covenant smoke test for v14 lender cases.

This is *not* a fine-grained regression test – it is a guardrail that:
- Ensures DSCR never drops below a minimum covenant threshold.
- Flags any residual balloon as a covenant red flag.
- Optionally checks LLCR/PLCR when available.

Tuning notes:
- Adjust BASE_CONFIG_PATH to your lender case scenario.
- Tighten DSCR_MIN_THRESHOLD / LLCR/PLCR thresholds once the case is frozen.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import pytest

from run_full_pipeline_v14 import run_v14_pipeline

# TODO: point this to the canonical lender case once final:
# e.g. "scenarios/dutchbay_lendercase_2025Q4.yaml"
BASE_CONFIG_PATH = "scenarios/test/base_scenario.yaml"

# Conservative but permissive starter thresholds – tune upwards when lenders lock.
DSCR_MIN_THRESHOLD = 1.00
LLCR_MIN_THRESHOLD = 1.00
PLCR_MIN_THRESHOLD = 1.00


def _finite_dscr_values(dscr_series: List[float]) -> List[float]:
    """Filter DSCR series down to finite, operational periods only."""
    finite: List[float] = []
    for v in dscr_series:
        if v is None:
            continue
        if isinstance(v, (int, float)) and not math.isinf(v) and not math.isnan(v):
            finite.append(float(v))
    return finite


@pytest.mark.smoke
def test_ring_fence_covenants_smoke() -> None:
    """
    High-level covenant sanity check on the lender/base case.

    Verifies:
    - scenario_result dict is populated.
    - DSCR never breaches the minimum covenant threshold.
    - Balloon, if present, is explicitly flagged in the covenant payload.
    - LLCR/PLCR, when available, clear basic >1.0 style thresholds.
    """
    # Run the canonical v14 pipeline
    result: Dict[str, Any] = run_v14_pipeline(
        config=BASE_CONFIG_PATH,
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )

    # In the v14 pipeline, scenario_result is intentionally a plain dict so the
    # CLI can JSON-serialise the whole payload.
    scenario_result = result.get("scenario_result") or {}
    assert isinstance(
        scenario_result, dict
    ), "scenario_result must be a dict-like payload"

    # ------------------------------
    # DSCR profile sanity
    # ------------------------------
    dscr_series = list(scenario_result.get("dscr_series") or [])
    finite_dscr = _finite_dscr_values(dscr_series)

    # We expect at least some finite DSCR values in the operational period
    assert finite_dscr, "No finite DSCR values found in scenario_result['dscr_series']"

    min_dscr = min(finite_dscr)
    assert (
        min_dscr >= DSCR_MIN_THRESHOLD
    ), f"Ring-fence breach: min DSCR {min_dscr:.3f} < {DSCR_MIN_THRESHOLD:.3f}"

    # ------------------------------
    # Covenant snapshot payload
    # ------------------------------
    covenants = scenario_result.get("debt_covenants") or {}
    assert isinstance(covenants, dict), "debt_covenants must be a dict-like payload"

    cov_dscr_min = float(covenants.get("dscr_min", 0.0))
    assert pytest.approx(cov_dscr_min, rel=1e-6) == pytest.approx(
        min_dscr, rel=1e-6
    ), "Debt covenant dscr_min should match series minimum"

    balloon_flag = bool(covenants.get("balloon_flag", False))
    balloon_remaining = float(covenants.get("balloon_remaining", 0.0))

    if balloon_flag:
        assert (
            balloon_remaining > 0.0
        ), "balloon_flag=True but balloon_remaining is not > 0.0"
    else:
        # If no balloon flagged, outstanding amount should be ~zero by end of tenor.
        assert balloon_remaining <= 1e-6

    # ------------------------------
    # LLCR / PLCR (optional)
    # ------------------------------
    llcr = covenants.get("llcr")
    if llcr is not None:
        llcr = float(llcr)
        assert llcr >= LLCR_MIN_THRESHOLD, f"LLCR {llcr:.3f} < {LLCR_MIN_THRESHOLD:.3f}"

    plcr = covenants.get("plcr")
    if plcr is not None:
        plcr = float(plcr)
        assert plcr >= PLCR_MIN_THRESHOLD, f"PLCR {plcr:.3f} < {PLCR_MIN_THRESHOLD:.3f}"

    # ------------------------------
    # Meta sanity: max debt vs profile
    # ------------------------------
    max_debt_usd = float(scenario_result.get("max_debt_usd") or 0.0)
    debt_result = result.get("debt_result") or {}
    debt_outstanding = debt_result.get("debt_outstanding") or []

    if debt_outstanding:
        peak_outstanding = max(float(x) for x in debt_outstanding)
        # Soft check with a generous tolerance to allow for IDC, FX etc.
        assert peak_outstanding > 0.0
        assert (
            peak_outstanding >= 0.5 * max_debt_usd
        ), "Peak outstanding looks inconsistent with max_debt_usd KPI"
