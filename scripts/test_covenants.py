#!/usr/bin/env python3
"""Covenant metric tests (DSCR, LLCR, PLCR, lock-ups, sweeps)."""

from dutchbay_finmodel.core import ModelConfig, evaluate_covenants


def test_covenant_metrics_presence_and_sign():
    cfg = ModelConfig()
    cov = evaluate_covenants(cfg)

    assert cov["llcr"] > 0.0
    assert cov["plcr"] > 0.0
    assert isinstance(cov["dscr_breach_years"], list)
    assert isinstance(cov["lockup_years"], list)
    # Stylised sweep should never be negative
    assert cov["total_swept_cash_lkr"] >= 0.0
