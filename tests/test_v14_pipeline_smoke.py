from dutchbay_v13.v14_pipeline import run_v14_pipeline


def test_v14_pipeline_smoke():
    """
    Very light smoke test that:
    - pipeline runs end-to-end using the default YAML
    - basic shapes are consistent
    - core metrics (LLCR/PLCR) are positive
    """
    result = run_v14_pipeline()

    years = result["years"]
    cfads = result["cfads_pre_debt"]
    dscr = result["dscr"]
    llcr = result["llcr"]
    plcr = result["plcr"]
    equity_table = result["equity_table"]

    # Shapes
    assert isinstance(years, list) and len(years) > 4
    assert len(cfads) == len(years)
    assert len(dscr) == len(years)

    # Metrics should be finite and positive in the base case
    assert llcr > 0.0
    assert plcr > 0.0

    # Equity table should look like a DataFrame-like object with rows
    assert hasattr(equity_table, "shape")
    rows, cols = equity_table.shape
    assert rows > 0
    assert cols >= 3

    