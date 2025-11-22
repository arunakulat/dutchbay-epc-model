from dutchbay_v13.finance.metrics import irr_bisection, npv


def test_irr_basic():
    # Invest 100, get 120 in one year -> IRR ~ 20%
    cfs = [-100, 120]
    r = irr_bisection(cfs)
    assert abs(r - 0.20) < 1e-3


def test_npv_zero_at_irr():
    cfs = [-100, 30, 40, 50]
    # find irr
    from dutchbay_v13.finance.metrics import irr_bisection

    r = irr_bisection(cfs)
    assert abs(npv(r, cfs)) < 1e-3
