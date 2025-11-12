import importlib

MODULES = [
    # package roots
    "dutchbay_v13",
    # core surfaces
    "dutchbay_v13.api",
    "dutchbay_v13.adapters",
    "dutchbay_v13.config",
    "dutchbay_v13.core",
    "dutchbay_v13.types",
    "dutchbay_v13.schema",
    "dutchbay_v13.validate",
    "dutchbay_v13.scenario_runner",
    # finance stack
    "dutchbay_v13.finance.irr",
    "dutchbay_v13.finance.debt",
    "dutchbay_v13.finance.cashflow",
    "dutchbay_v13.finance.metrics",
    # analytics
    "dutchbay_v13.monte_carlo",
    "dutchbay_v13.sensitivity",
    "dutchbay_v13.optimization",
    # reporting
    "dutchbay_v13.charts",
    "dutchbay_v13.report",
    "dutchbay_v13.report_pdf",
    # domain
    "dutchbay_v13.epc",
]

def test_import_surface():
    for name in MODULES:
        m = importlib.import_module(name)
        assert hasattr(m, "__spec__"), f"import failed: {name}"
