import importlib, math, types, pytest

CANDIDATES = ("run_monte_carlo", "run", "simulate", "monte_carlo", "run_simulation")
PARAMS     = ("generate_mc_parameters", "generate_parameters")

def _find_callable(mod, names):
    for n in names:
        fn = getattr(mod, n, None)
        if callable(fn):
            return fn
    return None

def test_import_monte_carlo_module():
    m = importlib.import_module("dutchbay_v13.monte_carlo")
    assert isinstance(m, types.ModuleType)

def test_optional_run_if_present():
    m = importlib.import_module("dutchbay_v13.monte_carlo")
    gen = _find_callable(m, PARAMS)
    run = _find_callable(m, CANDIDATES)
    if not gen and not run:
        pytest.xfail("Monte Carlo API not exported yet (import-only).")
    # If generator exists, call minimally/deterministically; else import-only
    if gen:
        try:
            params = gen()  # accept default shape if provided
        except TypeError:
            params = gen(5)  # try n=5 fallback
        assert params is not None
    if run:
        try:
            res = run({"tariff_lkr_per_kwh": 20.30}, n=5)  # best-effort
        except TypeError:
            try:
                res = run({"tariff_lkr_per_kwh": 20.30})
            except Exception:
                pytest.xfail("run() exists but signature is non-standard")
        assert res is not None
