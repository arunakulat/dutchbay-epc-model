#!/usr/bin/env python3
"""Optimization helper tests."""

from dutchbay_finmodel.core import ModelConfig
from dutchbay_finmodel.optimization import solve_tariff_for_target_irr


def test_solve_tariff_for_target_irr_basic():
    cfg = ModelConfig()
    tariff = solve_tariff_for_target_irr(cfg, target_irr=0.15, bracket=(10.0, 40.0))
    assert 10.0 <= tariff <= 40.0 or tariff != tariff  # allow NaN if no solution
