def test_imports():
    import dutchbay_v13  # noqa: F401
    from dutchbay_v13.core import build_financial_model

    assert callable(build_financial_model)
