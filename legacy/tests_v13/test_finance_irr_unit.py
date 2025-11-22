from dutchbay_v13.finance.irr import irr, npv


def test_irr_and_npv_simple():
    cfs = [-100, 60, 60]
    r = irr(cfs)
    assert 0.12 < r < 0.14  # ~19.1%
    assert abs(npv(r, cfs)) < 1e-6 or npv(r, cfs) == 0  # sanity
