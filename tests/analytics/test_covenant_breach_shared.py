"""#725 regression: one noise-tolerant covenant-breach primitive, no fabrication.

A dual-DSCR sculpt pins every trial's per-year minimum DSCR at EXACTLY the
covenant floor, so the per-trial ``dscr_min`` array clusters at the floor to
within floating-point noise (values like ``1.2999999999999996`` for a 1.30
floor). A strict ``arr < floor`` miscounts that sub-ULP scatter and fabricates an
~85-93% breach probability on a case whose TRUE breach probability is ``0.0``.
#657 fixed one path (``sensitivity.tail_risk``); #725 fixed the four siblings by
routing them all through :mod:`analytics.core.covenant_breach`.

Each fixed path is verified with a **sculpt-pinned repro** (prob == 0.0) AND a
**genuine-breach repro** (prob > 0), the two-sided guard the issue requires.
"""

from __future__ import annotations

import numpy as np
import pytest

import analytics.sensitivity.tail_risk as tail_risk
from analytics.capital_risk_layer_v14 import compute_capital_risk_layer
from analytics.contracts_v14 import MonteCarloResult
from analytics.core.covenant_breach import (
    PROB_BREACH_RTOL,
    is_floor_pinned,
    prob_breach,
)
from analytics.core.risk_metrics import RiskConfig, TailRiskAnalyzer
from analytics.mc.exports import (
    CovenantSpec,
    build_casper_risk_blocks,
    dscr_breach_probability,
)

try:
    import pandas  # noqa: F401

    HAS_PANDAS = True
except Exception:  # pragma: no cover
    HAS_PANDAS = False

FLOOR = 1.30

# One sculpt "pin unit": two values a ULP BELOW the floor, one AT it, one a ULP
# ABOVE. A strict ``< FLOOR`` counts the two below -> a fabricated 0.5 breach rate;
# the true rate is 0.0. Repeated, this is a per-trial pinned dscr_min array.
_PIN_UNIT = np.array([1.2999999999999996, 1.2999999999999998, 1.3, 1.3000000000000003])


def _pinned(n_reps: int = 50) -> np.ndarray:
    """A per-trial dscr_min array of ``4 * n_reps`` values pinned at the floor."""
    return np.tile(_PIN_UNIT, n_reps)


def test_strict_comparison_would_fabricate_the_bug_is_real() -> None:
    # Documents the defect the fix removes: the naive strict comparison the four
    # sibling paths used reports a spurious 50% breach on the pinned unit.
    assert float(np.mean(_PIN_UNIT < FLOOR)) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Shared primitive (single source of truth)
# ---------------------------------------------------------------------------


def test_prob_breach_pinned_is_zero() -> None:
    assert prob_breach(_pinned(), FLOOR) == pytest.approx(0.0)


def test_prob_breach_counts_genuine_breach_below_pin() -> None:
    mixed = np.concatenate([_pinned(), [1.10]])
    pb = prob_breach(mixed, FLOOR)
    assert pb > 0.0
    assert pb == pytest.approx(1.0 / mixed.size)


def test_prob_breach_clean_fraction_and_empty() -> None:
    assert prob_breach(np.array([1.20, 1.25, 1.35]), FLOOR) == pytest.approx(2 / 3)
    assert np.isnan(prob_breach(np.array([], dtype=float), FLOOR))


def test_is_floor_pinned_detects_and_rejects() -> None:
    assert is_floor_pinned(_pinned(), FLOOR) is True
    assert is_floor_pinned(np.array([1.0, 1.2, 1.3, 1.5, 2.0]), FLOOR) is False
    assert is_floor_pinned(np.array([], dtype=float), FLOOR) is False


def test_rtol_is_representation_noise_scale() -> None:
    assert PROB_BREACH_RTOL == 1e-9


def test_single_source_of_truth_all_paths_share_the_primitive() -> None:
    # tail_risk (#657) re-exports the canonical primitives, not private copies.
    assert tail_risk._prob_breach is prob_breach
    assert tail_risk._is_pinned_at_floor is is_floor_pinned


# ---------------------------------------------------------------------------
# Sibling path 1: analytics.capital_risk_layer_v14.compute_capital_risk_layer
# ---------------------------------------------------------------------------


def test_capital_risk_layer_pinned_dscr_no_fabricated_breach() -> None:
    rng = np.random.default_rng(725)
    dscr = _pinned(50)  # 200 pinned trials
    irr = rng.normal(0.08, 0.02, dscr.size)
    layer = compute_capital_risk_layer(
        equity_irr_samples=irr,
        min_dscr_samples=dscr,
        dscr_covenant=FLOOR,  # covenant == sculpt floor: the fabrication trigger
    )
    assert layer.dscr["prob_breach"] == pytest.approx(0.0)


def test_capital_risk_layer_counts_genuine_breach() -> None:
    rng = np.random.default_rng(725)
    dscr = np.concatenate([_pinned(50), np.full(20, 1.05)])  # 20 real breachers
    irr = rng.normal(0.08, 0.02, dscr.size)
    layer = compute_capital_risk_layer(
        equity_irr_samples=irr,
        min_dscr_samples=dscr,
        dscr_covenant=FLOOR,
    )
    assert layer.dscr["prob_breach"] == pytest.approx(20.0 / dscr.size)


# ---------------------------------------------------------------------------
# Sibling path 2: analytics.core.risk_metrics.covenant_breach_probability
# ---------------------------------------------------------------------------


def _analyzer() -> TailRiskAnalyzer:
    return TailRiskAnalyzer(
        RiskConfig(
            confidence_level=0.95,
            target_return=0.08,
            min_dscr=FLOOR,
            min_llcr=1.40,
            min_plcr=1.50,
        )
    )


def test_risk_metrics_pinned_dscr_no_fabricated_breach() -> None:
    # 50 scenarios x 4 years; every row's per-year min is a pinned value at FLOOR.
    dscr = _pinned(50).reshape(50, 4)
    llcr = np.full((50, 4), 1.60)  # comfortably above 1.40
    plcr = np.full((50, 4), 1.70)  # comfortably above 1.50
    out = _analyzer().covenant_breach_probability(dscr, llcr, plcr)
    assert out.dscr_breach_probability == pytest.approx(0.0)
    assert out.llcr_breach_probability == pytest.approx(0.0)
    assert out.plcr_breach_probability == pytest.approx(0.0)


def test_risk_metrics_counts_genuine_dscr_breach() -> None:
    dscr = _pinned(50).reshape(50, 4).copy()
    dscr[0, :] = 1.05  # one scenario genuinely breaches
    dscr[1, :] = 1.10  # a second
    llcr = np.full((50, 4), 1.60)
    plcr = np.full((50, 4), 1.70)
    out = _analyzer().covenant_breach_probability(dscr, llcr, plcr)
    assert out.dscr_breach_probability == pytest.approx(2.0 / 50)


# ---------------------------------------------------------------------------
# Sibling paths 3 & 4: analytics.mc.exports.dscr_breach_probability
# (one function, called at both mc/exports:179 and :248)
# ---------------------------------------------------------------------------


def test_mc_exports_dscr_breach_probability_pinned_is_zero() -> None:
    assert dscr_breach_probability(_pinned(), floor=FLOOR) == pytest.approx(0.0)


def test_mc_exports_dscr_breach_probability_counts_genuine() -> None:
    mixed = np.concatenate([_pinned(50), np.full(10, 1.05)])
    assert dscr_breach_probability(mixed, floor=FLOOR) == pytest.approx(
        10.0 / mixed.size
    )


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_casper_covenant_block_discloses_floor_pin() -> None:
    result = MonteCarloResult(
        summary={},
        metadata={"n_trials": int(_pinned().size)},
        trials={"dscr_min": list(_pinned())},
    )
    block = build_casper_risk_blocks(result, covenant=CovenantSpec(dscr_floor=FLOOR))[
        "covenant"
    ]
    assert block["prob_breach"] == pytest.approx(0.0)
    assert block["floor_pinned"] is True


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_casper_covenant_block_not_pinned_on_genuine_spread() -> None:
    rng = np.random.default_rng(725)
    dscr = rng.uniform(1.35, 1.80, 200)  # real spread, none at the floor
    result = MonteCarloResult(
        summary={},
        metadata={"n_trials": 200},
        trials={"dscr_min": list(dscr)},
    )
    block = build_casper_risk_blocks(result, covenant=CovenantSpec(dscr_floor=FLOOR))[
        "covenant"
    ]
    assert block["floor_pinned"] is False
