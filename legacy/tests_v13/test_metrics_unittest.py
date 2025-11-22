import unittest
from dutchbay_v13.finance.metrics import irr_bisection, npv


class TestMetrics(unittest.TestCase):
    def test_irr_basic(self):
        cfs = [-100, 120]
        r = irr_bisection(cfs)
        self.assertAlmostEqual(r, 0.20, places=3)

    def test_npv_zero_at_irr(self):
        cfs = [-100, 30, 40, 50]
        r = irr_bisection(cfs)
        self.assertAlmostEqual(npv(r, cfs), 0.0, places=3)


if __name__ == "__main__":
    unittest.main()
