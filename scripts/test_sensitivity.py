#!/usr/bin/env python3
"""Sensitivity tests."""

from dutchbay_finmodel.core import ModelConfig
from dutchbay_finmodel.sensitivity import one_way_sensitivity


def test_one_way_sensitivity_runs():
    cfg = ModelConfig()
    values = [0.35, 0.40, 0.45]
    df = one_way_sensitivity(cfg, "capacity_factor_p50", values)
    assert len(df) == len(values)
    assert "equity_irr" in df.columns
