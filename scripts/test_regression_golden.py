#!/usr/bin/env python3
"""Golden regression tests for hardened Dutch Bay model.

These are *snapshots* tied to the current ModelConfig defaults.
When you update the validated IC / lender case, recompute and
update the expected values here intentionally.
"""

import pytest
from dutchbay_finmodel.core import (
    ModelConfig,
    build_financial_model,
    calculate_equity_irr,
    calculate_llcr_plcr,
    calculate_project_irr,
)


def test_golden_base_case_regression():
    cfg = ModelConfig()
    df, proj_cf, eq_cf, cap = build_financial_model(cfg)
    ratios = calculate_llcr_plcr(cfg)

    # Expected values derived from the current hardened implementation.
    # These act as a tripwire for unintended code/assumption drift.
    expected_project_irr = 0.12016991965463464
    expected_equity_irr = 0.2044695761443247
    expected_min_dscr = 1.0518521216734873
    expected_llcr = 1.499648158448138
    expected_plcr = 1.7749711568646562

    prj_irr = calculate_project_irr(cfg)
    eq_irr = calculate_equity_irr(cfg)
    min_dscr = float(df["DSCR"].replace([float("inf")], 9999).min())

    assert prj_irr == pytest.approx(expected_project_irr, rel=1e-9)
    assert eq_irr == pytest.approx(expected_equity_irr, rel=1e-9)
    assert min_dscr == pytest.approx(expected_min_dscr, rel=1e-9)
    assert ratios["llcr"] == pytest.approx(expected_llcr, rel=1e-9)
    assert ratios["plcr"] == pytest.approx(expected_plcr, rel=1e-9)
