from dutchbay_v13.core import build_financial_model


def test_dscr_consistency():
    res = build_financial_model({})
    df = res["annual_data"]
    # recompute dscr from cfads/debt_service and compare to stored values
    calc = (df["cfads_usd"] / df["debt_service_usd"]).replace([float("inf")], 0.0)
    # stored dscr may be None where debt_service ~ 0; fillna for compare
    stored = df["dscr"].fillna(0.0)
    assert ((calc - stored).abs() < 1e-9).all()
    # min_dscr should match dataframe minimum (excluding NaN)
    assert (
        abs(res["min_dscr"] - stored.replace(0.0, float("nan")).min(skipna=True)) < 1e-9
    )
