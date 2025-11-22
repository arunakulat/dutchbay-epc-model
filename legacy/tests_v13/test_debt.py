from dutchbay_v13.db_types import DebtTerms
from dutchbay_v13.finance.debt import amortization_schedule, blended_rate


def test_debt_schedule_principal_sums():
    total = 100.0
    terms = DebtTerms()
    sched = amortization_schedule(total, terms, project_years=20)
    principal_sum = sum(y.principal for y in sched)
    assert abs(principal_sum - total) < 1e-6


def test_blended_rate_bounds():
    terms = DebtTerms()
    r = blended_rate(terms)
    # should lie within min/max of component rates
    lo = min(terms.usd_dfi_rate, terms.usd_mkt_rate, terms.lkr_rate)
    hi = max(terms.usd_dfi_rate, terms.usd_mkt_rate, terms.lkr_rate)
    assert lo <= r <= hi
