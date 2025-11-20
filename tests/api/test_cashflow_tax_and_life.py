"""Deeper cashflow tests: project life, tax, and stress scenarios.

Canonical engine path:
    dutchbay_v14chat/finance/cashflow.py

These tests are about lender-grade comfort:
- Full CFADS shape for 5 vs 20 year lives
- Tax holiday vs no holiday
- Enhanced capital allowance vs baseline
- High-opex stress vs baseline
- Zero-tariff stress case
"""

from pathlib import Path
import sys
import copy

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root (/DutchBay_EPC_Model) is on sys.path
# ---------------------------------------------------------------------------

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]  # .../DutchBay_EPC_Model

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dutchbay_v14chat.finance import cashflow as cf_mod  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
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
# Tests
# ---------------------------------------------------------------------------


def test_project_life_5_vs_20_years_shapes_and_magnitude():
    """5-year vs 20-year project life should change CFADS length, not explode."""
    p5 = copy.deepcopy(BASE_PARAMS)
    p5["returns"]["project_life_years"] = 5

    p20 = copy.deepcopy(BASE_PARAMS)
    p20["returns"]["project_life_years"] = 20

    cf5 = _run_cfads(p5)
    cf20 = _run_cfads(p20)

    assert len(cf5) == 5
    assert len(cf20) == 20

    # The first 5 years should be broadly in the same ballpark;
    # we just assert they are non-zero and same sign.
    assert any(x != 0.0 for x in cf5)
    assert any(x != 0.0 for x in cf20[:5])
    assert all((x >= 0 and y >= 0) or (x <= 0 and y <= 0) for x, y in zip(cf5, cf20[:5]))


def test_tax_holiday_increases_early_cfads():
    """Tax holiday should increase CFADS in holiday years vs no-holiday baseline."""
    base = copy.deepcopy(BASE_PARAMS)

    no_holiday = copy.deepcopy(base)
    no_holiday["tax"]["tax_holiday_years"] = 0
    no_holiday["tax"]["tax_holiday_start_year"] = 1

    with_holiday = copy.deepcopy(base)
    with_holiday["tax"]["tax_holiday_years"] = 3
    with_holiday["tax"]["tax_holiday_start_year"] = 1

    cf_no = _run_cfads(no_holiday)
    cf_hol = _run_cfads(with_holiday)

    # Compare first 3 years
    early_no = cf_no[:3]
    early_hol = cf_hol[:3]

    # CFADS with holiday should not be worse; at least one year strictly better
    assert all(h >= n for h, n in zip(early_hol, early_no))
    assert any(h > n for h, n in zip(early_hol, early_no))


def test_enhanced_allowance_does_not_hurt_early_cfads():
    """Enhanced capital allowance should not reduce early CFADS vs baseline.

    Implementation may or may not actually improve CFADS, but it must not
    *worsen* the early-year CFADS profile relative to baseline.
    """
    base = copy.deepcopy(BASE_PARAMS)

    baseline = copy.deepcopy(base)
    baseline["tax"]["enhanced_capital_allowance_pct"] = 1.0

    enhanced = copy.deepcopy(base)
    enhanced["tax"]["enhanced_capital_allowance_pct"] = 2.0

    cf_base = _run_cfads(baseline)
    cf_enh = _run_cfads(enhanced)

    # Focus on the first 5 years where depreciation effects matter most
    early_base = cf_base[:5]
    early_enh = cf_enh[:5]

    # Enhanced allowance must not make CFADS worse in early years.
    assert all(e >= b for e, b in zip(early_enh, early_base))


def test_high_opex_stress_reduces_cfads():
    """Very high opex should reduce CFADS vs a reasonable baseline."""
    base_low = copy.deepcopy(BASE_PARAMS)
    base_low["opex"]["usd_per_year"] = 3_000_000.0

    base_high = copy.deepcopy(BASE_PARAMS)
    base_high["opex"]["usd_per_year"] = 30_000_000.0  # 10x stress

    cf_low = _run_cfads(base_low)
    cf_high = _run_cfads(base_high)

    # Both lists same length, same life
    assert len(cf_low) == len(cf_high) == BASE_PARAMS["returns"]["project_life_years"]

    # Total CFADS under high-opex scenario should be lower
    assert sum(cf_high) < sum(cf_low)


def test_zero_tariff_collapses_cfads():
    """Zero-tariff stress: CFADS should collapse towards zero or below."""
    zero_tariff = copy.deepcopy(BASE_PARAMS)
    zero_tariff["tariff"]["lkr_per_kwh"] = 0.0

    cf = _run_cfads(zero_tariff)

    # With no tariff, CFADS should not be significantly positive.
    # Allow for tiny numerical noise.
    max_cf = max(cf)
    assert max_cf <= 1e-6
