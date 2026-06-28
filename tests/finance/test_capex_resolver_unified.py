"""CAPEX resolver single-source-of-truth (external audit F-08).

The equity-distribution module had its own _extract_capex_usd that read the flat
capex.usd_total and ignored capex.derive_from_breakdown — a CCCDIR second source that could
diverge from the bottom-up CAPEX the debt engine sizes on (and that analytics.core.metrics
already routes through). It now delegates to the single resolver finance.debt_v14
._extract_capex_usd when derive_from_breakdown is set, so the equity base cannot diverge.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from analytics.core.metrics import _derive_capex_usd as metrics_capex
from finance.debt_v14 import _extract_capex_usd as debt_capex
from finance.equity_distribution_v14_hydra import _extract_capex_usd as equity_capex

_ROOT = Path(__file__).resolve().parents[2]
_FIVEUSC = _ROOT / "scenarios" / "dutchbay_lendercase_5usc_fixed_lkr.yaml"  # derive_from_breakdown: true
_CANON = _ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"  # flat usd_total


def test_equity_derives_from_breakdown_when_no_flat_total() -> None:
    # The discriminating case: derive_from_breakdown + a breakdown but NO flat usd_total.
    # Without the delegation the equity resolver finds no flat total and returns None;
    # with it, it returns the bottom-up sum (matching the debt engine).
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "breakdown": {"turbines_usd": 100_000_000.0, "civils_usd": 107_500_000.0},
        }
    }
    expected = debt_capex(dict(cfg))
    assert expected == pytest.approx(207_500_000.0)
    assert equity_capex(cfg) == pytest.approx(expected)


def test_all_three_resolvers_agree_under_derive_from_breakdown() -> None:
    cfg = yaml.safe_load(_FIVEUSC.read_text())
    assert (cfg.get("capex") or {}).get("derive_from_breakdown") is True
    d = debt_capex(dict(cfg))
    assert equity_capex(cfg) == pytest.approx(d)
    assert metrics_capex(cfg) == pytest.approx(d)


def test_equity_uses_flat_total_without_derive() -> None:
    cfg = yaml.safe_load(_CANON.read_text())
    assert not (cfg.get("capex") or {}).get("derive_from_breakdown")
    assert equity_capex(cfg) == pytest.approx(float(cfg["capex"]["usd_total"]))


def test_derive_path_ignores_a_stale_flat_total() -> None:
    # If a stale flat usd_total disagrees with the breakdown but stays within the debt
    # engine's 0.5% cross-check tolerance, equity must still report the bottom-up sum
    # (same basis as debt), not the flat value.
    base = 207_500_000.0
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "usd_total": base * 1.004,  # within the 0.5% cross-check tolerance
            "breakdown": {"turbines_usd": 100_000_000.0, "civils_usd": 107_500_000.0},
        }
    }
    assert equity_capex(cfg) == pytest.approx(debt_capex(copy.deepcopy(cfg)))
    assert equity_capex(cfg) == pytest.approx(base)  # bottom-up, not the 1.004x flat
