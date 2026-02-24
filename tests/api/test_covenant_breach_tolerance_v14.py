import pytest
from analytics.contracts_v14 import check_covenant_breach_with_tolerance

def test_dscr_floor_breach_with_tolerance():
    # threshold 1.30, tolerance 1bp = 0.00013
    threshold = 1.30

    # OK: exactly threshold
    assert check_covenant_breach_with_tolerance(1.30, threshold) is False

    # OK: within 1bp (e.g. 1.2999)
    assert check_covenant_breach_with_tolerance(1.2999, threshold) is False

    # BREACH: beyond 1bp (e.g. 1.299)
    # 1.30 - 0.00013 = 1.29987. 1.299 < 1.29987 is True.
    assert check_covenant_breach_with_tolerance(1.299, threshold) is True

def test_leverage_ceiling_breach_with_tolerance():
    # threshold 4.0, tolerance 1bp = 0.0004
    threshold = 4.0

    # OK: exactly threshold
    assert check_covenant_breach_with_tolerance(4.0, threshold, covenant_type="ceiling") is False

    # OK: within 1bp (4.0001)
    assert check_covenant_breach_with_tolerance(4.0001, threshold, covenant_type="ceiling") is False

    # BREACH: beyond 1bp (4.001)
    assert check_covenant_breach_with_tolerance(4.001, threshold, covenant_type="ceiling") is True

def test_invalid_inputs():
    with pytest.raises(ValueError, match="non-negative"):
        check_covenant_breach_with_tolerance(1.0, 1.0, tolerance_bps=-1)

    with pytest.raises(ValueError, match="covenant_type"):
        check_covenant_breach_with_tolerance(1.0, 1.0, covenant_type="invalid")
