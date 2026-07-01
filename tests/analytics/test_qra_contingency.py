"""QRA-driven CAPEX contingency (AACE RP 119R-21).

Contingency sized by a parametric quantitative risk analysis (base-cost uncertainty x
confidence z-score), not a fixed percentage. Opt-in via capex.contingency.method: qra;
default 'fixed' keeps the explicit line item (backward-compatible).
"""

from __future__ import annotations

import pytest

from analytics.cost.contingency import ContingencyResult, resolve_contingency
from finance.debt_v14 import _extract_capex_usd

_Z80 = 0.8416  # one-sided z at P80


def test_qra_contingency_is_base_times_sigma_times_z() -> None:
    r = resolve_contingency(
        100_000_000.0,
        {
            "contingency": {
                "method": "qra",
                "base_cost_uncertainty_pct": 10.0,
                "confidence_level": 0.80,
            }
        },
    )
    assert isinstance(r, ContingencyResult)
    assert r.method == "qra"
    assert r.contingency_usd == pytest.approx(
        100_000_000.0 * 0.10 * _Z80, rel=1e-3
    )  # ~8.42M
    assert r.z_score == pytest.approx(_Z80, abs=1e-3)


def test_higher_confidence_raises_contingency() -> None:
    cfg = {"contingency": {"method": "qra", "base_cost_uncertainty_pct": 10.0}}
    p80 = resolve_contingency(
        100e6, {"contingency": {**cfg["contingency"], "confidence_level": 0.80}}
    )
    p90 = resolve_contingency(
        100e6, {"contingency": {**cfg["contingency"], "confidence_level": 0.90}}
    )
    assert p90.contingency_usd > p80.contingency_usd  # P90 needs more contingency


def test_fixed_method_returns_zero_increment() -> None:
    r = resolve_contingency(100e6, {"contingency": {"method": "fixed"}})
    assert r.method == "fixed"
    assert r.contingency_usd == 0.0
    # no contingency block at all -> also fixed
    assert resolve_contingency(100e6, {}).method == "fixed"


def test_qra_requires_uncertainty_and_valid_confidence() -> None:
    with pytest.raises(ValueError, match="base_cost_uncertainty_pct"):
        resolve_contingency(100e6, {"contingency": {"method": "qra"}})
    with pytest.raises(ValueError, match="confidence_level"):
        resolve_contingency(
            100e6,
            {
                "contingency": {
                    "method": "qra",
                    "base_cost_uncertainty_pct": 10.0,
                    "confidence_level": 1.0,
                }
            },
        )


def test_capex_derivation_uses_qra_contingency() -> None:
    """derive_from_breakdown + QRA recomputes contingency off the base (ex-contingency line)."""
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "contingency": {
                "method": "qra",
                "base_cost_uncertainty_pct": 12.0,
                "confidence_level": 0.80,
            },
            "breakdown": {
                "wtg_usd": 110_000_000.0,
                "bop_usd": 30_000_000.0,
                "grid_usd": 12_000_000.0,
                "contingency_usd": 2_000_000.0,  # fixed line is IGNORED under QRA
            },
        }
    }
    base = 152_000_000.0  # excludes the fixed contingency line
    expected = base + base * 0.12 * _Z80
    assert _extract_capex_usd(cfg) == pytest.approx(expected, rel=1e-3)  # ~167.35M


def test_capex_derivation_default_is_breakdown_sum() -> None:
    """No contingency block -> the breakdown sum stands (backward-compatible)."""
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "usd_total": 154_000_000.0,
            "breakdown": {
                "wtg_usd": 110e6,
                "bop_usd": 30e6,
                "grid_usd": 12e6,
                "contingency_usd": 2e6,
            },
        }
    }
    assert _extract_capex_usd(cfg) == pytest.approx(154_000_000.0, rel=1e-9)
