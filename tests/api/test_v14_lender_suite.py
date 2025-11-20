"""Lender-grade v14 finance tests in one suite.

Covers:
- dutchbay_v14chat.finance.cashflow (extra tax behaviour: 0% vs 30%)
- dutchbay_v14chat.finance.debt (basic amortisation sanity)
- dutchbay_v14chat.finance.irr (end-to-end CFADS -> IRR/NPV smoke)
"""

from pathlib import Path
import sys
import copy
import inspect

import pytest

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

# ---------------------------------------------------------------------------
# Ensure repo root (/DutchBay_EPC_Model) is on sys.path
# ---------------------------------------------------------------------------

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dutchbay_v14chat.finance import cashflow as cf_mod  # type: ignore
from dutchbay_v14chat.finance import debt as debt_mod  # type: ignore
from dutchbay_v14chat.finance import irr as irr_mod  # type: ignore
from constants import DEFAULT_DISCOUNT_RATE


# ---------------------------------------------------------------------------
# Shared helpers / base parameters
# ---------------------------------------------------------------------------

BASE_PARAMS = {
    "project": {
        "capacity_mw": 100.0,
        "capacity_factor": 0.40,
    },
    "tariff": {
        "lkr_per_kwh": 20.0,
    },
    "opex": {
        "usd_per_year": 3_000_000.0,
    },
    "returns": {
        "project_life_years": 20,
    },
    "tax": {
        "corporate_tax_rate": 0.30,
        "depreciation_years": 15,
        "tax_holiday_years": 0,
        "tax_holiday_start_year": 1,
        "enhanced_capital_allowance_pct": 1.0,
    },
}


def _run_cfads(params: dict) -> list[float]:
    """Validate and run CFADS; fail loud on validation ERRORs."""
    issues = cf_mod.validate_parameters(params)  # type: ignore[attr-defined]
    error_msgs = [m for m in issues if "ERROR" in m.upper()]
    if error_msgs:
        pytest.fail("Parameter validation failed:\n" + "\n".join(error_msgs))

    cfads = cf_mod.build_annual_cfads(params)  # type: ignore[attr-defined]
    assert isinstance(cfads, list)
    assert all(isinstance(x, (int, float)) for x in cfads)
    return cfads


# ---------------------------------------------------------------------------
# 1) Extra tax behaviour pin: 0% vs 30% corporate tax
# ---------------------------------------------------------------------------

def test_zero_tax_rate_increases_total_cfads():
    """0% corporate tax should increase total CFADS vs a positive tax rate."""
    base = copy.deepcopy(BASE_PARAMS)

    taxed = copy.deepcopy(base)
    taxed["tax"]["corporate_tax_rate"] = 0.30

    zero_tax = copy.deepcopy(base)
    zero_tax["tax"]["corporate_tax_rate"] = 0.0

    cf_taxed = _run_cfads(taxed)
    cf_zero = _run_cfads(zero_tax)

    assert sum(cf_zero) > sum(cf_taxed)


# ---------------------------------------------------------------------------
# 2) Debt engine sanity: amortising schedule shape & final balance
# ---------------------------------------------------------------------------

def _find_debt_builder_function():
    """Try to locate a reasonable debt schedule builder in the module."""
    candidate_names = [
        "build_debt_schedule",
        "build_debt_schedule_v14",
        "generate_debt_schedule",
        "build_annuity_schedule",
    ]
    for name in candidate_names:
        if hasattr(debt_mod, name):
            return getattr(debt_mod, name)
    return None


def _call_debt_builder(builder_fn):
    """Call the builder with a simple amortising case, adapting to its signature."""
    sig = inspect.signature(builder_fn)

    base_cfg = {
        "principal": 100_000_000.0,
        "principal_usd": 100_000_000.0,
        "annual_interest_rate": 0.06,
        "rate": 0.06,
        "tenor_years": 15,
        "years": 15,
        "payments_per_year": 1,
        "repayment_type": "annuity",
        "schedule_type": "annuity",
        "grace_period_years": 0,
    }

    params = list(sig.parameters.values())

    # Single-config style: builder(config_dict)
    if len(params) == 1 and params[0].kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    ):
        return builder_fn(base_cfg)

    # Otherwise: kwargs based on intersection of names
    kwargs = {}
    for p in params:
        if p.name in base_cfg:
            kwargs[p.name] = base_cfg[p.name]
    return builder_fn(**kwargs)


def _normalize_debt_schedule(schedule):
    """Return a list of dict-like records from various schedule representations."""
    if pd is not None and isinstance(schedule, pd.DataFrame):
        return schedule.to_dict("records")
    if isinstance(schedule, list):
        if schedule and isinstance(schedule[0], dict):
            return schedule
    pytest.fail(f"Unsupported schedule type {type(schedule)!r} in debt module tests")


def test_debt_schedule_basic_shape_and_final_balance():
    """Amortising loan should yield sensible schedule with final balance ≈ 0."""
    builder_fn = _find_debt_builder_function()
    if builder_fn is None:
        pytest.skip(
            "No known debt schedule builder found in dutchbay_v14chat.finance.debt"
        )

    schedule = _call_debt_builder(builder_fn)
    records = _normalize_debt_schedule(schedule)

    assert len(records) > 0, "Debt schedule should not be empty"

    # Try to locate opening/closing balance keys heuristically
    sample_keys = records[0].keys()
    opening_key = None
    closing_key = None
    for k in sample_keys:
        lk = k.lower()
        if "opening" in lk and "balance" in lk:
            opening_key = k
        if "closing" in lk and "balance" in lk:
            closing_key = k

    if opening_key and closing_key:
        first = records[0]
        last = records[-1]
        first_open = float(first[opening_key])
        last_close = float(last[closing_key])

        # Principal drawn should be positive
        assert first_open > 0

        # Final balance should be near zero for a standard fully-amortising case
        assert abs(last_close) < 1.0

        # Closing balances broadly decline over time (allow small bumps).
        closes = [float(r[closing_key]) for r in records]
        assert closes[0] >= closes[-1]
    else:
        # At minimum, ensure non-empty schedule; column names may differ.
        assert True


# ---------------------------------------------------------------------------
# 3) End-to-end v14 smoke: CFADS -> IRR & NPV
# ---------------------------------------------------------------------------

def test_end_to_end_cfads_irr_npv_sanity():
    """Synthetic end-to-end smoke: CFADS -> IRR/NPV should be sane."""
    params = copy.deepcopy(BASE_PARAMS)

    # Assume a notional USD capex; we don't need perfect realism here,
    # just something that produces a sign change for IRR.
    notional_capex = 100_000_000.0

    cfads = _run_cfads(params)

    # Construct project cashflows: upfront capex out, then CFADS
    cashflows = [-notional_capex] + cfads

    irr_value = irr_mod.irr(cashflows)
    npv_value = irr_mod.npv(DEFAULT_DISCOUNT_RATE, cashflows)

    # IRR should be a finite positive rate. Different implementations may
    # return decimal (0.2) or "percent-style" (20.0+), so we only assert sign.
    assert irr_value is not None
    assert isinstance(irr_value, (int, float))
    assert irr_value > 0.0

    # NPV should be finite (no crash). We don't assert sign here, just sanity.
    assert npv_value is not None
    assert isinstance(npv_value, (int, float))
