"""
Architecture test: IRR/NPV must only live in finance.irr.
"""

import inspect

import analytics.core.metrics as metrics_module
import finance.irr as irr_module


def _find_irr_like_functions(mod):
    irrish = []
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        lname = name.lower()
        if "irr" in lname or "npv" in lname:
            irrish.append(name)
    return irrish


def test_irr_npvs_exist_in_finance_irr():
    names = _find_irr_like_functions(irr_module)
    assert names, "Expected IRR/NPV functions in finance.irr, found none."


def test_no_irr_npvs_in_metrics_module():
    names = _find_irr_like_functions(metrics_module)
    assert not names, (
        "IRR/NPV-like functions must NOT be defined in "
        "analytics.core.metrics; keep them only in finance.irr."
    )
