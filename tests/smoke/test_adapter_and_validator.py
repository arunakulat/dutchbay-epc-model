from dutchbay_v13.validate import validate_params_dict
from dutchbay_v13.adapters import run_irr

def test_adapter_and_validator():
    p = {
        "project": {"capacity_mw": 150, "timeline": {"lifetime_years": 25}},
        "capex": {"usd_total": 225_000_000},
        "Financing_Terms": {
            "debt_ratio": 0.70,
            "tenor_years": 15,
            "interest_only_years": 2,
            "amortization": "sculpted",
            "dscr_target": 1.30,
            "min_dscr": 1.20,
            "mix": {"lkr_max": 0.45, "dfi_max": 0.10, "usd_commercial_min": 0.20},
            "rates": {"lkr_floor": 0.08, "usd_floor": 0.075, "dfi_floor": 0.065},
            "reserves": {"dsra_months": 6},
        },
        "metrics": {"npv_discount_rate": 0.12},
    }
    # relaxed-mode validation
    validate_params_dict(p, mode="relaxed")

    # simple CFADS stream (flat 50m for 25y)
    annual = [{"year": i+1, "cfads_usd": 50_000_000.0} for i in range(25)]
    res = run_irr(p, annual)

    assert isinstance(res, dict), "adapter must return a mapping"
    assert "npv_12" in res, "summary must include NPV"
