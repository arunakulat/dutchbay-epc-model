from dutchbay_v13.finance.irr import irr, npv


def test_irr_simple():
    r = irr([-100.0, 60.0, 60.0])
    assert r is not None
    assert abs(r - 0.13079) < 1e-3  # ~13.079%


def test_npv_zero_rate():
    cf = [-100.0, 30.0, 40.0, 50.0]
    assert abs(npv(0.0, cf) - sum(cf)) < 1e-9
