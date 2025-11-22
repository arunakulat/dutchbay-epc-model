from dutchbay_v13.core import build_financial_model


def test_debt_yaml_override_changes_output():
    # Lower debt ratio should typically increase equity IRR (lower leverage risk here given simplified model),
    # We just assert both runs succeed and outputs differ to ensure override is applied.
    base = build_financial_model({})
    alt = build_financial_model(
        {"debt": {"debt_ratio": 0.60, "tenor_years": 10, "grace_years": 0}}
    )
    assert base["min_dscr"] != alt["min_dscr"]
