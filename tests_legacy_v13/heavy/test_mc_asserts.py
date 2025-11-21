import importlib, math

def test_mc_generate_and_run():
    m = importlib.import_module("dutchbay_v13.monte_carlo")
    assert hasattr(m, "generate_mc_parameters")
    params = m.generate_mc_parameters(n=4, base=20.30)
    assert isinstance(params, list) and len(params) == 4
    res = m.run_monte_carlo({"tariff_lkr_per_kwh": 20.30}, n=4)
    assert "results" in res and len(res["results"]) == 4
    irrs = [r["equity_irr"] for r in res["results"]]
    # strictly increasing with tariff
    assert all(irrs[i] <= irrs[i+1] for i in range(len(irrs)-1))
